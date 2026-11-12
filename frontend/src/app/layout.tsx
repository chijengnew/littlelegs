import { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import { Chiron_GoRound_TC, Iansui, Nunito } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getTranslations } from "next-intl/server";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import AuthProvider from "@/components/AuthProvider";
import PlannerProvider from "@/components/PlannerProvider";
import { ArrowDownIcon } from "@/components/icons";
import RegistrationGuard from "@/components/auth/RegistrationGuard";
import "./globals.css";

const nunito = Nunito({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-nunito",
});

const iansui = Iansui({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  preload: false,
  adjustFontFallback: false,
  variable: "--font-iansui",
});

const chironGoRound = Chiron_GoRound_TC({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  adjustFontFallback: false,
  variable: "--font-chiron",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return {
    title: { default: t("name"), template: `%s｜${t("name")}` },
    description: t("tagline"),
    openGraph: { siteName: t("name"), locale: "zh_TW", type: "website" },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#faf8f3",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const t = await getTranslations("app");
  return (
    <html lang="zh-TW" className={`${nunito.variable} ${iansui.variable} ${chironGoRound.variable}`}>
      <body>
        <NextIntlClientProvider>
          <AuthProvider>
          <PlannerProvider>
          <div className="skip-bar">
            <a href="#main" className="skip-link">
              <span className="skip-link-icon" aria-hidden="true"><ArrowDownIcon size={18} /></span>
              <span className="skip-link-text">{t("skip")}</span>
              <kbd className="skip-link-key" aria-hidden="true">Enter</kbd>
            </a>
          </div>
          <Suspense fallback={null}>
            <RegistrationGuard />
          </Suspense>
          <SiteHeader />
          <main id="main">{children}</main>
          <SiteFooter />
          </PlannerProvider>
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
