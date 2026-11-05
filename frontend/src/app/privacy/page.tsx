import { getTranslations } from "next-intl/server";
import ui from "@/components/ui.module.css";
import s from "../legal.module.css";

const CONTACT_EMAIL = "chiiifortest@gmail.com";

export default async function PrivacyPage() {
  const t = await getTranslations();
  return (
    <article className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{t("app.privacy")}</h1>
        <h2>蒐集的資料</h2>
        <p>孩子年齡（必填，不蒐集姓名或生日）、起點與終點位置（含裝置座標）、出遊日期與時間、午睡與用餐時段、偏好條件、景點選擇與停留時間；會員另含帳號識別。</p>
        <h2>目的與利用方式</h2>
        <p>計算候選景點與當日行程。訪客的條件只在本次瀏覽流程中使用；會員的查詢歷史與收藏保存至會員刪除該筆或刪除帳號。會員查看地圖時，瀏覽器直接向 Google 載入地圖，Google 依其隱私權政策處理連線資料；地圖上的位置只在當次畫面使用，不另行保存。</p>
        <p>按下導航連結時，瀏覽器會把目的地（可能是你的起訖點或裝置座標）送到 Google 地圖，Google 依其隱私權政策處理；不按連結就不會傳送。</p>
        <p>出遊準備清單的勾選與自訂項目只存在你的瀏覽器，不會傳到伺服器：訪客只保留到瀏覽流程結束；會員依帳號與行程分開保存，登出、切換帳號或刪除帳號時清除，刪除單筆紀錄時也會清除該筆的清單。</p>
        <h2>意見回饋</h2>
        <p>你主動送出回饋時，我們保存回饋類型、選填的滿意度、內容、選填的聯絡信箱與來源頁面類型；景點資料錯誤回報另含該景點的內部編號。回饋不主動連結會員帳號，也不記錄完整網址或行程內容，但你填寫的內容與信箱仍可能識別個人，請不要填入孩子姓名等不必要的資料。回饋保存 12 個月後刪除；已刪除的資料可能仍留在資料庫備份中，直到備份依保留期間被覆蓋。回饋不會因刪除帳號而自動刪除；需要查詢或刪除時，請來信聯絡信箱 <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>，並提供送出時使用的信箱或回饋內容。</p>
        <h2>不提供的影響</h2>
        <p>未填孩子年齡或起點時無法查詢行程。</p>
        <h2>權利行使</h2>
        <p>查詢、更正與製給複製本請來信聯絡信箱 <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>；刪除帳號與單筆紀錄可在會員功能中操作。</p>
      </section>
    </article>
  );
}
