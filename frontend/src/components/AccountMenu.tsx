"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { safeNext, withNext } from "@/lib/authFlow";
import { useAuth } from "./AuthProvider";
import SignOutButton from "./auth/SignOutButton";
import { UserIcon } from "./icons";
import ui from "./ui.module.css";
import s from "./AccountMenu.module.css";

type Variant = "guest" | "member" | "unverified" | "error";

const initial = (email: string | null | undefined) => (email?.trim()[0] ?? "?").toUpperCase();

export default function AccountMenu() {
  const pathname = usePathname();
  return <Menu key={pathname} pathname={pathname} />;
}

function Menu({ pathname }: { pathname: string }) {
  const t = useTranslations();
  const auth = useAuth();
  const next = safeNext(pathname);
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!auth.booted || auth.pending) {
    return (
      <>
        <span className="visually-hidden" role="status">{t("auth.verifying")}</span>
        <span className={s.placeholder} aria-hidden="true" />
      </>
    );
  }

  const variant: Variant = auth.member ? "member" : auth.unverified ? "unverified" : auth.user ? "error" : "guest";
  const close = () => setOpen(false);

  return (
    <div
      className={s.root}
      ref={root}
      onBlur={(e) => {
        const to = e.relatedTarget as Node | null;
        if (open && to && !root.current?.contains(to)) setOpen(false);
      }}
    >
      {variant === "member" && <span className="visually-hidden" role="status">{t("auth.verified")}</span>}
      {variant === "error" && <span className="visually-hidden" role="status">{t("auth.verificationFailed")}</span>}
      <button
        ref={trigger}
        type="button"
        className={variant === "member" ? s.triggerMember : s.trigger}
        aria-label={t(`accountMenu.${variant}`)}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <UserIcon />
        {(variant === "unverified" || variant === "error") && <span className={s.dot} aria-hidden="true" />}
      </button>
      <div id={panelId} className={s.panel} hidden={!open}>
        {variant === "guest" && (
          <>
            <p className={s.title}>{t("accountMenu.guestTitle")}</p>
            <p className={s.hint}>{t("accountMenu.guestHint")}</p>
            <div className={s.stack}>
              <Link className={`${ui.primary} ${ui.block}`} href={withNext("/login", next)} onClick={close}>
                {t("app.login")}
              </Link>
              <Link className={`${ui.secondary} ${ui.block}`} href={withNext("/register", next)} onClick={close}>
                {t("accountMenu.register")}
              </Link>
            </div>
          </>
        )}
        {variant === "member" && (
          <>
            <div className={s.who}>
              <span className={s.avatar} aria-hidden="true">{initial(auth.user?.email)}</span>
              <p className={s.email}>{auth.user?.email}</p>
            </div>
            <ul className={s.list}>
              <li>
                <Link className={s.item} href="/account?tab=history" onClick={close}>{t("accountMenu.history")}</Link>
              </li>
              <li>
                <Link className={s.item} href="/account?tab=favorites" onClick={close}>{t("accountMenu.favorites")}</Link>
              </li>
              <li>
                <Link className={s.item} href="/account?tab=account" onClick={close}>{t("accountMenu.settings")}</Link>
              </li>
            </ul>
            <div className={s.foot}>
              <SignOutButton className={s.item} icon />
            </div>
          </>
        )}
        {variant === "unverified" && (
          <>
            <p className={s.title}>{t("accountMenu.unverifiedTitle")}</p>
            <p className={s.hint}>{t("accountMenu.unverifiedHint")}</p>
            <div className={s.stack}>
              <Link className={`${ui.primary} ${ui.block}`} href={withNext("/verify-email", next)} onClick={close}>
                {t("auth.verifyEmailNav")}
              </Link>
            </div>
            <div className={s.foot}>
              <SignOutButton className={s.item} icon />
            </div>
          </>
        )}
        {variant === "error" && (
          <>
            <p className={s.title}>{t("auth.verificationFailed")}</p>
            <div className={s.stack}>
              <Link className={`${ui.secondary} ${ui.block}`} href="/account" onClick={close}>
                {t("auth.account")}
              </Link>
            </div>
            <div className={s.foot}>
              <SignOutButton className={s.item} icon />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
