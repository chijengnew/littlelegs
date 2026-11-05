"""刪除意圖的持久儲存：RDS 備份範圍之外、不可覆寫。

- 意圖只含：操作 ID、類型、目標不可變 UUID／Firebase UID、接受時間與最小處理資訊；不含孩子、行程或座標。
- 寫入採條件寫入（S3 If-None-Match: *），避免覆寫既有意圖；完成標記另寫一個物件。
- 正式環境用 S3（加密 bucket、IAM 限專案前綴）；LocalIntentStore 只供開發與測試。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class DeletionIntent:
    operation_id: str
    kind: str
    user_id: str
    firebase_uid: str | None
    target_id: str | None
    accepted_at: str


class IntentWriteFailed(Exception):
    """明確失敗：未接受刪除。"""


class IntentWriteUnknown(Exception):
    """結果不明：必須沿用同一 operation_id 查核／重試。"""


class IntentStore(Protocol):
    async def put_intent(self, intent: DeletionIntent) -> bool: ...

    async def get_intent(self, operation_id: str) -> DeletionIntent | None: ...

    async def is_completed(self, operation_id: str) -> bool: ...

    async def mark_completed(self, operation_id: str, completed_at: str) -> None: ...

    async def list_pending(self) -> list[DeletionIntent]: ...

    async def list_all(self) -> list[DeletionIntent]: ...


class LocalIntentStore:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        (self.root / "intents").mkdir(parents=True, exist_ok=True)
        (self.root / "completed").mkdir(parents=True, exist_ok=True)

    async def put_intent(self, intent: DeletionIntent) -> bool:
        p = self.root / "intents" / f"{intent.operation_id}.json"
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = await self.get_intent(intent.operation_id)
            if existing != intent:
                raise IntentWriteFailed("同一 operation_id 已有不同內容的意圖") from None
            return False
        except OSError as e:
            raise IntentWriteFailed(str(e)) from e
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(intent), f)
            f.flush()
            os.fsync(f.fileno())
        return True

    async def get_intent(self, operation_id: str) -> DeletionIntent | None:
        p = self.root / "intents" / f"{operation_id}.json"
        if not p.exists():
            return None
        return DeletionIntent(**json.loads(p.read_text(encoding="utf-8")))

    async def is_completed(self, operation_id: str) -> bool:
        return (self.root / "completed" / f"{operation_id}.json").exists()

    async def mark_completed(self, operation_id: str, completed_at: str) -> None:
        p = self.root / "completed" / f"{operation_id}.json"
        if not p.exists():
            p.write_text(json.dumps({"operation_id": operation_id, "completed_at": completed_at}), encoding="utf-8")

    async def list_all(self) -> list[DeletionIntent]:
        return [
            DeletionIntent(**json.loads(p.read_text(encoding="utf-8")))
            for p in sorted((self.root / "intents").glob("*.json"))
        ]

    async def list_pending(self) -> list[DeletionIntent]:
        return [i for i in await self.list_all() if not await self.is_completed(i.operation_id)]


class S3IntentStore:
    """S3 實作（需要 boto3；以 EC2 instance profile 取得限專案前綴的 Put/Get/List 權限）。"""

    def __init__(self, bucket: str, prefix: str) -> None:
        import boto3

        self._s3 = boto3.client("s3")
        self._b, self._p = bucket, prefix.rstrip("/") + "/"

    async def _call(self, fn, **kw):
        import anyio

        return await anyio.to_thread.run_sync(lambda: fn(**kw))

    async def put_intent(self, intent: DeletionIntent) -> bool:
        from botocore.exceptions import ClientError, EndpointConnectionError, ReadTimeoutError

        body = json.dumps(asdict(intent)).encode()
        try:
            await self._call(
                self._s3.put_object,
                Bucket=self._b,
                Key=f"{self._p}intents/{intent.operation_id}.json",
                Body=body,
                IfNoneMatch="*",
                ServerSideEncryption="aws:kms",
            )
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("PreconditionFailed", "ConditionalRequestConflict"):
                existing = await self.get_intent(intent.operation_id)
                if existing != intent:
                    raise IntentWriteFailed("同一 operation_id 已有不同內容的意圖") from e
                return False
            raise IntentWriteFailed(code or "ClientError") from e
        except (EndpointConnectionError, ReadTimeoutError) as e:
            raise IntentWriteUnknown(type(e).__name__) from e

    async def get_intent(self, operation_id: str) -> DeletionIntent | None:
        from botocore.exceptions import ClientError

        try:
            r = await self._call(self._s3.get_object, Bucket=self._b, Key=f"{self._p}intents/{operation_id}.json")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return DeletionIntent(**json.loads(r["Body"].read()))

    async def is_completed(self, operation_id: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            await self._call(self._s3.head_object, Bucket=self._b, Key=f"{self._p}completed/{operation_id}.json")
            return True
        except ClientError:
            return False

    async def mark_completed(self, operation_id: str, completed_at: str) -> None:
        from botocore.exceptions import ClientError

        try:
            await self._call(
                self._s3.put_object,
                Bucket=self._b,
                Key=f"{self._p}completed/{operation_id}.json",
                Body=json.dumps({"operation_id": operation_id, "completed_at": completed_at}).encode(),
                IfNoneMatch="*",
                ServerSideEncryption="aws:kms",
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "PreconditionFailed":
                raise

    async def list_all(self) -> list[DeletionIntent]:
        out = []
        token = None
        while True:
            kw = {"Bucket": self._b, "Prefix": f"{self._p}intents/"}
            if token:
                kw["ContinuationToken"] = token
            r = await self._call(self._s3.list_objects_v2, **kw)
            for obj in r.get("Contents", []):
                oid = obj["Key"].rsplit("/", 1)[-1].removesuffix(".json")
                i = await self.get_intent(oid)
                if i:
                    out.append(i)
            if not r.get("IsTruncated"):
                return out
            token = r.get("NextContinuationToken")

    async def list_pending(self) -> list[DeletionIntent]:
        return [i for i in await self.list_all() if not await self.is_completed(i.operation_id)]
