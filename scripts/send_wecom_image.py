import os
import json
import base64
import hashlib
import requests
from pathlib import Path
from PIL import Image

WEBHOOK = os.getenv("REPORT_WEBHOOK")

SOURCE_FILE = os.getenv("SOURCE_FILE", "daily-report.png")
SEND_FILE = os.getenv("SEND_FILE", "daily-report-send.jpg")
NEWS_FILE = Path("output/news/top_news.json")


def compress_image():
    img = Image.open(SOURCE_FILE).convert("RGB")

    max_width = 1200
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height))

    quality = 85
    while quality >= 45:
        img.save(SEND_FILE, "JPEG", quality=quality, optimize=True)
        size = os.path.getsize(SEND_FILE)

        if size < 1900 * 1024:
            print(f"compressed image size: {size / 1024:.1f} KB, quality={quality}")
            return

        quality -= 8

    print(f"warning: image still large: {os.path.getsize(SEND_FILE) / 1024:.1f} KB")


def send_image():
    if not WEBHOOK:
        raise RuntimeError("REPORT_WEBHOOK is missing")

    compress_image()

    with open(SEND_FILE, "rb") as f:
        data = f.read()

    image_base64 = base64.b64encode(data).decode("utf-8")
    image_md5 = hashlib.md5(data).hexdigest()

    payload = {
        "msgtype": "image",
        "image": {
            "base64": image_base64,
            "md5": image_md5
        }
    }

    r = requests.post(WEBHOOK, json=payload, timeout=30)
    print("image status:", r.status_code)
    print("image response:", r.text)
    r.raise_for_status()


def load_news_items():
    if not NEWS_FILE.exists():
        return []

    try:
        raw = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        return raw.get("items", []) if isinstance(raw, dict) else raw
    except Exception as e:
        print("load news error:", repr(e))
        return []


def build_news_markdown(news_items):
    lines = []
    lines.append("## 📌 今日重点资讯")
    lines.append("")

    count = 0

    for item in news_items:
        if count >= 8:
            break

        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        link = str(
            item.get("link")
            or item.get("url")
            or item.get("href")
            or ""
        ).strip()
        source = str(item.get("source", "行业资讯")).strip()

        if not title or not link:
            continue

        count += 1
        lines.append(f"{count}. [{title}]({link})")
        lines.append(f"<font color=\"comment\">来源：{source}</font>")
        lines.append("")

    if count == 0:
        return ""

    return "\n".join(lines)


def send_markdown(content):
    if not content:
        print("markdown empty, skipped")
        return

    if not WEBHOOK:
        raise RuntimeError("REPORT_WEBHOOK is missing")

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    r = requests.post(WEBHOOK, json=payload, timeout=30)
    print("markdown status:", r.status_code)
    print("markdown response:", r.text)
    r.raise_for_status()


if __name__ == "__main__":
    send_image()

    news_items = load_news_items()
    markdown_text = build_news_markdown(news_items)
    send_markdown(markdown_text)
