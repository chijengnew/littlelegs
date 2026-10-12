from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")


def get_current_uid(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if credentials is None:
        raise _unauthorized()
    token = credentials.credentials

    if token.startswith("mock:") and len(token) > len("mock:"):
        return token.removeprefix("mock:")
    raise _unauthorized()