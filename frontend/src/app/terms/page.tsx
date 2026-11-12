import { getTranslations } from "next-intl/server";
import ui from "@/components/ui.module.css";
import { phrased } from "@/lib/phrases";
import s from "../legal.module.css";

const OPERATOR = "CHI";
const CONTACT_EMAIL = "chiiifortest@gmail.com";

const keep = (c: React.ReactNode) => <span className={s.keep}>{c}</span>;

function External({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

export default async function TermsPage() {
  const t = await getTranslations();
  return phrased(
    <article className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{t("app.terms")}</h1>
        <h2>服務說明</h2>
        <p>
          LittleLegs 由 {OPERATOR} 經營，協助家長規劃台灣的親子單日自駕行程：依您填的條件推薦景點，並把 {keep("1–5 個景點")}排成{keep("一天的行程。")}
        </p>
        <h2>行程結果怎麼看</h2>
        <ul>
          <li>行程依政府開放資料、Google 的地點、路線與天氣資訊，以及本站估計值計算，僅供{keep("規劃參考。")}</li>
          <li>車程是不含即時路況的開車估計時間；停留時間和適合年齡是{keep("本站估計。")}</li>
          <li>出遊日期在 {keep("7 天以後")}，特殊營業時間（例如臨時休館）{keep("無法確認。")}</li>
          <li>停車、餐飲、步行路線和現場狀況，請出發前自行確認，並以{keep("現場公告為準。")}</li>
          <li>
            導航連結開啟的實際路線和時間可能與本站估算不同。開車時請{keep("專心駕駛，")}
            {keep("不要操作手機。")}
          </li>
        </ul>
        <h2>資料來源</h2>
        <p>
          景點資料的來源與授權由 {keep("Government Open Data")} 提供。地點建議、地圖與導航由 Google 提供，依{" "}
          {keep("Google Maps Platform")} 的條款顯示。如發現資料有誤，歡迎透過{keep("「意見回饋」")}
          {keep("告訴我們。")}
        </p>
        <h2>Google 服務</h2>
        <p>
          本服務使用 Google 的地點建議、地圖、路線與天氣功能。使用這些功能時，您也須遵守{" "}
          <External href="https://maps.google.com/help/terms_maps/">
            {keep("Google 地圖／")}
            {keep("Google 地球附加服務條款")}
          </External>
          ，Google 會依 <External href="https://policies.google.com/privacy">{keep("Google 隱私權政策")}</External>
          {keep("處理相關資料。")}
        </p>
        <h2>會員帳號</h2>
        <ul>
          <li>請妥善保管您的登入資訊，不要和他人{keep("共用帳號。")}</li>
          <li>您可以隨時在會員頁刪除帳號，刪除後{keep("無法復原。")}</li>
        </ul>
        <h2>請不要這樣使用</h2>
        <ul>
          <li>用程式自動或大量查詢，或試圖規避{keep("用量限制。")}</li>
          <li>干擾、攻擊或破壞{keep("本服務的運作。")}</li>
          <li>複製、轉售或大量擷取本服務顯示的 {keep("Google 內容。")}</li>
        </ul>
        <h2>服務變更</h2>
        <p>
          為了控制成本與維持服務品質，部分功能可能因用量上限暫時無法使用。我們也可能調整、暫停或終止部分或全部服務，並盡量事先在{keep("網站上公告。")}
        </p>
        <h2>責任範圍</h2>
        <p>
          我們會盡力維持資料正確和服務穩定，但無法保證所有資料即時、完整。在法律允許的範圍內，因資料不準確或現場狀況改變造成的損失，由{keep("使用者")}
          {keep("自行判斷與承擔。")}
        </p>
        <h2>聯絡我們</h2>
        <p>
          對本條款有疑問，請寫信到 <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>。
        </p>
      </section>
    </article>,
    s.keep,
  );
}
