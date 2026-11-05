import { getTranslations } from "next-intl/server";
import ui from "@/components/ui.module.css";
import s from "../legal.module.css";

export default async function TermsPage() {
  const t = await getTranslations();
  return (
    <article className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{t("app.terms")}</h1>
        <p>行程依政府開放資料、Google 地點／路線資訊與專案估計值計算，僅供規劃參考；車程為不含即時路況的估計，營業時間、停車、餐飲與現場狀況請出發前自行確認。</p>
        <p>景點資料來源與授權列於各地點詳情頁。地圖與地點建議內容依 Google Maps Platform 條款顯示。</p>
        <p>
          會員地圖由 Google 地圖提供；使用時須遵守{" "}
          <a href="https://maps.google.com/help/terms_maps/" target="_blank" rel="noopener noreferrer">Google 地圖／Google 地球附加服務條款</a>
          ，Google 依{" "}
          <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google 隱私權政策</a>
          處理相關資料。
        </p>
      </section>
    </article>
  );
}
