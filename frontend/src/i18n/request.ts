import { getRequestConfig } from "next-intl/server";

export const LOCALE = "zh-TW";

export default getRequestConfig(async () => ({
  locale: LOCALE,
  timeZone: "Asia/Taipei",
  messages: (await import(`../../messages/${LOCALE}.json`)).default,
}));
