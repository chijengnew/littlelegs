"use client";

import { useLayoutEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api/client";
import { toUiError } from "@/lib/api/problem";
import {
  FEEDBACK_TYPES,
  MAX_FEEDBACK_LENGTH,
  feedbackContext,
  toFeedbackBody,
  validateFeedback,
  type FeedbackContext,
  type FeedbackErrors,
  type FeedbackType,
} from "@/lib/feedback";
import ui from "./ui.module.css";
import a from "./auth/auth.module.css";
import s from "./FeedbackForm.module.css";

export default function FeedbackPage() {
  const params = useSearchParams();
  return <FeedbackForm key={params.toString()} ctx={feedbackContext(params)} />;
}

function FeedbackForm({ ctx }: { ctx: FeedbackContext }) {
  const t = useTranslations();
  const [type, setType] = useState<FeedbackType>(ctx.type);
  const [rating, setRating] = useState<number | null>(null);
  const [content, setContent] = useState("");
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<FeedbackErrors>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useLayoutEffect(() => () => setDone(false), []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const v = validateFeedback({ content, email });
    setErrors(v);
    setProblem(null);
    if (v.content || v.email) return;
    setBusy(true);
    try {
      const { data, error, response } = await api.POST("/v1/feedback", {
        body: toFeedbackBody({ type, rating, content, email }, ctx),
      });
      if (data) {
        setDone(true);
        setContent("");
        setEmail("");
        setRating(null);
      } else {
        setProblem(response.status === 429 ? t("feedback.rateLimited") : toUiError(t, error, response.status).message);
      }
    } catch (err) {
      setProblem(toUiError(t, err).message);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className={a.wrap}>
        <section className={ui.card}>
          <h1 className={a.title}>{t("feedback.title")}</h1>
          <p className={ui.bannerOk} role="status">{t("feedback.done")}</p>
          <div className={a.actions} style={{ marginTop: 16 }}>
            <Link className={ui.primary} href="/">{t("feedback.home")}</Link>
            <button type="button" className={ui.soft} onClick={() => setDone(false)}>{t("feedback.again")}</button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className={a.wrap}>
      <section className={ui.card}>
        <h1 className={a.title}>{t("feedback.title")}</h1>
        <p className={ui.hint}>{t("feedback.intro")}</p>
        <form className={s.form} onSubmit={submit} noValidate>
          <div>
            <label className={ui.label} htmlFor="fb-type">{t("feedback.type")}</label>
            <select id="fb-type" className={ui.input} value={type} onChange={(e) => setType(e.target.value as FeedbackType)}>
              {FEEDBACK_TYPES.map((x) => (
                <option key={x} value={x}>{t(`feedback.types.${x}`)}</option>
              ))}
            </select>
            {type === "place_data" && ctx.placeId && <p className={ui.hint}>{t("feedback.placeAttached")}</p>}
          </div>
          <div>
            <label className={ui.label} htmlFor="fb-rating">{t("feedback.rating")}</label>
            <select
              id="fb-rating"
              className={ui.input}
              value={rating ?? ""}
              onChange={(e) => setRating(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">{t("feedback.ratingNone")}</option>
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>{t("feedback.ratingValue", { n })}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={ui.label} htmlFor="fb-content">{t("feedback.content")}</label>
            <textarea
              id="fb-content"
              className={`${ui.input} ${s.textarea}`}
              rows={6}
              value={content}
              maxLength={MAX_FEEDBACK_LENGTH}
              aria-invalid={Boolean(errors.content)}
              aria-describedby="fb-content-hint"
              onChange={(e) => setContent(e.target.value)}
            />
            <div className={s.row} id="fb-content-hint">
              <span className={ui.hint}>{t("feedback.contentHint")}</span>
              <span className={ui.hint}>{t("feedback.contentCount", { n: content.length })}</span>
            </div>
            {errors.content && <p className={ui.error} role="alert">{t(`feedback.${errors.content}`)}</p>}
          </div>
          <div>
            <label className={ui.label} htmlFor="fb-email">{t("feedback.email")}</label>
            <input
              id="fb-email"
              className={ui.input}
              type="email"
              autoComplete="email"
              maxLength={254}
              value={email}
              aria-invalid={Boolean(errors.email)}
              onChange={(e) => setEmail(e.target.value)}
            />
            <p className={ui.hint}>{t("feedback.emailHint")}</p>
            {errors.email && <p className={ui.error} role="alert">{t(`feedback.${errors.email}`)}</p>}
          </div>
          <p className={ui.hint} style={{ margin: 0 }}>
            {t("feedback.notice")} <Link href="/privacy">{t("app.privacy")}</Link>
          </p>
          {problem && <p className={ui.bannerError} role="alert">{problem}</p>}
          <button type="submit" className={ui.primary} disabled={busy} aria-busy={busy}>
            {busy ? t("feedback.submitting") : t("feedback.submit")}
          </button>
        </form>
      </section>
    </div>
  );
}
