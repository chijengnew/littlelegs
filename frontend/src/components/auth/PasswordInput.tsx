"use client";

import { useState, type InputHTMLAttributes } from "react";
import { useTranslations } from "next-intl";
import { EyeIcon, EyeOffIcon } from "../icons";
import ui from "../ui.module.css";
import s from "./auth.module.css";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className">;

export default function PasswordInput(props: Props) {
  const t = useTranslations("auth");
  const [shown, setShown] = useState(false);
  return (
    <div className={s.password}>
      <input {...props} type={shown ? "text" : "password"} className={ui.input} />
      <button
        type="button"
        className={s.reveal}
        aria-label={t("showPassword")}
        aria-pressed={shown}
        aria-controls={props.id}
        disabled={props.disabled}
        onClick={() => setShown((v) => !v)}
      >
        {shown ? <EyeOffIcon size={20} /> : <EyeIcon size={20} />}
      </button>
    </div>
  );
}
