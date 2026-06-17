import os
import json
import hashlib
import base64
import requests
from pathlib import Path
from PIL import Image

WEBHOOK = os.getenv("REPORT_WEBHOOK")
WEEKLY_URL = os.getenv(
    "WEEKLY_URL",
    "https://yangyituo1231.github.io/Trendradar-sports-news/output/weekly/weekly_report.html"
)

SOURCE_FILE = os.getenv("SOURCE_FILE", "weekly-report.png")
SEND_FILE = os.getenv("SEND_FILE", "weekly-report-send.jpg")


def check_env():
    if not WEBHOOK:
        raise RuntimeError("REPORT_WEBHOOK missing")
    if not WEEKLY_URL:
        raise RuntimeError("WEEKLY_URL missing")
    if not Path(SOURCE_FILE).exists():
        raise RuntimeError(f"{SOURCE_FILE} not found")


def post_wecom(payload, name):

    resp = requests.post(
        WEBHOOK,
        headers={
            "Content-Type": "application/json; charset=utf-8"
        },
        json=payload,
        timeout=20
    )

    print(f"{name} http status: {resp.status_code}")
    print(f"{name} response: {resp.text}")

    try:
        result = resp.json()
    except Exception:
        result = {}

    if result.get("errcode") not in (0, None):
        raise RuntimeError(f"{name} failed: {result}")


def send_markdown():

    content = f"""
📊 361°儿童行业周报

点击查看完整网页版：

{WEEKLY_URL}

👇 周报长图同步推送
"""

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    post_wecom(payload, "weekly markdown")


def compress_image():
    img = Image.open(SOURCE_FILE).convert("RGB")

    if img.width > 1200:
        ratio = 1200 / img.width
        img = img.resize((1200, int(img.height * ratio)))

    quality = 85
    img.save(SEND_FILE, format="JPEG", quality=quality, optimize=True)

    # ä¼ä¸å¾®ä¿¡ç¾¤æºå¨äººå¾çéå¶éå¸¸ä¸º 2MBï¼è¿éèªå¨åå° 1.9MB ä»¥ä¸
    while Path(SEND_FILE).stat().st_size > 1900 * 1024 and quality > 45:
        quality -= 8
        img.save(SEND_FILE, format="JPEG", quality=quality, optimize=True)

    print(f"image saved: {SEND_FILE}")
    print(f"image size: {Path(SEND_FILE).stat().st_size / 1024:.1f} KB")
    print(f"image quality: {quality}")


def send_image():
    with open(SEND_FILE, "rb") as f:
        image_data = f.read()

    md5 = hashlib.md5(image_data).hexdigest()
    b64 = base64.b64encode(image_data).decode("utf-8")

    payload = {
        "msgtype": "image",
        "image": {
            "base64": b64,
            "md5": md5
        }
    }

    post_wecom(payload, "weekly image")


if __name__ == "__main__":
    check_env()
    import time

    send_markdown()

    time.sleep(2)

    compress_image()

    send_image()
    print("weekly report sent")
