import { Suspense } from "react";
import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getTranslations } from "next-intl/server";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";
import AuthProvider from "@/components/AuthProvider";
import PlannerProvider from "@/components/PlannerProvider";
import RegistrationGuard from "@/components/auth/RegistrationGuard";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return { title: t("name"), description: t("tagline"), icons: { icon: "data:," } };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1877f2",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const t = await getTranslations("app");
  return (
    <html lang="zh-TW">
      <body>
        <NextIntlClientProvider>
          <AuthProvider>
          <PlannerProvider>
          <a href="#main" className="visually-hidden">
            {t("skip")}
          </a>
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
