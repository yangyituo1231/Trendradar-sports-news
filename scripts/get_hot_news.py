import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from collections import Counter, defaultdict

# =========================
# 0. 基础配置
# =========================
MAX_ITEMS = 160
RSS_PER_QUERY_LIMIT = 10
RECENT_DAYS = 7

OUT_DIR = Path("output/weekly")
OUT_FILE = OUT_DIR / "weekly_news.json"

NOW = datetime.now()
NOW_UTC = datetime.now(timezone.utc)
MONTH = NOW.month


# =========================
# 1. 经营日历
# =========================
def current_campaign():
    if MONTH == 1:
        return "元旦年货"
    if MONTH == 2:
        return "春节开春"
    if MONTH == 3:
        return "38大促春季上新"
    if MONTH == 4:
        return "清明春游"
    if MONTH == 5:
        return "五一六一618预热"
    if MONTH == 6:
        return "六一618端午"
    if MONTH in [7, 8]:
        return "暑期消费"
    if MONTH == 9:
        return "开学季99大促"
    if MONTH == 10:
        return "国庆双11预热"
    if MONTH == 11:
        return "双11"
    if MONTH == 12:
        return "双12年货预热"
    return "日常经营"


CAMPAIGN = current_campaign()


# =========================
# 2. 查询词
# =========================
A_LEVEL_QUERIES = [
    "运动品牌 消费趋势 零售",
    "运动户外 消费趋势",
    "童装 儿童运动 消费趋势",
    "运动鞋服 行业趋势",
    "运动品牌 618 战报",
    "抖音电商 运动户外 618",
    "天猫 运动户外 618",
    "京东 运动户外 618",
    "小红书 运动户外 种草",
    "年轻人 运动消费",
    "亲子消费 儿童运动",
    "暑期 亲子户外 消费",
    "防晒衣 凉感 速干 消费趋势",
    "商场 客流 消费 运动品牌",
    "奥莱 折扣 运动品牌",
    "体育消费 新趋势",
    "儿童消费 市场 趋势",
]

B_LEVEL_QUERIES = [
    "Nike 运动品牌 中国 消费",
    "耐克 中国 运动消费",
    "Adidas 阿迪达斯 中国 运动",
    "安踏 儿童 运动",
    "安踏儿童 童装",
    "李宁 童装 儿童",
    "李宁YOUNG 儿童",
    "特步儿童 运动",
    "361度 儿童 运动",
    "361儿童 新品",
    "FILA KIDS 儿童",
    "巴拉巴拉 运动童装",
    "On 昂跑 中国 消费",
    "HOKA 跑步 消费",
    "亚瑟士 跑步 消费",
    "Salomon 萨洛蒙 户外",
    "lululemon 中国 消费",
    "安踏 李宁 耐克 阿迪 运动品牌",
]

C_LEVEL_QUERIES = [
    "AI 电商 运动品牌",
    "AI 营销 618",
    "文旅 亲子 户外 消费",
    "城市骑行 运动消费",
    "露营 亲子 户外 消费",
    "防晒 消费 高温",
    "凉感 面料 运动",
    "户外生活方式 中国消费",
    "商圈 活动 亲子 运动",
    "情绪消费 年轻人 运动",
]

HOT_PRODUCT_QUERIES = [
    "运动品牌 新品 跑鞋",
    "儿童运动鞋 新品",
    "儿童跑鞋 新品",
    "儿童篮球鞋 新品",
    "安踏儿童 新品",
    "Nike Kids 新品",
    "Adidas Kids 新品",
    "FILA KIDS 新品",
    "李宁YOUNG 新品",
    "特步儿童 新品",
    "361儿童 新品",
    "防晒衣 新品 运动品牌",
    "凉感 速干 新品 童装",
    "运动户外 尖货 新品",
    "儿童防晒服 新品",
]

KEYWORDS = list(dict.fromkeys(
    A_LEVEL_QUERIES
    + B_LEVEL_QUERIES
    + C_LEVEL_QUERIES
    + HOT_PRODUCT_QUERIES
))


# =========================
# 3. 词库
# =========================
BRAND_WORDS = [
    "Nike", "耐克", "Adidas", "阿迪达斯", "Puma", "彪马",
    "安踏", "安踏儿童", "FILA", "FILA KIDS", "李宁", "李宁YOUNG",
    "特步", "特步儿童", "361", "361度", "361儿童",
    "巴拉巴拉", "On", "昂跑", "HOKA", "亚瑟士", "ASICS",
    "Salomon", "萨洛蒙", "lululemon", "始祖鸟", "北面",
    "New Balance", "泰兰尼斯",
]

CORE_BRANDS = [
    "安踏儿童", "安踏", "Nike", "耐克", "Adidas", "阿迪达斯",
    "李宁", "李宁YOUNG", "特步", "特步儿童", "361", "361度",
    "361儿童", "FILA", "FILA KIDS", "巴拉巴拉", "On", "昂跑",
    "HOKA", "亚瑟士", "ASICS", "lululemon", "New Balance",
]

A_WORDS = [
    "消费", "趋势", "行业", "社零", "客流", "增长", "下滑",
    "618", "双11", "暑期", "开学", "防晒", "凉感", "速干",
    "户外", "运动户外", "亲子", "童装", "儿童运动",
    "商场", "商圈", "奥莱", "折扣", "平台", "抖音", "天猫", "京东",
    "报告", "洞察", "数据", "白皮书", "市场", "品类", "渠道",
]

B_WORDS = [
    "发布", "新品", "联名", "代言", "签约", "合作", "门店",
    "旗舰店", "战略", "实验室", "开业", "增长", "榜单",
    "首店", "拆分", "收购", "可持续", "科技", "研发",
]

C_WORDS = [
    "AI", "人工智能", "大模型", "机器人",
    "文旅", "城市骑行", "露营", "活动", "生活方式",
    "防晒", "凉感", "高温", "情绪消费", "松弛感",
]

HOT_PRODUCT_WORDS = [
    "新品", "尖货", "跑鞋", "童鞋", "防晒衣", "防晒服",
    "凉感", "速干", "短袖", "短裤", "运动鞋", "户外鞋",
    "联名", "首发", "上市", "发布", "鞋款", "系列",
    "篮球鞋", "训练鞋", "足弓", "缓震", "科技",
]

HARD_NEGATIVE_KEYWORDS = [
    "彩票", "博彩", "赌球", "下注", "365BET", "官网入口",
    "电竞比赛", "游戏赛事", "成人用品",
]

SPORTS_EVENT_NEGATIVE = [
    "中超", "英超", "欧冠", "NBA", "CBA", "世界杯", "世锦赛",
    "冠军", "夺冠", "决赛", "半决赛", "比分", "赛程", "联赛",
    "主教练", "球员", "转会", "国家队", "运动员",
]

FINANCE_NEGATIVE = [
    "央行", "利率", "财政", "货币政策", "地产", "楼市",
    "基金", "证券", "港股", "A股", "美股", "IPO", "龙虎榜",
    "涨停", "跌停", "目标价", "评级", "研报",
]

LOW_QUALITY_SOURCE_WORDS = [
    "雪球", "360娱乐", "搜狐号", "百家号", "财富号", "格隆汇",
]

AD_TITLE_WORDS = [
    "凑单", "拍3件", "券后", "包邮", "get@", "大冤种",
    "快来", "值得买", "入口", "查看指南", "排行榜", "推荐榜",
    "哪款最适合", "买哪个牌子好", "横向测评", "避坑指南",
    "省钱快报", "$", "折起",
]

SOURCE_PREFERENCE = [
    "界面新闻", "Jiemian", "36氪", "36 Kr", "赢商网", "联商网",
    "亿邦动力", "电商报", "中国商报", "北京商报", "第一财经",
    "新华网", "澎湃新闻", "thepaper.cn", "每日经济新闻",
    "南方都市报", "腾讯新闻", "新京报", "中国经济网", "财联社",
    "虎嗅", "品牌星球", "晚点", "钛媒体", "国家统计局",
    "央视新闻", "央视网", "人民网", "美通社",
]


# =========================
# 4. 工具函数
# =========================
def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r" - .*?$", "", title)
    title = re.sub(r"_.*?$", "", title)
    title = re.sub(r"\s*\|\s*.*?$", "", title)
    title = title.replace("（图）", "").replace("(图)", "")
    return title.strip()


def has_any(text: str, words: list) -> bool:
    return any(w in text for w in words)


def parse_pub_datetime(value: str):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def item_age_hours(item: dict) -> float:
    dt = parse_pub_datetime(item.get("published_at", ""))
    if not dt:
        return 999999
    return (NOW_UTC - dt).total_seconds() / 3600


def is_recent_item(item: dict) -> bool:
    h = item_age_hours(item)
    return 0 <= h <= RECENT_DAYS * 24


def freshness_score(item: dict) -> int:
    h = item_age_hours(item)
    if h <= 24:
        return 35
    if h <= 48:
        return 28
    if h <= 72:
        return 20
    if h <= 120:
        return 8
    if h <= 168:
        return 0
    return -999


def compact_key(title: str) -> str:
    text = normalize_title(title).lower()
    text = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|]+", "", text)
    return text[:52]


def detect_brand(title: str) -> str:
    for brand in CORE_BRANDS:
        if brand in title:
            if brand in ["Nike", "耐克"]:
                return "Nike"
            if brand in ["Adidas", "阿迪达斯"]:
                return "Adidas"
            if brand in ["安踏儿童", "安踏"]:
                return "安踏"
            if brand in ["李宁YOUNG", "李宁"]:
                return "李宁"
            if brand in ["特步儿童", "特步"]:
                return "特步"
            if brand in ["361", "361度", "361儿童"]:
                return "361"
            if brand in ["FILA", "FILA KIDS"]:
                return "FILA"
            if brand in ["On", "昂跑"]:
                return "On昂跑"
            if brand in ["ASICS", "亚瑟士"]:
                return "亚瑟士"
            return brand
    return "行业"


def is_business_exempt(title: str) -> bool:
    return has_any(title, [
        "运动品牌", "童装", "儿童", "鞋服", "消费", "零售",
        "商场", "商圈", "门店", "户外", "跑鞋", "防晒",
        "凉感", "品牌", "签约", "代言", "联名", "新品",
        "运动户外", "体育消费", "篮球鞋", "儿童鞋",
    ])


def is_bad_item(title: str, source: str) -> bool:
    if not title or len(title) < 8:
        return True

    if has_any(title, HARD_NEGATIVE_KEYWORDS):
        return True

    if has_any(title, AD_TITLE_WORDS):
        return True

    if has_any(source, LOW_QUALITY_SOURCE_WORDS):
        return True

    if has_any(title, SPORTS_EVENT_NEGATIVE) and not is_business_exempt(title):
        return True

    if has_any(title, FINANCE_NEGATIVE) and not is_business_exempt(title):
        return True

    if title.count("#") >= 2:
        return True

    if len(title) > 72 and has_any(title, ["#","✨","同款","超值好货"]):
        return True

    return False


def topic_key(title: str) -> str:
    title = normalize_title(title)

    groups = {
        "平台大促": ["618", "双11", "大促", "抖音", "天猫", "京东", "直播"],
        "防晒凉感": ["防晒", "凉感", "速干", "高温", "防晒衣", "防晒服"],
        "户外运动": ["户外", "跑步", "跑鞋", "骑行", "露营", "徒步", "冲锋衣"],
        "童装儿童": ["童装", "儿童", "亲子", "校园", "童鞋", "青少年", "足弓"],
        "商圈客流": ["商场", "商圈", "门店", "客流", "会员", "奥莱", "购物中心"],
        "行业趋势": ["趋势", "报告", "洞察", "消费", "行业", "市场", "社零"],
        "品牌竞争": CORE_BRANDS,
        "AI科技": ["AI", "人工智能", "机器人", "大模型", "科技"],
    }

    for key, words in groups.items():
        if has_any(title, words):
            return key + "_" + compact_key(title)[:24]

    return "其他_" + compact_key(title)[:30]


# =========================
# 5. RSS抓取
# =========================
def fetch_google_news_rss(keyword: str):
    query = urllib.parse.quote(f"{keyword} when:{RECENT_DAYS}d")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    items = []

    for idx, node in enumerate(root.findall(".//item")):
        if idx >= RSS_PER_QUERY_LIMIT:
            break

        title = normalize_title(node.findtext("title"))
        link = clean_text(node.findtext("link"))
        pub_date = clean_text(node.findtext("pubDate"))

        source = "Google News"
        source_node = node.find("source")
        if source_node is not None and source_node.text:
            source = clean_text(source_node.text)

        row = {
            "title": title,
            "source": source,
            "url": link,
            "published_at": pub_date,
            "keyword": keyword,
        }

        if not is_recent_item(row):
            continue

        if is_bad_item(title, source):
            continue

        items.append(row)

    return items


# =========================
# 6. 分级评分
# =========================
def base_score(item: dict) -> int:
    title = item.get("title", "")
    source = item.get("source", "")

    score = freshness_score(item)

    for s in SOURCE_PREFERENCE:
        if s in source:
            score += 6

    if has_any(title, BRAND_WORDS):
        score += 10

    if has_any(title, ["618", "双11", "暑期", "开学", "防晒", "凉感", "速干"]):
        score += 8

    if has_any(title, ["消费", "趋势", "增长", "客流", "商场", "门店", "零售", "报告", "洞察"]):
        score += 10

    return score


def score_a(item: dict) -> int:
    title = item.get("title", "")
    score = base_score(item)

    score += sum(7 for w in A_WORDS if w in title)

    if has_any(title, ["趋势", "增长", "消费", "客流", "行业", "平台", "大促", "报告", "洞察", "数据"]):
        score += 32

    if has_any(title, ["财报", "营收", "净利润", "市值", "股价"]):
        score -= 18

    if has_any(title, ["明星", "代言", "签约", "联名"]):
        score -= 12

    if has_any(title, ["排行榜", "推荐", "测评"]):
        score -= 35

    return score


def score_b(item: dict) -> int:
    title = item.get("title", "")
    score = base_score(item)

    score += sum(8 for w in B_WORDS if w in title)

    if has_any(title, BRAND_WORDS):
        score += 32

    if has_any(title, ["新品", "联名", "代言", "签约", "旗舰店", "实验室", "战略合作", "发布", "开业", "拆分"]):
        score += 26

    if not has_any(title, BRAND_WORDS):
        score -= 18

    if has_any(title, ["排行榜", "推荐榜", "测评"]):
        score -= 35

    return score


def score_c(item: dict) -> int:
    title = item.get("title", "")
    score = base_score(item)

    score += sum(7 for w in C_WORDS if w in title)

    if has_any(title, ["AI", "文旅", "露营", "骑行", "智能", "生活方式", "情绪消费"]):
        score += 22

    if has_any(title, ["排行榜", "推荐榜", "测评"]):
        score -= 40

    return score


def score_hot_product(item: dict) -> int:
    title = item.get("title", "")
    score = base_score(item)

    score += sum(10 for w in HOT_PRODUCT_WORDS if w in title)

    if has_any(title, BRAND_WORDS):
        score += 18

    if has_any(title, ["新品", "发布", "首发", "上市", "联名", "系列", "实验室", "科技"]):
        score += 30

    if has_any(title, ["排行榜", "推荐榜", "测评", "哪款", "凑单", "包邮"]):
        score -= 80

    return score


def classify_item(item: dict) -> dict:
    scores = {
        "A": score_a(item),
        "B": score_b(item),
        "C": score_c(item),
    }

    level = max(scores, key=scores.get)
    item["level"] = level
    item["level_score"] = scores[level]
    item["age_hours"] = round(item_age_hours(item), 1)
    item["compact_key"] = compact_key(item.get("title", ""))
    item["topic_key"] = topic_key(item.get("title", ""))
    item["brand"] = detect_brand(item.get("title", ""))

    return item


# =========================
# 7. 去重 / 限额
# =========================
def dedupe(items):
    best = {}

    for item in items:
        title = normalize_title(item.get("title", ""))
        if not title:
            continue

        item["title"] = title
        item = classify_item(item)

        if item["level_score"] <= 0:
            continue

        key = item["topic_key"]
        old = best.get(key)

        if old is None:
            best[key] = item
        else:
            old_score = old.get("level_score", 0)
            new_score = item.get("level_score", 0)
            old_age = old.get("age_hours", 999999)
            new_age = item.get("age_hours", 999999)

            if new_score > old_score or (new_score == old_score and new_age < old_age):
                best[key] = item

    return list(best.values())


def apply_brand_cap(rows, brand_cap=2):
    result = []
    counter = defaultdict(int)

    for item in rows:
        brand = item.get("brand", "行业")

        if brand != "行业" and counter[brand] >= brand_cap:
            continue

        result.append(item)
        counter[brand] += 1

    return result


def pick_by_level(items, level, limit):
    rows = [x for x in items if x.get("level") == level]

    rows = sorted(
        rows,
        key=lambda x: (x.get("level_score", 0), -x.get("age_hours", 999999)),
        reverse=True,
    )

    if level == "B":
        rows = apply_brand_cap(rows, brand_cap=2)

    return rows[:limit]


def pick_hot_products(items, limit=5):
    rows = []

    for item in items:
        title = item.get("title", "")

        if not has_any(title, HOT_PRODUCT_WORDS):
            continue

        if has_any(title, ["排行榜", "推荐榜", "测评", "哪款", "凑单", "包邮"]):
            continue

        row = dict(item)
        row["hot_product_score"] = score_hot_product(row)

        if row["hot_product_score"] <= 0:
            continue

        rows.append(row)

    rows = sorted(
        rows,
        key=lambda x: (x.get("hot_product_score", 0), -x.get("age_hours", 999999)),
        reverse=True,
    )

    return apply_brand_cap(rows, brand_cap=2)[:limit]


def build_keywords(items):
    text = " ".join([x.get("title", "") for x in items[:100]])

    keyword_pool = [
        "618", "防晒衣", "防晒服", "凉感", "速干", "运动户外",
        "儿童运动", "亲子消费", "AI营销", "平台大促", "品牌竞争",
        "商场客流", "新品发布", "联名合作", "户外生活", "暑期消费",
        "小红书种草", "抖音电商", "奥莱折扣", "运动童装", "跑鞋",
        "儿童鞋", "篮球鞋", "足弓科技", "可持续", "实验室",
    ]

    words = []

    for w in keyword_pool:
        if w in text and w not in words:
            words.append(w)

    if len(words) < 12:
        counter = Counter()
        for title in [x.get("title", "") for x in items]:
            for w in keyword_pool:
                if w in title:
                    counter[w] += 1

        for w, _ in counter.most_common():
            if w not in words:
                words.append(w)

    return words[:18]


def build_weekly_view(items):
    a_items = pick_by_level(items, "A", 8)
    b_items = pick_by_level(items, "B", 8)
    c_items = pick_by_level(items, "C", 8)
    hot_products = pick_hot_products(items, 5)

    all_selected = a_items + b_items + c_items + hot_products

    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "campaign": CAMPAIGN,
        "recent_days": RECENT_DAYS,
        "summary": {
            "total": len(items),
            "a_count": len(a_items),
            "b_count": len(b_items),
            "c_count": len(c_items),
            "hot_product_count": len(hot_products),
        },
        "levels": {
            "A": {
                "name": "A级｜核心经营趋势",
                "weight": "60%",
                "items": a_items,
            },
            "B": {
                "name": "B级｜品牌案例",
                "weight": "25%",
                "items": b_items,
            },
            "C": {
                "name": "C级｜热点补充",
                "weight": "10%",
                "items": c_items,
            },
        },
        "hot_products": hot_products,
        "keywords": build_keywords(all_selected),
        "items": items[:MAX_ITEMS],
    }


# =========================
# 8. 主程序
# =========================
def main():
    all_items = []

    print(f"Weekly campaign: {CAMPAIGN}")
    print(f"Total keywords: {len(KEYWORDS)}")
    print(f"Recent window: last {RECENT_DAYS} days")

    for idx, keyword in enumerate(KEYWORDS, start=1):
        try:
            rows = fetch_google_news_rss(keyword)
            all_items.extend(rows)
            print(f"[{idx}/{len(KEYWORDS)}] fetched {len(rows)} items: {keyword}")
            time.sleep(0.35)
        except Exception as e:
            print(f"Fetch failed: {keyword} | {e}")

    print(f"Raw items: {len(all_items)}")

    items = dedupe(all_items)

    items = sorted(
        items,
        key=lambda x: (x.get("level_score", 0), -x.get("age_hours", 999999)),
        reverse=True,
    )

    print(f"After dedupe/classify: {len(items)}")

    payload = build_weekly_view(items)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved weekly news to {OUT_FILE}")

    print("\nA Level:")
    for i, x in enumerate(payload["levels"]["A"]["items"], start=1):
        print(f"A{i}. [{x.get('level_score')}] {x.get('title')} | {x.get('source')}")

    print("\nB Level:")
    for i, x in enumerate(payload["levels"]["B"]["items"], start=1):
        print(f"B{i}. [{x.get('level_score')}] [{x.get('brand')}] {x.get('title')} | {x.get('source')}")

    print("\nC Level:")
    for i, x in enumerate(payload["levels"]["C"]["items"], start=1):
        print(f"C{i}. [{x.get('level_score')}] {x.get('title')} | {x.get('source')}")

    print("\nHot Products:")
    for i, x in enumerate(payload["hot_products"], start=1):
        print(f"P{i}. [{x.get('hot_product_score')}] [{x.get('brand')}] {x.get('title')} | {x.get('source')}")


if __name__ == "__main__":
    main()
