import { getTranslations } from "next-intl/server";
import ui from "@/components/ui.module.css";
import { phrased } from "@/lib/phrases";
import s from "../legal.module.css";

const OPERATOR = "CHI";
const CONTACT_EMAIL = "chiiifortest@gmail.com";

const keep = (c: React.ReactNode) => <span className={s.keep}>{c}</span>;

export default async function PrivacyPage() {
  const t = await getTranslations();
  const mail = <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>;
  return phrased(
    <article className={s.wrap}>
      <section className={ui.card}>
        <h1 className={s.title}>{t("app.privacy")}</h1>
        <div className={s.summary}>
          <h2>重點摘要</h2>
          <ul>
            <li>我們只用孩子的年齡、起訖位置和行程條件來排行程，不蒐集孩子的{keep("姓名或生日。")}</li>
            <li>訪客的條件不會存在我們的伺服器；會員的歷史與收藏會保存至{keep("您自己刪除。")}</li>
            <li>計算車程、天氣和顯示地圖時，部分位置會{keep("傳給 Google。")}</li>
          </ul>
        </div>
        <h2>誰蒐集您的資料</h2>
        <p>
          LittleLegs 由 {OPERATOR} 經營。個資相關問題請寫信到 {mail}。
        </p>
        <h2>我們蒐集哪些資料</h2>
        <ul>
          <li>行程條件：孩子年齡、出遊日期與時間、午睡與用餐時段、雨天與偏好設定、選擇的景點與{keep("停留時間。")}</li>
          <li>位置：起點與終點；選擇{keep("「目前位置」時")}，包含{keep("裝置座標。")}</li>
          <li>會員帳號：登入信箱與{keep("帳號識別碼。")}</li>
          <li>意見回饋：見下方{keep("「意見回饋」。")}</li>
        </ul>
        <p>我們不蒐集孩子的{keep("姓名或生日。")}</p>
        <h2>為什麼蒐集、怎麼使用</h2>
        <ul>
          <li>推薦候選景點、排出當日行程，並檢查{keep("營業時間與車程。")}</li>
          <li>會員：保存查詢歷史與收藏，方便日後查看或{keep("重新規劃。")}</li>
        </ul>
        <h2>存在哪裡、存多久</h2>
        <ul>
          <li>訪客：條件存在於您的瀏覽器，用於當次規劃；伺服器計算完{keep("就不保存。")}</li>
          <li>會員：查詢歷史與收藏保存到您刪除該筆或{keep("刪除帳號。")}</li>
          <li>
            出遊準備清單：勾選和自訂項目只存在於您的瀏覽器，不會傳到伺服器。訪客的清單保留到瀏覽流程結束；會員的清單依帳號和行程分開保存，登出、切換帳號、刪除帳號或刪除該筆{keep("紀錄時清除。")}
          </li>
          <li>
            備份：資料刪除後，可能仍留在資料庫備份中最多 {keep("30 天")}，之後隨備份清除。為了確保刪除確實完成，我們會另外保留不含個人內容的刪除處理紀錄{keep("至少 90 天。")}
          </li>
        </ul>
        <h2>意見回饋</h2>
        <ul>
          <li>
            您主動送出回饋時，我們保存回饋類型、滿意度、內容、聯絡信箱和來源頁面類型；回報景點資料錯誤時，另外保存該景點的{keep("內部編號。")}
          </li>
          <li>
            回饋不會連結會員帳號，也不記錄完整網址或行程內容。但您填的內容和信箱仍可能識別到您，請不要填入孩子的姓名等{keep("不必要的資料。")}
          </li>
          <li>回饋保存 {keep("12 個月")}後刪除，刪除後可能仍留在備份中，直到備份依{keep("保留期間被覆蓋。")}</li>
          <li>
            刪除帳號不會自動刪除回饋。需要查詢或刪除時，請寫信到 {mail}，並附上送出時用的信箱或{keep("回饋內容。")}
          </li>
        </ul>
        <h2>不提供會怎樣</h2>
        <ul>
          <li>沒有填孩子年齡、出遊日期與時間或起點，就無法{keep("查詢行程。")}</li>
          <li>不允許裝置定位也能使用，改成輸入{keep("地點就好。")}</li>
          <li>不註冊會員也能規劃，只是無法保存{keep("歷史與收藏。")}</li>
        </ul>
        <h2>您的權利</h2>
        <p>
          依{keep("個人資料保護法")}，您可以查詢或請求閱覽、請求補充或更正、請求停止蒐集、處理或利用，以及請求刪除您的{keep("個人資料。")}
        </p>
        <ul>
          <li>刪除帳號、單筆歷史或收藏：可以在會員頁{keep("直接操作。")}</li>
          <li>其他請求：請寫信到 {mail}，我們會在法定{keep("期間內回覆。")}</li>
        </ul>
      </section>
    </article>,
    s.keep,
  );
}
