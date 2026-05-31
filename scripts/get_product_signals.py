from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import xml.etree.ElementTree as ET
import requests
import json
import re
import time
from collections import Counter

OUTPUT_DIR = Path("output/products")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# =========================================================
# 1. 品牌池：儿童 / 成人 / 童装 / 户外 / 生活方式
# =========================================================
BRANDS = [
    # 361与核心儿童运动竞品
    "361儿童", "361°儿童", "安踏儿童", "李宁YOUNG", "特步儿童",
    "FILA Kids", "Nike Kids", "Adidas Kids", "Puma Kids",
    "New Balance Kids", "Skechers Kids", "Asics Kids", "Jordan Kids",

    # 重要童装 / 儿童生活方式品牌
    "巴拉巴拉", "Balabala", "Mini Peace", "modytiger", "moodytiger",
    "MQD童装", "安奈儿", "Annil", "小猪班纳", "pawin paw",
    "马骑顿", "M.Latin Kids", "jnby by JNBY", "戴维贝拉", "davebella",
    "英氏", "YeeHoO", "暇步士童装", "Hush Puppies Kids",

    # 国内成人运动
    "安踏", "李宁", "361°", "特步", "鸿星尔克", "匹克", "乔丹体育", "FILA",

    # 国际运动
    "Nike", "Adidas", "Puma", "New Balance", "Asics", "Skechers",
    "Under Armour", "Jordan", "Converse", "Vans", "Crocs",

    # 跑步 / 户外 / 趋势品牌
    "On", "Hoka", "Salomon", "lululemon", "Arc'teryx", "始祖鸟",
    "The North Face", "北面", "迪桑特", "Descente", "可隆", "KOLON SPORT",
    "凯乐石", "KAILAS", "伯希和", "PELLIOT", "蕉下", "Beneunder"
]

# =========================================================
# 2. 经营节点：全年大促 / 季节 / 场景
# =========================================================
EVENT_KEYWORDS = [
    "618", "双11", "双十一", "双12", "双十二", "99大促", "年货节",
    "38节", "女王节", "520", "六一", "儿童节", "开学季", "暑期",
    "寒假", "春节", "国庆", "中秋", "会员日", "奥莱折扣",
    "直播大促", "抖音大促", "天猫大促", "京东大促", "唯品会大促"
]

# =========================================================
# 3. 四季商品池
# =========================================================
SEASON_PRODUCTS = [
    # 春季
    "轻外套", "卫衣", "长裤", "棒球服", "校园运动鞋", "跑步鞋", "轻户外鞋",

    # 夏季
    "防晒衣", "凉感T恤", "速干T恤", "短裤", "运动凉鞋", "溯溪鞋",
    "遮阳帽", "防晒帽", "冰感面料",

    # 秋季
    "开学鞋", "训练鞋", "篮球鞋", "足球鞋", "卫衣套装", "运动长裤",
    "冲锋衣", "软壳外套",

    # 冬季
    "羽绒服", "棉服", "加绒裤", "保暖内衣", "抓绒衣", "防风外套",
    "防水外套", "防滑鞋", "棉鞋", "雪地靴", "冬季跑鞋"
]

# =========================================================
# 4. 鞋类科技 / 结构 / 场景
# =========================================================
SHOE_TECH_KEYWORDS = [
    "碳板跑鞋", "全掌碳板", "半掌碳板", "厚底跑鞋", "缓震跑鞋",
    "竞速跑鞋", "慢跑鞋", "训练跑鞋", "轻量跑鞋", "稳定支撑跑鞋",
    "足弓支撑", "防滑大底", "耐磨大底", "回弹科技", "氮科技",
    "超临界发泡", "EVA中底", "TPU支撑", "BOA旋钮", "防水鞋面"
]

# =========================================================
# 5. 运动场景池
# =========================================================
SPORT_SCENES = [
    "跑步", "马拉松", "篮球", "足球", "网球", "羽毛球", "乒乓球",
    "跳绳", "校园体育", "中考体育", "亲子运动", "户外徒步",
    "露营", "骑行", "滑雪", "瑜伽", "健身", "训练", "通勤",
    "城市轻户外", "山系穿搭", "越野跑", "溯溪"
]

# =========================================================
# 6. 人群趋势
# =========================================================
CONSUMER_KEYWORDS = [
    "儿童", "青少年", "大童", "小童", "中大童", "成人化", "亲子同款",
    "校园", "学生党", "年轻人", "女性运动", "家庭消费", "低线城市",
    "下沉市场", "悦己消费", "情绪消费", "户外家庭"
]

# =========================================================
# 7. 全部商品关键词
# =========================================================
PRODUCT_KEYWORDS = list(dict.fromkeys(
    SEASON_PRODUCTS
    + SHOE_TECH_KEYWORDS
    + SPORT_SCENES
    + CONSUMER_KEYWORDS
    + EVENT_KEYWORDS
    + [
        "新品", "热卖", "爆款", "上新", "联名", "科技", "缓震",
        "防晒", "凉感", "速干", "轻量", "防水", "防风", "保暖",
        "功能面料", "运动科技", "专业运动", "生活方式", "多巴胺穿搭"
    ]
))

# =========================================================
# 8. 重点搜索词
# =========================================================
FOCUS_QUERIES = [
    # 儿童 / 青少年
    "儿童运动鞋 新品 热卖",
    "青少年跑鞋 新品 热卖",
    "儿童篮球鞋 校园 体育",
    "儿童防晒衣 热卖",
    "儿童凉感T恤 热卖",
    "儿童冲锋衣 防水",
    "儿童羽绒服 保暖",
    "童装 运动 新品",
    "青少年 成人化 运动鞋",

    # 成人运动趋势
    "碳板跑鞋 新品 热卖",
    "厚底跑鞋 热卖",
    "缓震跑鞋 新品",
    "户外鞋 热卖",
    "冲锋衣 新品 热卖",
    "防晒衣 运动品牌 热卖",
    "瑜伽服 新品 热卖",
    "轻户外 运动品牌 新品",

    # 大促节点
    "618 运动品牌 热卖 商品",
    "双11 运动品牌 热卖 商品",
    "双12 运动品牌 热卖 商品",
    "99大促 运动品牌 热卖 商品",
    "开学季 儿童运动鞋",
    "年货节 运动品牌",
    "六一 童装 儿童运动",
]

CORE_KIDS_BRANDS = [
    "361儿童", "安踏儿童", "李宁YOUNG", "FILA Kids", "Nike Kids",
    "Adidas Kids", "巴拉巴拉", "Balabala", "modytiger", "Mini Peace",
    "安奈儿", "戴维贝拉"
]

CORE_ADULT_BRANDS = [
    "Nike", "Adidas", "On", "Hoka", "Salomon", "lululemon",
    "安踏", "李宁", "361°", "特步", "北面", "迪桑特", "始祖鸟"
]

# =========================================================
# 工具函数
# =========================================================
def clean_text(text):
    text = str(text or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text

def short(text, n=80):
    text = clean_text(text)
    return text if len(text) <= n else text[:n] + "..."

def google_news_rss(query):
    q = quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

def fetch_rss(query, timeout=15):
    url = google_news_rss(query)
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 TrendRadar Product Monitor"}
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        items = []
        for item in root.findall(".//item"):
            title = clean_text(item.findtext("title"))
            link = clean_text(item.findtext("link"))
            pub_date = clean_text(item.findtext("pubDate"))

            source = ""
            source_node = item.find("{http://search.yahoo.com/mrss/}source")
            if source_node is not None:
                source = clean_text(source_node.text)

            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "source": source,
                    "query": query
                })
        return items

    except Exception as e:
        print(f"fetch rss error: {query} {repr(e)}")
        return []

def detect_brand(text):
    hits = []
    lower_text = text.lower()
    for brand in BRANDS:
        if brand.lower() in lower_text or brand in text:
            hits.append(brand)
    return list(dict.fromkeys(hits))

def detect_keywords(text):
    hits = []
    lower_text = text.lower()
    for kw in PRODUCT_KEYWORDS:
        if kw.lower() in lower_text or kw in text:
            hits.append(kw)
    return list(dict.fromkeys(hits))

def classify_category(text):
    rules = [
        ("儿童鞋", ["儿童跑鞋", "儿童篮球鞋", "儿童运动鞋", "青少年跑鞋", "校园运动鞋", "跳绳鞋", "童鞋"]),
        ("儿童服装", ["儿童防晒衣", "儿童凉感T恤", "儿童速干T恤", "儿童运动套装", "童装", "儿童外套", "儿童羽绒服", "儿童冲锋衣"]),
        ("青少年成人化", ["青少年", "成人化", "大童", "中大童", "校园"]),
        ("跑步科技", ["碳板", "厚底", "竞速", "缓震", "跑鞋", "马拉松"]),
        ("篮球足球", ["篮球", "足球", "篮球鞋", "足球鞋"]),
        ("户外轻运动", ["户外", "轻户外", "冲锋衣", "户外鞋", "山系", "越野", "露营", "徒步"]),
        ("防晒凉感", ["防晒", "凉感", "速干", "冰感"]),
        ("秋冬保暖", ["羽绒服", "棉服", "加绒", "保暖", "抓绒", "雪地靴", "防滑"]),
        ("防水防护", ["防水", "防风", "冲锋衣", "软壳", "防滑"]),
        ("大促节点", EVENT_KEYWORDS),
        ("品牌新品", ["新品", "上新", "发布", "联名"]),
        ("平台热卖", ["热卖", "爆款", "大促"]),
    ]

    for cat, words in rules:
        if any(w in text for w in words):
            return cat
    return "综合趋势"

def detect_season_tag(text):
    if any(w in text for w in ["防晒", "凉感", "速干", "短裤", "凉鞋", "溯溪"]):
        return "夏季"
    if any(w in text for w in ["羽绒服", "棉服", "保暖", "加绒", "抓绒", "雪地靴"]):
        return "冬季"
    if any(w in text for w in ["开学", "卫衣", "篮球", "训练", "长裤"]):
        return "秋季"
    if any(w in text for w in ["轻外套", "跑步", "轻户外", "棒球服"]):
        return "春季"
    return "全年"

def score_signal(title, query, brands, keywords):
    score = 10

    value_words = [
        "新品", "热卖", "爆款", "上新", "发布", "联名",
        "增长", "趋势", "儿童", "青少年", "防晒", "凉感",
        "跑鞋", "户外", "碳板", "保暖", "防水", "冲锋衣",
        "开学季", "双11", "618"
    ]
    bad_words = ["股票", "涨停", "财报", "赛事比分", "转会", "球员", "伤病"]

    for w in value_words:
        if w in title:
            score += 7

    for w in bad_words:
        if w in title:
            score -= 25

    score += len(brands) * 10
    score += min(len(keywords) * 4, 24)

    if any(w in query for w in ["儿童", "青少年", "童装"]):
        score += 8
    if any(w in query for w in EVENT_KEYWORDS):
        score += 6
    if any(w in query for w in SHOE_TECH_KEYWORDS):
        score += 6

    return max(0, min(score, 100))

# =========================================================
# 生成搜索任务
# =========================================================
queries = []

queries.extend(FOCUS_QUERIES)

# 儿童品牌 × 商品方向
for brand in CORE_KIDS_BRANDS:
    for kw in ["新品", "运动鞋", "跑鞋", "篮球鞋", "防晒衣", "凉感T恤", "冲锋衣", "羽绒服", "开学季"]:
        queries.append(f"{brand} {kw}")

# 成人品牌 × 场景/科技
for brand in CORE_ADULT_BRANDS:
    for kw in ["新品", "跑鞋 热卖", "碳板跑鞋", "防晒衣", "冲锋衣", "户外鞋", "双11", "618"]:
        queries.append(f"{brand} {kw}")

# 节点 × 核心品类
for event in ["618", "双11", "双12", "99大促", "开学季", "年货节", "六一"]:
    for kw in ["儿童运动鞋", "童装", "跑鞋", "防晒衣", "羽绒服", "冲锋衣"]:
        queries.append(f"{event} {kw} 热卖")

queries = list(dict.fromkeys(queries))[:140]

# =========================================================
# 抓取信号
# =========================================================
signals = []
seen_titles = set()

for idx, query in enumerate(queries, start=1):
    print(f"[{idx}/{len(queries)}] search: {query}")

    items = fetch_rss(query)
    time.sleep(0.45)

    for item in items[:7]:
        title = clean_text(item.get("title", ""))
        if not title or title in seen_titles:
            continue

        seen_titles.add(title)

        full_text = title + " " + query
        brands = detect_brand(full_text)
        keywords = detect_keywords(full_text)
        category = classify_category(full_text)
        season_tag = detect_season_tag(full_text)
        heat = score_signal(title, query, brands, keywords)

        if heat <= 15:
            continue

        signals.append({
            "date": today,
            "title": title,
            "short_title": short(title, 66),
            "query": query,
            "brand_hits": brands,
            "keyword_hits": keywords,
            "category": category,
            "season_tag": season_tag,
            "source": item.get("source", ""),
            "link": item.get("link", ""),
            "pub_date": item.get("pub_date", ""),
            "heat": heat,
            "type": "product_signal"
        })

# =========================================================
# 汇总统计
# =========================================================
brand_counter = Counter()
keyword_counter = Counter()
category_counter = Counter()
season_counter = Counter()

for s in signals:
    for b in s.get("brand_hits", []):
        brand_counter[b] += 1
    for k in s.get("keyword_hits", []):
        keyword_counter[k] += 1
    category_counter[s.get("category", "综合趋势")] += 1
    season_counter[s.get("season_tag", "全年")] += 1

top_signals = sorted(signals, key=lambda x: x.get("heat", 0), reverse=True)[:100]

summary = {
    "date": today,
    "generated_time": now_time,
    "source": "Google News RSS product signal monitor",
    "desc": "全年运动鞋服商品趋势信号监测：覆盖儿童、成人、童装、四季商品、大促节点、鞋科技、运动场景。该数据代表公开资讯热度信号，不等同于平台真实销量。",
    "query_count": len(queries),
    "signal_count": len(signals),
    "top_brands": brand_counter.most_common(40),
    "top_keywords": keyword_counter.most_common(60),
    "top_categories": category_counter.most_common(30),
    "top_seasons": season_counter.most_common(10),
    "signals": top_signals
}

output_file = OUTPUT_DIR / f"product_signals_{today}.json"
latest_file = OUTPUT_DIR / "latest_product_signals.json"

output_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
latest_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"product signals saved: {output_file}")
print(f"latest product signals saved: {latest_file}")
print(f"signal count: {len(signals)}")
