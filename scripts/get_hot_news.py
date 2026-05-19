import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# =========================
# 1. 资讯抓取关键词
# =========================

KEYWORDS = [
    # 运动童装 / 儿童运动
    "运动童装 儿童运动 消费",
    "童装 亲子 户外 运动",
    "儿童运动 校园 体育 消费",
    "亲子运动 童装 户外",
    "校园体育 运动童装",
    "暑期消费 儿童运动",

    # 品类 / 天气 / 季节
    "防晒衣 凉感 速干 运动",
    "高温 防晒衣 凉感 消费",
    "暴雨 天气 商场 客流",
    "夏季 运动品牌 防晒 凉感",
    "防晒 消费 运动品牌",
    "速干 短裤 运动童装",

    # 平台 / 大促 / 内容
    "618 运动品牌 防晒 凉感",
    "618 童装 运动品牌",
    "双11 运动品牌 童装",
    "抖音电商 运动品牌",
    "抖音直播 童装 运动",
    "小红书 种草 运动品牌",
    "小红书 童装 防晒",
    "天猫 运动童装 618",
    "京东 运动品牌 618",
    "唯品会 运动童装",

    # 商圈 / 门店 / 客流
    "商场 客流 消费 运动品牌",
    "购物中心 儿童运动 亲子",
    "奥莱 折扣 运动品牌",
    "门店 客流 会员 运动品牌",
    "商圈 活动 亲子 运动",
    "本地生活 商场 客流 消费",

    # 场景
    "户外 露营 骑行 亲子消费",
    "城市骑行 运动消费",
    "露营 亲子 户外 消费",
    "夜经济 运动消费",
    "城市徒步 轻户外 消费",

    # 品牌
    "安踏儿童 童装",
    "李宁YOUNG 儿童",
    "特步儿童 运动",
    "361度 儿童 运动",
    "巴拉巴拉 运动童装",
    "迪卡侬 儿童运动",
    "Nike Kids 童装",
    "Adidas Kids 童装",
    "lululemon 中国 消费",
    "始祖鸟 户外 消费",
]

MAX_ITEMS = 80
OUT_DIR = Path("output/news")
OUT_FILE = OUT_DIR / "latest.json"

# =========================
# 2. 负面过滤：减少无经营价值内容
# =========================

NEGATIVE_KEYWORDS = [
    # 泛体育赛事
    "中超", "英超", "欧冠", "NBA", "CBA", "世界杯", "世锦赛",
    "冠军", "夺冠", "决赛", "半决赛", "比分", "赛程", "联赛",
    "主教练", "球员", "转会", "足球", "篮球", "乒乓球", "羽毛球",
    "网球", "拳击", "格斗", "赛车", "马拉松成绩", "破纪录",
    "体育总局", "奥运会", "全运会", "国家队", "运动员",

    # 过度宏观/金融
    "GDP", "央行", "利率", "财政", "货币政策", "地产", "楼市",
    "基金", "证券", "股价", "港股", "A股", "美股", "融资",
    "并购", "IPO", "上市公司", "财报电话会",

    # 低相关
    "彩票", "电竞比赛", "游戏赛事", "博彩",
]

# 有些词不能一刀切过滤，但要降权
SOFT_NEGATIVE_KEYWORDS = [
    "财报", "营收", "净利润", "股东", "市值", "评级", "研报",
    "管理层", "董事会", "资本市场",
]

# =========================
# 3. 经营相关关键词与权重
# =========================

HOT_WORDS = {
    # 童装儿童
    "运动童装": 10,
    "童装": 8,
    "儿童运动": 10,
    "儿童": 6,
    "亲子": 7,
    "校园": 6,
    "校园体育": 8,
    "暑期": 5,

    # 商品品类
    "防晒衣": 9,
    "防晒": 7,
    "凉感": 7,
    "速干": 6,
    "短裤": 5,
    "运动凉鞋": 5,
    "轻外套": 5,
    "功能面料": 5,

    # 天气
    "高温": 7,
    "暴雨": 6,
    "强对流": 6,
    "降雨": 5,
    "天气": 4,

    # 平台与大促
    "618": 7,
    "双11": 7,
    "双十一": 7,
    "大促": 6,
    "预售": 5,
    "抖音": 7,
    "抖音电商": 8,
    "直播": 6,
    "小红书": 7,
    "种草": 6,
    "天猫": 5,
    "京东": 5,
    "唯品会": 5,

    # 门店与商圈
    "商场": 7,
    "商圈": 7,
    "购物中心": 7,
    "客流": 8,
    "门店": 7,
    "奥莱": 7,
    "折扣": 5,
    "会员": 5,
    "零售": 6,
    "消费": 5,
    "本地生活": 6,

    # 场景
    "户外": 7,
    "轻户外": 8,
    "露营": 6,
    "骑行": 6,
    "城市骑行": 8,
    "城市徒步": 7,
    "夜经济": 6,
    "文旅": 6,
    "出行": 5,

    # 品牌
    "安踏儿童": 8,
    "李宁YOUNG": 8,
    "特步儿童": 8,
    "361度": 7,
    "361儿童": 8,
    "巴拉巴拉": 6,
    "迪卡侬": 6,
    "Nike Kids": 6,
    "Adidas Kids": 6,
    "lululemon": 5,
    "始祖鸟": 5,
    "萨洛蒙": 5,
}

SOURCE_PREFERENCE = [
    "界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报",
    "中国商报", "北京商报", "第一财经", "证券时报", "新华网",
    "澎湃新闻", "每日经济新闻", "南方都市报", "腾讯新闻",
    "新京报", "中国经济网", "财联社", "虎嗅", "品牌星球",
]

# =========================
# 4. 工具函数
# =========================

def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_title(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r" - .*?$", "", title)
    title = re.sub(r"_.*?$", "", title)
    title = title.replace("（图）", "").replace("(图)", "")
    return title.strip()


def fetch_google_news_rss(keyword: str):
    query = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    items = []

    for item in root.findall(".//item"):
        title = normalize_title(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        pub_date = clean_text(item.findtext("pubDate"))

        source = "Google News"
        source_node = item.find("source")
        if source_node is not None and source_node.text:
            source = clean_text(source_node.text)

        if title:
            items.append({
                "title": title,
                "source": source,
                "url": link,
                "published_at": pub_date,
                "keyword": keyword,
            })

    return items


def has_any(text: str, words: list) -> bool:
    return any(w in text for w in words)


def is_hard_negative(title: str) -> bool:
    return has_any(title, NEGATIVE_KEYWORDS)


def relevance_score(item: dict) -> int:
    title = item.get("title", "")
    source = item.get("source", "")

    score = 0

    # 经营热词加权
    for word, weight in HOT_WORDS.items():
        if word in title:
            score += weight

    # 来源加权
    for s in SOURCE_PREFERENCE:
        if s in source:
            score += 2

    # 组合加权：更像经营日报的组合
    combos = [
        (["童装", "儿童", "亲子"], 8),
        (["防晒", "凉感", "速干", "高温"], 7),
        (["商场", "商圈", "客流", "门店"], 7),
        (["抖音", "小红书", "直播", "种草"], 6),
        (["户外", "骑行", "露营", "文旅"], 6),
        (["618", "大促", "预售", "双11"], 5),
    ]

    for words, bonus in combos:
        if sum(1 for w in words if w in title) >= 2:
            score += bonus

    # 纯赛事/纯宏观，硬过滤
    if is_hard_negative(title):
        score -= 30

    # 软负面降权
    for w in SOFT_NEGATIVE_KEYWORDS:
        if w in title:
            score -= 5

    # 财报类：只保留和童装/儿童/品类强相关的
    if "财报" in title and not has_any(title, ["童装", "儿童", "品牌", "零售", "消费"]):
        score -= 12

    return score


def dedupe(items):
    seen = set()
    result = []

    for item in items:
        title = normalize_title(item.get("title", ""))
        key = re.sub(r"\W+", "", title.lower())

        if not key or key in seen:
            continue

        seen.add(key)
        item["title"] = title
        result.append(item)

    return result


def diversify(items):
    """
    控制同类内容占比，避免618或单一品牌霸屏。
    """
    buckets = {
        "promo": [],
        "kids": [],
        "weather": [],
        "platform": [],
        "store": [],
        "outdoor": [],
        "brand": [],
        "other": [],
    }

    for item in items:
        title = item.get("title", "")

        if has_any(title, ["618", "双11", "双十一", "大促", "预售"]):
            buckets["promo"].append(item)
        elif has_any(title, ["童装", "儿童", "亲子", "校园"]):
            buckets["kids"].append(item)
        elif has_any(title, ["高温", "防晒", "凉感", "速干", "暴雨", "天气"]):
            buckets["weather"].append(item)
        elif has_any(title, ["抖音", "小红书", "直播", "种草", "天猫", "京东", "唯品会"]):
            buckets["platform"].append(item)
        elif has_any(title, ["商场", "商圈", "客流", "门店", "奥莱", "会员"]):
            buckets["store"].append(item)
        elif has_any(title, ["户外", "骑行", "露营", "文旅", "夜经济", "出行"]):
            buckets["outdoor"].append(item)
        elif has_any(title, ["安踏", "李宁", "特步", "361", "巴拉巴拉", "迪卡侬", "lululemon", "始祖鸟"]):
            buckets["brand"].append(item)
        else:
            buckets["other"].append(item)

    final = []
    order = ["kids", "weather", "store", "platform", "outdoor", "promo", "brand", "other"]

    limits = {
        "promo": 14,
        "kids": 18,
        "weather": 14,
        "platform": 12,
        "store": 12,
        "outdoor": 10,
        "brand": 8,
        "other": 6,
    }

    for key in order:
        final.extend(buckets[key][:limits[key]])

    final.sort(key=lambda x: x.get("score", 0), reverse=True)
    return final[:MAX_ITEMS]


# =========================
# 5. 主程序
# =========================

def main():
    all_items = []

    for keyword in KEYWORDS:
        try:
            rows = fetch_google_news_rss(keyword)
            all_items.extend(rows)
            print(f"Fetched {len(rows)} items for: {keyword}")
            time.sleep(0.35)
        except Exception as e:
            print(f"Fetch failed: {keyword} | {e}")

    all_items = dedupe(all_items)

    filtered = []

    for item in all_items:
        title = item.get("title", "")
        score = relevance_score(item)

        if score > 0:
            item["score"] = score
            filtered.append(item)

    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    filtered = diversify(filtered)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(filtered),
        "items": filtered,
    }

    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(filtered)} filtered news items to {OUT_FILE}")

    # 输出前20条便于调试
    for i, item in enumerate(filtered[:20], start=1):
        print(f"{i}. [{item.get('score')}] {item.get('title')} | {item.get('source')}")


if __name__ == "__main__":
    main()
