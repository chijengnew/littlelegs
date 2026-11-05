"""景點細分類型：來源分類（confirmed）＋名稱關鍵字（inferred）。

- 來源分類：全國景點 AttractionClasses、臺北旅遊網與臺南景點的 categories；照來源標記，記為 confirmed。
  範圍太寬的分類（例如「文化類」「遊憩類」「戶外踏青」「在地藝文」）不用。
- 名稱關鍵字：每條規則獨立判斷，可同時屬於多個類型；記為 inferred，證據寫明命中的字樣。
- 都無法判斷時才歸為「其他景點」（由 resolve.merge 處理）。
- 公園類的來源分類同樣要求名稱像公園（PARK_NAME），避免臺北賓館這類地點被歸為公園。
"""

from __future__ import annotations

import re

from .model import Attr, SourceRec
from .sources import PARK_NAME

CATEGORY_TYPES: dict[tuple[str, str], str] = {
    **{
        ("tdx_attractions", k): v
        for k, v in {
            "生態場館類": "nature_center",
            "觀光遊樂業類": "amusement_park",
            "休閒農業類": "farm",
            "溫泉類": "hot_spring",
            "宗教廟宇類": "temple",
            "商圈商店類": "shopping",
            "藝文場館類": "arts_venue",
            "文化資產類": "heritage",
            "原住民文化類": "indigenous",
            "客家文化類": "hakka",
            "水域環境類": "waterfront",
            "體育健身類": "sports",
            "自然風景類": "nature",
            "國家風景區類": "nature",
            "國家自然公園類": "nature",
            "國家公園類": "nature",
            "森林遊樂區類": "nature",
            "平地森林園區類": "nature",
        }.items()
    },
    **{
        ("taipei_attractions", k): v
        for k, v in {
            "藝文館所": "arts_venue",
            "歷史建築": "heritage",
            "主題商街": "shopping",
            "宗教信仰": "temple",
            "單車遊蹤": "bike_path",
            "觀光夜市": "night_market",
            "養生溫泉": "hot_spring",
        }.items()
    },
    **{
        ("tainan_attractions", k): v
        for k, v in {
            "宗教廟宇": "temple",
            "歷史古蹟": "heritage",
            "地方展館": "arts_venue",
            "自然景觀": "nature",
            "生態教育": "nature_center",
            "公園綠地": "park_playground",
            "休閒農漁": "farm",
            "戶外運動": "sports",
            "觀光工廠": "tourism_factory",
            "客家文化": "hakka",
            "原民文化": "indigenous",
            "風景區": "nature",
            "夜市夜遊": "night_market",
            "溫泉度假": "hot_spring",
        }.items()
    },
}

NAME_RULES: list[tuple[str, str, str | None]] = [
    (
        "museum",
        r"博物館|博物院|美術館|科學館|科學教育館|科教館|文物館|陳列館|史料館|史蹟館|資料館|院史|史蹟室|檔案館",
        None,
    ),
    ("parent_child_center", r"親子館|托育資源中心|育兒資源中心", None),
    ("zoo", r"動物園|鳥園|蝴蝶園|昆蟲館|昆蟲園", None),
    ("aquarium", r"水族館|海生館|海洋生物|海洋館", None),
    (
        "amusement_park",
        r"遊樂園|樂園|遊樂世界|遊樂區|九族文化村|小人國|義大世界|六福村|劍湖山|恐龍園區|樂世界|海洋世界|水世界",
        r"森林遊樂區",
    ),
    ("tourism_factory", r"觀光工廠|觀光工場", None),
    (
        "industry_heritage",
        r"糖廠|醬油|油廠|鹽場|鹽山|酒窖|酒廠|釀|製所|製造所|茶廠|鋸木|林場|礦|產業文化|碾米|發電廠|郵局|信用合作社"
        r"|林業|漁村生活館|種苗|工藝之家|窯|陶瓷廠|鹽田|出張所",
        None,
    ),
    (
        "diy_workshop",
        r"工作室|工作坊|DIY|手作|工坊|體驗館|體驗工場|陶藝|陶坊|繡|雕房|畫室|紙傘|木偶雕刻|工房|手創|巧手",
        None,
    ),
    (
        "shop_cafe",
        r"咖啡|[Cc]offee|[Cc]afe|門市|行$|文具|農會|書店|書屋|書局|商行|老店|麵包|餅舖|冰店|茶坊|小舖|雜貨|小築|小柴軒|餐廳|[Ss]hop|魚舖|玩具屋|租車|の店",
        None,
    ),
    ("env_edu", r"環境教育|環教", None),
    ("nature_center", r"自然中心|生態教育|生態館|自然教育中心|保育中心|保育教育|生態展示館|生態園區|試驗所", None),
    ("visitor_center", r"遊客中心|旅遊服務中心|服務中心|旅客中心|借問站", None),
    (
        "farm",
        r"農場|牧場|農園|果園|休閒農業區|茶園|農莊|酒莊|菇|花田|養殖場|漁場|休閒漁業|農業區|田園|農村|乳牛|馬場|園藝"
        r"|養生園區",
        None,
    ),
    ("park_playground", r"公園|遊戲場|綠地|親水|植物園|花園|苗圃|綠園道", r"國家公園|國家自然公園"),
    ("library", r"圖書館|圖書分館", None),
    (
        "arts_venue",
        r"藝術中心|藝文中心|文創|美術村|藝術村|劇場|劇院|戲院|音樂廳|展覽館|展示館|展演|文化館|文化中心|紀念館|藝廊"
        r"|藝術館|藝文館|文學館|故事館|故事屋|藝術園區|藝文空間|文化園區|藝文特區|文化會館|美學館|社教中心|書法館"
        r"|主題館|音樂館|會館|生活館|藝術廣場|藝術空間|發展館|啟蒙館|創生基地|新創|創客|工藝|傳藝|布袋戲|南北管|戲館|影像館"
        r"|電影院|會展中心|藏樂館|文化基地|文學|樂團|展售中心|展示中心|記念館|場館$|館$",
        None,
    ),
    ("night_market", r"夜市", None),
    ("old_street", r"老街(?!溪)", None),
    ("street", r"巷$|巷弄|街$|街巷|大道$|街區|藝術街|彩繪|大街", None),
    (
        "shopping",
        r"商圈|市場|市集|商店街|購物|百貨|商場|[Oo]utlet|商街|花市|特區$|[Mm]all|PLAZA|[Pp]laza|生活.{0,6}店$",
        None,
    ),
    (
        "temple",
        r"宮$|宮[（(]|廟|寺|教堂|天主堂|禮拜堂|講堂|佛堂|齋堂|鸞堂|善堂|祠|佛|禪|道觀|聖母|媽祖|城隍|神社|清真|[^政]府$"
        r"|殿$|聖心堂|福城|岳$|神石",
        None,
    ),
    (
        "heritage",
        r"古蹟|故居|遺址|砲台|炮台|礮臺|城門|古城|官邸|舊址|宿舍|燈塔|眷村|新村|[一二三四五六七八九十]村$|古厝|古宅|大厝"
        r"|洋樓|舊站|碉堡|牌坊|古井|墓|聚落|街屋|書院|紀念碑|鐵橋|古橋|[東西南北]門|故壘|戰史|坑道|據點|營區|圳"
        r"|厝|宅$|塔$|井$|閣$|樓$|亭$|派出所|警備道|老屋|老宅|老建築|石碑|中興莊|樹屋|隧道|山莊|甕牆|塾|陣地|古戰場|舊辦公廳舍|行館",
        None,
    ),
    ("indigenous", r"部落|原住民|原民|祭場|祭典", None),
    ("hakka", r"客家|客庄", None),
    ("beach", r"海灘|沙灘|海水浴場|沙洲", None),
    (
        "waterfront",
        r"碼頭|漁港|港$|港口|水岸|河岸|海堤|海岸|岬|礁|(?<![台臺])灣$|海濱|河濱|水道|運河|渡口|燈塔|浮潛|湧泉",
        None,
    ),
    ("hot_spring", r"溫泉|冷泉|湯屋|湯$", None),
    ("bike_path", r"自行車道|單車道|自行車|腳踏車道|鐵馬道", None),
    ("trail", r"步道|古道|登山|山徑|林道|之道$|走廊|廊道|環線", None),
    (
        "sports",
        r"運動中心|運動場|運動公園|體育館|體育場|溜冰|滑板|游泳|球場|攀岩|滑草|射擊|馬術|飛行傘|高爾夫|划船|衝浪"
        r"|露營|營地|賽車|卡丁|潛水|獨木舟|騎馬",
        None,
    ),
    ("campus", r"大學$|大學[（(]|大學.{0,4}校區|學院$|高中$|國中$|國小$|國小[（(]|小學$|中學$", None),
    ("station", r"車站|火車站|高鐵站|驛站|驛$|鐵道(?!.*餐廳)|車庫|機廠|航空站|機場|轉運站", None),
    ("scenic_ride", r"纜車|台車|蹦蹦車|小火車|鐵道自行車|雙層巴士|觀光列車|遊船|渡輪|搭船", None),
    ("public_art", r"公共藝術|雕像|雕塑|壁畫|裝置藝術|郵筒|標誌|意象|詩牆|詩路|勒石", None),
    ("community", r"社區|生態村|[^文化]村$|里$|庄$", None),
    (
        "landmark",
        r"橋$|大橋|城堡|鐘樓|大樓|塔$|廣場|地標|城$|拱門|牌樓|公路$|閘門|圓環|巨蛋|長城|風力發電",
        r"國家公園",
    ),
    (
        "nature",
        r"山$|山[（(]|峰|嶺|瀑布|湖|潭|溪|峽谷|森林|國家公園|風景區|風景特定區|觀景台|觀景臺|瞭望|草原|秘境|洞|神木|濕地"
        r"|溼地|埤|池$|島|嶼|坪$|台地|地質|奇岩|海蝕|花海|櫻花|梅園|竹林|吊橋|天空|日出|夕陽|觀星|雲海|遊憩區|休憩區"
        r"|休息區|蝶|幽谷|翠谷|化石|石滬|老樹|樟樹|夫妻樹|自然紀念物|賞鷹|賞鳥|賞櫻|追日|平台$|沙丘|地景|風口|谷$|林$|樹木園|竹棚|山林"
        r"|獼猴|海底|水庫|保護區|埡口|紅樹林|樹王|之樹|海螺|勒石群",
        None,
    ),
]
_NAME_RULES = [(t, re.compile(rx), re.compile(ex) if ex else None) for t, rx, ex in NAME_RULES]


def category_types(rec: SourceRec) -> dict[str, Attr]:
    """來源分類對應的類型（confirmed）。"""
    out: dict[str, Attr] = {}
    cats = rec.display.get("attraction_classes") or rec.display.get("categories") or []
    for cat in cats:
        t = CATEGORY_TYPES.get((rec.dataset_key, cat))
        if t is None or t in out:
            continue
        if t == "park_playground" and not PARK_NAME.search(rec.name):
            continue
        out[t] = Attr(True, "confirmed", f"來源分類「{cat}」")
    return out


def name_types(name: str) -> dict[str, Attr]:
    """名稱關鍵字推定的類型（inferred）。"""
    out: dict[str, Attr] = {}
    for t, rx, ex in _NAME_RULES:
        if t in out or (ex and ex.search(name)):
            continue
        m = rx.search(name)
        if m:
            out[t] = Attr(True, "inferred", f"名稱含「{m.group(0).rstrip('（(')}」推定")
    return out
