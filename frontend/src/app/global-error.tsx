"use client";

import Link from "next/link";
import messages from "../../messages/zh-TW.json";
import StatePanel from "@/components/StatePanel";
import ui from "@/components/ui.module.css";
import "./globals.css";

export default function GlobalError({ retry }: { error: unknown; retry: () => void }) {
  const m = messages.state;
  return (
    <html lang="zh-TW">
      <body>
        <title>{`${m.errorTitle}｜${messages.app.name}`}</title>
        <main id="main">
          <StatePanel
            tone="error"
            level={1}
            live="alert"
            title={m.errorTitle}
            description={<p>{m.errorBody}</p>}
            actions={
              <>
                <button type="button" className={ui.primary} onClick={() => retry()}>{m.retry}</button>
                <Link className={ui.secondary} href="/">{m.home}</Link>
              </>
            }
          />
        </main>
      </body>
    </html>
  );
}
