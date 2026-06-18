from pathlib import Path
import json
import re
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

WEEKLY_NEWS = Path("output/weekly/weekly_news.json")
ANALYSIS_FILE = Path("output/weekly/weekly_analysis.json")
IMAGE_CACHE = Path("output/weekly/news_image_cache.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_url(v):
    v = str(v or "").strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return ""


def title_key(title):
    t = re.sub(r"\s+", "", str(title or "").lower())
    t = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\-_/|]+", "", t)
    return t[:60]


def fetch_cover(url):
    url = clean_url(url)
    if not url:
        return ""

    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if not r.ok:
            return ""

        soup = BeautifulSoup(r.text, "html.parser")

        candidates = [
            ("meta", {"property": "og:image"}),
            ("meta", {"name": "og:image"}),
            ("meta", {"property": "twitter:image"}),
            ("meta", {"name": "twitter:image"}),
            ("meta", {"itemprop": "image"}),
        ]

        for tag_name, attrs in candidates:
            tag = soup.find(tag_name, attrs=attrs)
            if tag:
                img = tag.get("content") or tag.get("value") or ""
                img = clean_url(urljoin(url, img))
                if img:
                    return img

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
            src = clean_url(urljoin(url, src))
            if src and not any(x in src.lower() for x in ["logo", "icon", "avatar", "qrcode"]):
                return src

    except Exception as e:
        print(f"fetch image failed: {url} | {e}")

    return ""


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load json error: {path} | {e}")
    return default


def collect_items():
    items = []

    weekly_news = load_json(WEEKLY_NEWS, {})
    analysis = load_json(ANALYSIS_FILE, {})

    for level in ["A", "B", "C"]:
        rows = weekly_news.get("levels", {}).get(level, {}).get("items", [])
        if isinstance(rows, list):
            items.extend(rows)

    if isinstance(weekly_news.get("hot_products"), list):
        items.extend(weekly_news.get("hot_products"))

    for key in ["major_events", "competitor_actions"]:
        rows = analysis.get(key, [])
        if isinstance(rows, list):
            items.extend(rows)

    return [x for x in items if isinstance(x, dict)]


def main():
    old_cache = load_json(IMAGE_CACHE, {})
    cache = dict(old_cache)

    items = collect_items()
    print(f"items to check: {len(items)}")

    updated = 0

    for item in items:
        title = item.get("title", "")
        link = clean_url(item.get("link") or item.get("url"))
        key = title_key(title)

        if not key or not link:
            continue

        if cache.get(key, {}).get("image"):
            continue

        image = fetch_cover(link)

        cache[key] = {
            "title": title,
            "link": link,
            "source": item.get("source", ""),
            "image": image
        }

        if image:
            updated += 1
            print(f"image ok: {title[:30]} -> {image[:80]}")
        else:
            print(f"image none: {title[:30]}")

    IMAGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"image cache saved: {IMAGE_CACHE}")
    print(f"new images: {updated}")


if __name__ == "__main__":
    main()
