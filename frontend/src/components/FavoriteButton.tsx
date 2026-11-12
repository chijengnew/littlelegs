"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { api, type PlanResponse } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import { withNext } from "@/lib/authFlow";
import { toConditions } from "@/lib/form";
import { uuidv7 } from "@/lib/ids";
import { linkFavoritePacking } from "@/lib/packingStorage";
import { useAuth } from "./AuthProvider";
import { usePlanner } from "./PlannerProvider";
import type { EditStop } from "./PlanView";
import { ArrowRightIcon, HeartIcon } from "./icons";
import ui from "./ui.module.css";

type SaveAs = "plan" | "unverified" | "infeasible";
const SAVE_AS: Record<PlanResponse["feasibility"], SaveAs> = { feasible: "plan", unverified: "unverified", infeasible: "infeasible" };

type Props = { plan: PlanResponse | null; stops: EditStop[]; dirty: boolean; busy: boolean };

export default function FavoriteButton({ plan, stops, dirty, busy }: Props) {
  const t = useTranslations();
  const auth = useAuth();
  const { form } = usePlanner();
  const [result, setResult] = useState<{ fp: string; created: boolean } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const op = useRef<{ fp: string; key: string } | null>(null);

  const body =
    plan && form?.start && !dirty && stops.length > 0
      ? {
          conditions: toConditions(form),
          stops: stops.map(({ place_id, stay_minutes }) => ({ place_id, stay_minutes })),
          saved_as: SAVE_AS[plan.feasibility],
          source_history_id: plan.history?.id ?? null,
        }
      : null;
  const fp = body ? JSON.stringify(body) : null;
  const saved = result && result.fp === fp ? result : null;

  async function save() {
    if (!body || !fp || saving) return;
    if (body.saved_as !== "plan" && !confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    if (!op.current || op.current.fp !== fp) op.current = { fp, key: uuidv7() };
    setSaving(true);
    setError(null);
    try {
      const { data, error: problem, response } = await api.POST("/v1/favorites", {
        params: { header: { "Idempotency-Key": op.current.key } },
        body,
      });
      if (data) {
        setResult({ fp, created: data.created });
        if (auth.user && plan) linkFavoritePacking(auth.user.uid, data.favorite.id, plan.query_id);
        op.current = null;
      } else setError(toUiError(t, problem, response.status).message);
    } catch (e) {
      setError(toUiError(t, e).message);
    } finally {
      setSaving(false);
    }
  }

  const star = <HeartIcon />;
  if (!auth.configured || !auth.booted || auth.pending || (auth.user && !auth.member)) {
    return (
      <>
        <button type="button" className={ui.secondary} disabled>{star}{t("favorite.save")}</button>
        {!auth.configured && <p className={ui.hint} style={{ marginTop: -4 }}>{t("auth.disabledFeature")}</p>}
      </>
    );
  }
  if (!auth.user) {
    return (
      <>
        <Link className={ui.secondary} href={withNext("/login", "/planner")}>{star}{t("favorite.loginToSave")}</Link>
      </>
    );
  }
  if (saved) {
    return (
      <div className={ui.bannerOk} role="status">
        <HeartIcon fill="currentColor" />
        <div>
          <strong>{t(saved.created ? "favorite.saved" : "favorite.savedExisting")}</strong>
          <p style={{ margin: "2px 0 0" }}>
            <Link className={ui.inlineNav} href="/account?tab=favorites" style={{ marginLeft: "calc(var(--space-2) * -1)" }}>
              {t("favorite.viewInAccount")}
              <ArrowRightIcon className={ui.arrowEnd} />
            </Link>
          </p>
        </div>
      </div>
    );
  }
  if (confirming && body) {
    return (
      <div className={ui.bannerWarn} role="alertdialog" aria-labelledby="fav-confirm">
        <div>
          <p id="fav-confirm" style={{ margin: 0 }}>
            {t(body.saved_as === "infeasible" ? "favorite.confirmInfeasible" : "favorite.confirmUnverified")}
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button type="button" className={ui.secondary} onClick={() => setConfirming(false)}>{t("favorite.cancel")}</button>
            <button type="button" className={ui.primary} onClick={save} disabled={saving || busy}>{t("favorite.confirmSave")}</button>
          </div>
        </div>
      </div>
    );
  }
  return (
    <>
      <button type="button" className={ui.secondary} onClick={save} disabled={!body || busy || saving} aria-busy={saving}>
        {star}{saving ? t("favorite.saving") : t("favorite.save")}
      </button>
      {dirty && <p className={ui.hint} style={{ marginTop: -4 }}>{t("favorite.checkFirst")}</p>}
      {error && <p className={ui.error} role="alert">{error}</p>}
    </>
  );
}
