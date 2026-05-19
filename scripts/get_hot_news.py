import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

KEYWORDS = [
    "运动品牌", "运动童装", "儿童运动", "安踏", "李宁", "特步", "361度",
    "防晒衣", "凉感", "618 运动", "抖音 电商 运动", "小红书 种草 运动",
    "户外 露营 骑行", "商场 客流 消费", "奥莱 折扣 运动"
]

MAX_ITEMS = 80
OUT_DIR = Path("output/news")
OUT_FILE = OUT_DIR / "latest.json"


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
            all_items.extend(fetch_google_news_rss(keyword))
            time.sleep(0.5)
        except Exception as e:
            print(f"Fetch failed: {keyword} | {e}")

    all_items = dedupe(all_items)
    all_items = all_items[:MAX_ITEMS]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(all_items),
        "items": all_items
    }

    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(all_items)} news items to {OUT_FILE}")


if __name__ == "__main__":
    main()
