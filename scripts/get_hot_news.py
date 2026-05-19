import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# =========================
# 1. 更贴近经营日报的关键词
# =========================

KEYWORDS = [
    "运动品牌 消费 零售",
    "运动童装 儿童运动 消费",
    "童装 亲子 户外 运动",
    "618 运动品牌 防晒 凉感",
    "防晒衣 凉感 速干 运动",
    "抖音电商 运动品牌",
    "小红书 种草 运动品牌",
    "商场 客流 消费 运动品牌",
    "奥莱 折扣 运动品牌",
    "户外 露营 骑行 亲子消费",
    "安踏 童装 儿童",
    "李宁 童装 儿童",
    "特步 儿童 运动",
    "361度 儿童 运动",
    "高温 防晒 消费",
    "暴雨 天气 商场 客流",
]

MAX_ITEMS = 80
OUT_DIR = Path("output/news")
OUT_FILE = OUT_DIR / "latest.json"

# =========================
# 2. 过滤泛体育/赛事内容
# =========================

NEGATIVE_KEYWORDS = [
    "中超", "英超", "欧冠", "NBA", "CBA", "世界杯", "世锦赛",
    "冠军", "夺冠", "决赛", "半决赛", "比分", "赛程", "联赛",
    "主教练", "球员", "转会", "足球", "篮球", "乒乓球", "羽毛球",
    "网球", "拳击", "格斗", "赛车", "马拉松成绩", "破纪录",
    "体育总局", "奥运会", "全运会", "国家队", "运动员",
]

# =========================
# 3. 提升经营相关性
# =========================

POSITIVE_KEYWORDS = [
    "童装", "儿童", "亲子", "运动品牌", "品牌", "消费", "零售",
    "商场", "商圈", "客流", "门店", "奥莱", "折扣", "会员",
    "电商", "直播", "抖音", "小红书", "种草", "618", "大促",
    "防晒", "凉感", "速干", "高温", "暴雨", "天气", "户外",
    "露营", "骑行", "文旅", "夜经济", "暑期", "校园",
    "安踏", "李宁", "特步", "361", "On", "lululemon", "始祖鸟",
]

SOURCE_PREFERENCE = [
    "界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报",
    "中国商报", "北京商报", "第一财经", "证券时报", "新华网",
    "澎湃新闻", "每日经济新闻", "南方都市报", "腾讯新闻",
]


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
        title = clean_text(item.findtext("title"))
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


def is_negative(title: str) -> bool:
    return any(k in title for k in NEGATIVE_KEYWORDS)


def relevance_score(item: dict) -> int:
    title = item.get("title", "")
    source = item.get("source", "")

    score = 0

    for k in POSITIVE_KEYWORDS:
        if k in title:
            score += 3

    for s in SOURCE_PREFERENCE:
        if s in source:
            score += 2

    if any(k in title for k in ["童装", "儿童", "亲子", "运动童装"]):
        score += 6

    if any(k in title for k in ["618", "大促", "防晒", "凉感", "高温", "暴雨"]):
        score += 5

    if any(k in title for k in ["商场", "商圈", "客流", "门店", "奥莱", "零售"]):
        score += 5

    if any(k in title for k in ["抖音", "小红书", "直播", "电商", "种草"]):
        score += 5

    if is_negative(title):
        score -= 20

    return score


def dedupe(items):
    seen = set()
    result = []

    for item in items:
        title = item.get("title", "")
        key = re.sub(r"\W+", "", title.lower())

        if not key or key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def main():
    all_items = []

    for keyword in KEYWORDS:
        try:
            rows = fetch_google_news_rss(keyword)
            all_items.extend(rows)
            print(f"Fetched {len(rows)} items for: {keyword}")
            time.sleep(0.4)
        except Exception as e:
            print(f"Fetch failed: {keyword} | {e}")

    all_items = dedupe(all_items)

    # 过滤明显不相关赛事新闻
    filtered = []
    for item in all_items:
        title = item.get("title", "")
        score = relevance_score(item)
        if score > 0:
            item["score"] = score
            filtered.append(item)

    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    filtered = filtered[:MAX_ITEMS]

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


if __name__ == "__main__":
    main()
