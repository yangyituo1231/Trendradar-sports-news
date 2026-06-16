from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import requests
import json
import re
import time
from collections import Counter

# =========================================================
# 0. 基础配置
# =========================================================
OUTPUT_DIR = Path("output/products")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")
NOW_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
NOW_UTC = datetime.now(timezone.utc)

# 商品周报建议看近8天，既能抓新品，也避免一年多以前的旧内容反复进榜
RECENT_DAYS = 8
CUTOFF_DATE = NOW_UTC - timedelta(days=RECENT_DAYS)

MAX_QUERIES = 120
RSS_PER_QUERY = 8
MAX_SIGNALS = 100

# =========================================================
# 1. 品牌与商品词库
# =========================================================
KIDS_BRANDS = [
    "361儿童", "361°儿童", "361度儿童", "361°KIDS", "361 Kids",
    "安踏儿童", "李宁YOUNG", "特步儿童", "FILA Kids", "FILA KIDS",
    "Nike Kids", "Adidas Kids", "Puma Kids", "New Balance Kids", "Skechers Kids",
    "Asics Kids", "Jordan Kids", "巴拉巴拉", "Balabala", "Mini Peace",
    "modytiger", "moodytiger", "MQD童装", "安奈儿", "Annil", "小猪班纳",
    "pawin paw", "马骑顿", "M.Latin Kids", "jnby by JNBY", "戴维贝拉",
    "davebella", "英氏", "YeeHoO", "暇步士童装", "Hush Puppies Kids", "泰兰尼斯"
]

ADULT_BRANDS = [
    "安踏", "李宁", "361°", "361度", "特步", "鸿星尔克", "匹克", "乔丹体育",
    "FILA", "Nike", "Adidas", "Puma", "New Balance", "Asics", "ASICS",
    "Skechers", "Under Armour", "Jordan", "Converse", "Vans", "Crocs",
    "On", "ON Running", "Hoka", "HOKA", "Salomon", "lululemon",
    "Arc'teryx", "始祖鸟", "The North Face", "北面", "迪桑特", "Descente",
    "可隆", "KOLON SPORT", "凯乐石", "KAILAS", "伯希和", "PELLIOT", "蕉下", "Beneunder"
]

BRANDS = list(dict.fromkeys(KIDS_BRANDS + ADULT_BRANDS))

EVENT_KEYWORDS = [
    "618", "双11", "双十一", "双12", "双十二", "99大促", "年货节",
    "38节", "六一", "儿童节", "开学季", "暑期", "寒假", "春节", "国庆",
    "中秋", "会员日", "直播大促", "抖音大促", "天猫大促", "京东大促", "唯品会大促"
]

PRODUCT_WORDS = [
    # 儿童/鞋
    "儿童运动鞋", "儿童跑鞋", "儿童篮球鞋", "儿童足球鞋", "青少年跑鞋", "校园运动鞋",
    "跳绳鞋", "训练鞋", "开学鞋", "童鞋", "大童鞋", "足弓", "足弓支撑",
    # 服装
    "儿童防晒衣", "防晒衣", "凉感T恤", "速干T恤", "短袖", "短裤", "运动套装",
    "卫衣", "长裤", "轻外套", "棒球服", "冲锋衣", "软壳外套", "羽绒服", "棉服",
    "抓绒衣", "防风外套", "防水外套", "防晒帽", "遮阳帽",
    # 成人运动参考
    "跑鞋", "碳板跑鞋", "厚底跑鞋", "缓震跑鞋", "竞速跑鞋", "慢跑鞋", "户外鞋",
    "溯溪鞋", "运动凉鞋", "恢复拖鞋", "洞洞鞋", "瑜伽服", "运动内衣",
    # 科技/功能
    "碳板", "全掌碳板", "半掌碳板", "厚底", "缓震", "回弹", "超临界发泡",
    "氮科技", "EVA中底", "TPU支撑", "BOA旋钮", "防滑大底", "耐磨大底",
    "防晒", "凉感", "速干", "冰感", "防水", "防风", "保暖", "加绒", "功能面料",
    # 场景
    "篮球", "足球", "跑步", "马拉松", "网球", "羽毛球", "校园体育", "中考体育",
    "亲子运动", "轻户外", "户外徒步", "露营", "骑行", "滑雪", "训练", "城市轻户外",
    # 商品事件
    "新品", "上新", "热卖", "爆款", "发布", "首发", "上市", "联名", "系列"
]

CORE_PRODUCT_WORDS = [
    "鞋", "服", "童装", "童鞋", "跑鞋", "篮球鞋", "足球鞋", "运动鞋", "防晒衣",
    "T恤", "冲锋衣", "羽绒服", "棉服", "卫衣", "短裤", "长裤", "外套",
    "帽", "书包", "拖鞋", "凉鞋", "户外", "跑步", "篮球", "足球", "新品",
    "上新", "发布", "首发", "联名", "热卖", "爆款", "儿童", "青少年", "足弓"
]

PRODUCT_KEYWORDS = list(dict.fromkeys(PRODUCT_WORDS + EVENT_KEYWORDS))

# =========================================================
# 2. 查询词
# =========================================================
FOCUS_QUERIES = [
    "儿童运动鞋 新品", "儿童跑鞋 新品", "儿童篮球鞋 校园体育", "儿童防晒衣 热卖",
    "儿童凉感T恤 热卖", "儿童冲锋衣 防水", "儿童羽绒服 保暖", "童装 运动 新品",
    "青少年 足弓 跑鞋", "青少年 成人化 运动鞋", "碳板跑鞋 新品", "厚底跑鞋 热卖",
    "缓震跑鞋 新品", "户外鞋 热卖", "防晒衣 运动品牌", "轻户外 运动品牌 新品",
    "恢复拖鞋 运动品牌", "618 运动户外 热卖", "618 儿童运动鞋", "618 防晒衣",
    "开学季 儿童运动鞋", "六一 童装 儿童运动", "暑期 亲子户外 运动"
]

queries = []
queries.extend(FOCUS_QUERIES)

for brand in KIDS_BRANDS:
    for kw in ["新品", "运动鞋", "跑鞋", "篮球鞋", "防晒衣", "凉感T恤", "冲锋衣", "开学季"]:
        queries.append(f"{brand} {kw}")

for brand in ADULT_BRANDS:
    for kw in ["新品", "跑鞋", "碳板跑鞋", "防晒衣", "冲锋衣", "户外鞋", "恢复拖鞋"]:
        queries.append(f"{brand} {kw}")

for event in ["618", "双11", "双12", "99大促", "开学季", "六一", "暑期"]:
    for kw in ["儿童运动鞋", "童装", "跑鞋", "防晒衣", "冲锋衣", "户外鞋"]:
        queries.append(f"{event} {kw} 热卖")

QUERIES = list(dict.fromkeys(queries))[:MAX_QUERIES]

# =========================================================
# 3. 过滤词库
# =========================================================
BAD_TITLE_WORDS = [
    # 财经/资本市场
    "股票", "涨停", "跌停", "股价", "财报", "年报", "中报", "季报", "业绩发布",
    "营收", "毛利率", "净利润", "市值", "港股", "A股", "美股", "IPO", "融资",
    "券商", "研报", "目标价", "评级", "东方财富", "雪球", "财富号",
    # 非鞋服商品
    "电视", "手机", "汽车", "房产", "床品", "枕芯", "被芯", "床垫", "饮品", "冷饮",
    "相机", "音频", "数码", "保健品", "普拉达", "资生堂", "桑蚕丝",
    # 体育赛事新闻，不是运动消费/商品
    "比分", "赛程", "转会", "主教练", "球员", "伤病", "冠军", "夺冠", "决赛", "世界杯版权",
    # 低质/广告
    "超值好货", "省钱快报", "加拿大省钱快报", "北美省钱快报", "t.cn", "http://t.cn",
    "超话", "抽奖", "转发本条", "我来了", "偶遇", "哈哈", "打call", "送花花",
    "365BET", "博彩", "官网入口", "赛果",
    "消费指南", "白皮书", "ESG", "可持续", "榜单", "市场规模", "指南", "测评",
    "推荐", "排行榜", "怎么买", "哪款好","人工智能","AI","出海","跨境电商"
]

BAD_SOURCES = [
    "雪球", "东方财富", "证券时报", "财联社", "华尔街见闻", "中华网财经", "21财经",
    "财富号", "加拿大省钱快报", "北美省钱快报", "格隆汇", "AASTOCKS"
]

WEAK_AD_WORDS = [
    "凑单", "领券", "券后", "到手", "国补", "专场", "已开售", "好价", "包邮",
    "推荐榜", "排行榜", "怎么选", "买哪个牌子好", "深度测评", "避坑指南", "选购指南"
]

TRUSTED_SOURCES = [
    "美通社", "36氪", "新华网", "人民网", "澎湃", "thepaper", "界面", "Jiemian",
    "中国日报", "新京报", "凤凰网", "腾讯", "QQ News", "中华网生活", "赢商网",
    "亿邦动力", "母婴行业观察", "中国纺织报", "Hypebeast", "CBNData", "经济观察报",
    "Morketing", "品牌星球", "联商网", "电商报", "钛媒体", "虎嗅"
]

# =========================================================
# 4. 工具函数
# =========================================================
def clean_text(text):
    text = str(text or "").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def short(text, n=80):
    text = clean_text(text)
    return text if len(text) <= n else text[:n] + "..."


def compact_key(title):
    text = clean_text(title).lower()
    text = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|]+", "", text)
    return text[:58]


def parse_pub_date(pub_date):
    try:
        if not pub_date:
            return None
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def age_hours(pub_date):
    dt = parse_pub_date(pub_date)
    if not dt:
        return 999999
    return (NOW_UTC - dt).total_seconds() / 3600


def is_recent(pub_date):
    dt = parse_pub_date(pub_date)
    if dt is None:
        return False
    return CUTOFF_DATE <= dt <= NOW_UTC + timedelta(hours=2)


def has_any(text, words):
    return any(w in text for w in words)


def google_news_rss(query):
    return f"https://news.google.com/rss/search?q={quote(query)} when:{RECENT_DAYS}d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"


def fetch_rss(query, timeout=15):
    url = google_news_rss(query)
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 TrendRadar Product Monitor"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        for idx, item in enumerate(root.findall(".//item")):
            if idx >= RSS_PER_QUERY:
                break
            source_node = item.find("source")
            items.append({
                "title": clean_text(item.findtext("title")),
                "link": clean_text(item.findtext("link")),
                "pub_date": clean_text(item.findtext("pubDate")),
                "source": clean_text(source_node.text if source_node is not None else "Google News"),
                "query": query
            })
        return items
    except Exception as e:
        print(f"fetch rss error: {query} {repr(e)}")
        return []


def is_trusted_source(source, title):
    text = f"{source} {title}"
    return has_any(text, TRUSTED_SOURCES)


def has_core_product_signal(title):

    must_have_product = [
        "鞋","跑鞋","篮球鞋","足球鞋",
        "童鞋","运动鞋","户外鞋",
        "防晒衣","防晒服","凉感T恤","速干T恤",
        "冲锋衣","羽绒服","棉服",
        "外套","短裤","长裤",
        "帽","书包","拖鞋","凉鞋"
    ]

    product_scene = [
        "儿童","青少年","校园","足弓",
        "篮球","足球","跑步","户外",
        "防晒","凉感","速干","缓震","碳板"
    ]

    must_have_action = [
        "新品","上新","发布","首发",
        "上市","联名","热卖","爆款",
        "推出","登场","开售"
    ]

    return (
        has_any(title, must_have_product)
        and
        (has_any(title, must_have_action) or has_any(title, product_scene))
    )


def has_strong_product_signal(title):
    strong = [
        "新品", "上新", "发布", "首发", "上市", "联名", "热卖", "爆款",
        "跑鞋", "运动鞋", "篮球鞋", "足球鞋", "户外鞋", "童鞋", "防晒衣", "凉感T恤",
        "速干T恤", "冲锋衣", "羽绒服", "棉服", "足弓", "碳板", "缓震", "防水", "保暖"
    ]
    return has_any(title, strong)


def should_drop_item(title, source, pub_date):
    title = clean_text(title)
    source = clean_text(source)
    full = f"{title} {source}"

    if not title or len(title) < 8:
        return True
    if not is_recent(pub_date):
        return True
    if has_any(full, BAD_TITLE_WORDS):
        return True
    if has_any(source, BAD_SOURCES):
        return True

    # 商品信号区必须有鞋服/运动/儿童/新品等硬信号，纯营销、纯财报、纯生活方式不要进
    if not has_core_product_signal(title):
        return True
    # 必须是真商品
    if not has_strong_product_signal(title):
        return True

    # 弱广告测评类，只保留同时有品牌 + 明确产品词的内容
    if has_any(title, WEAK_AD_WORDS):
        if not (detect_brand(title) and has_strong_product_signal(title)):
            return True

    # 新浪类内容噪音高，严格保留新品/产品/品牌硬信号
    if "新浪" in source or "新浪" in title or "Sina" in source:
        return True

    # 没品牌也没强商品词，过滤
    if not detect_brand(title) and not has_strong_product_signal(title):
        return True

    return False


def detect_brand(title):
    text = clean_text(title)
    lower_text = text.lower()
    hits = []

    for brand in BRANDS:
        b_lower = brand.lower()
        if brand == "On":
            patterns = [r"\bOn Running\b", r"On昂跑", r"昂跑", r"Cloudsurfer", r"Cloudmonster", r"Cloud 6", r"Cloudflow"]
            if any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
                hits.append("On")
            continue
        if brand in text or b_lower in lower_text:
            hits.append(brand)

    normalize = {
        "361度儿童": "361儿童", "361°儿童": "361儿童", "361°KIDS": "361儿童", "361 Kids": "361儿童",
        "361度": "361°", "FILA KIDS": "FILA Kids", "ON Running": "On", "HOKA": "Hoka",
        "ASICS": "Asics", "moodytiger": "modytiger"
    }
    return list(dict.fromkeys([normalize.get(h, h) for h in hits]))


def detect_keywords(text):
    text = clean_text(text)
    lower_text = text.lower()
    hits = []
    for kw in PRODUCT_KEYWORDS:
        if kw in text or kw.lower() in lower_text:
            hits.append(kw)
    return list(dict.fromkeys(hits))


def classify_category(text):
    rules = [
        ("儿童鞋", ["儿童跑鞋", "儿童篮球鞋", "儿童运动鞋", "青少年跑鞋", "校园运动鞋", "跳绳鞋", "童鞋", "足弓"]),
        ("儿童服装", ["儿童防晒衣", "儿童凉感T恤", "儿童速干T恤", "儿童运动套装", "童装", "儿童外套", "儿童羽绒服", "儿童冲锋衣"]),
        ("防晒凉感", ["防晒", "凉感", "速干", "冰感"]),
        ("跑步科技", ["碳板", "厚底", "竞速", "缓震", "跑鞋", "马拉松", "超临界"]),
        ("篮球足球", ["篮球", "足球", "篮球鞋", "足球鞋"]),
        ("户外轻运动", ["户外", "轻户外", "冲锋衣", "户外鞋", "山系", "越野", "露营", "徒步", "溯溪"]),
        ("运动恢复", ["恢复拖鞋", "拖鞋", "运动凉鞋", "洞洞鞋", "凉鞋"]),
        ("秋冬保暖", ["羽绒服", "棉服", "加绒", "保暖", "抓绒", "雪地靴", "防滑"]),
        ("防水防护", ["防水", "防风", "软壳", "防滑"]),
        ("青少年成人化", ["青少年", "成人化", "大童", "中大童", "校园"]),
        ("品牌新品", ["新品", "上新", "发布", "首发", "上市", "联名"]),
        ("大促热卖", EVENT_KEYWORDS + ["热卖", "爆款", "大促"]),
    ]
    for cat, words in rules:
        if has_any(text, words):
            return cat
    return "商品趋势"


def detect_season_tag(text):
    if has_any(text, ["防晒", "凉感", "速干", "短裤", "凉鞋", "溯溪", "冰感"]):
        return "夏季"
    if has_any(text, ["羽绒服", "棉服", "保暖", "加绒", "抓绒", "雪地靴"]):
        return "冬季"
    if has_any(text, ["开学", "卫衣", "篮球", "训练", "长裤"]):
        return "秋季"
    if has_any(text, ["轻外套", "跑步", "轻户外", "棒球服"]):
        return "春季"
    return "全年"


def freshness_bonus(pub_date):
    h = age_hours(pub_date)
    if h <= 24:
        return 20
    if h <= 72:
        return 14
    if h <= 168:
        return 8
    if h <= 336:
        return 3
    return 0


def score_signal(title, query, brands, keywords, source, pub_date):
    score = 20
    score += freshness_bonus(pub_date)

    value_words = [
        "新品", "热卖", "爆款", "上新", "发布", "首发", "上市", "联名", "儿童", "青少年",
        "防晒", "凉感", "速干", "跑鞋", "户外", "碳板", "足弓", "保暖", "防水", "冲锋衣",
        "开学季", "双11", "618", "六一", "暑期"
    ]
    for w in value_words:
        if w in title:
            score += 6

    # 儿童品牌优先于成人品牌
    if any(b in KIDS_BRANDS or b in ["361儿童", "FILA Kids"] for b in brands):
        score += 18
    elif brands:
        score += 8

    score += min(len(keywords) * 3, 24)

    if has_any(query, ["儿童", "青少年", "童装", "童鞋"]):
        score += 8
    if has_any(query, EVENT_KEYWORDS):
        score += 4
    if is_trusted_source(source, title):
        score += 6

    # 强商品词加分
    if has_strong_product_signal(title):
        score += 10

    # 处罚泛内容
    weak_words = ["ESG", "白皮书", "趋势报告", "消费洞察", "财报", "营收", "市值", "融资", "收购"]
    for w in weak_words:
        if w in title:
            score -= 18

    if not brands and len(keywords) < 2:
        score -= 18
    if "新浪" in source or "新浪" in title:
        score -= 8

    return max(0, min(score, 100))

# =========================================================
# 5. 主程序
# =========================================================
def main():
    signals = []
    seen = set()

    print(f"Product signal monitor | recent_days={RECENT_DAYS} | queries={len(QUERIES)}")

    for idx, query in enumerate(QUERIES, start=1):
        print(f"[{idx}/{len(QUERIES)}] search: {query}")
        items = fetch_rss(query)
        time.sleep(0.35)

        for item in items:
            title = clean_text(item.get("title", ""))
            source = clean_text(item.get("source", ""))
            pub_date = clean_text(item.get("pub_date", ""))
            key = compact_key(title)

            if not title or key in seen:
                continue
            if should_drop_item(title, source, pub_date):
                continue

            brands = detect_brand(title)
            full_text = f"{title} {query}"
            keywords = detect_keywords(full_text)
            category = classify_category(full_text)
            season_tag = detect_season_tag(full_text)
            heat = score_signal(title, query, brands, keywords, source, pub_date)

            if heat < 45:
                continue

            seen.add(key)
            signals.append({
                "date": TODAY,
                "title": title,
                "short_title": short(title, 66),
                "query": query,
                "brand_hits": brands,
                "keyword_hits": keywords[:10],
                "category": category,
                "season_tag": season_tag,
                "source": source,
                "link": item.get("link", ""),
                "pub_date": pub_date,
                "age_hours": round(age_hours(pub_date), 1),
                "heat": heat,
                "type": "product_signal"
            })

    signals = sorted(signals, key=lambda x: (x.get("heat", 0), -x.get("age_hours", 999999)), reverse=True)
    top_signals = signals[:MAX_SIGNALS]

    brand_counter = Counter()
    keyword_counter = Counter()
    category_counter = Counter()
    season_counter = Counter()

    for s in top_signals:
        for b in s.get("brand_hits", []):
            brand_counter[b] += 1
        for k in s.get("keyword_hits", []):
            keyword_counter[k] += 1
        category_counter[s.get("category", "商品趋势")] += 1
        season_counter[s.get("season_tag", "全年")] += 1

    summary = {
        "date": TODAY,
        "generated_time": NOW_TIME,
        "source": "Google News RSS product signal monitor",
        "desc": "运动鞋服商品趋势信号监测：重点覆盖儿童运动、鞋服新品、夏季功能、跑步科技、户外轻运动、大促热卖。已强化过滤财经财报、纯营销、弱广告、测评导购和非鞋服商品。",
        "recent_days": RECENT_DAYS,
        "query_count": len(QUERIES),
        "signal_count": len(top_signals),
        "top_brands": brand_counter.most_common(40),
        "top_keywords": keyword_counter.most_common(60),
        "top_categories": category_counter.most_common(30),
        "top_seasons": season_counter.most_common(10),
        "signals": top_signals
    }

    output_file = OUTPUT_DIR / f"product_signals_{TODAY}.json"
    latest_file = OUTPUT_DIR / "latest_product_signals.json"

    output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"product signals saved: {output_file}")
    print(f"latest product signals saved: {latest_file}")
    print(f"signal count: {len(top_signals)}")

    print("\nTop 20 product signals:")
    for i, s in enumerate(top_signals[:20], start=1):
        print(f"{i}. [{s['heat']}] [{s['category']}] {s['title']} | {s['source']}")


if __name__ == "__main__":
    main()
