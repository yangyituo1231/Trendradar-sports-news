import os
import base64
import hashlib
import requests
from PIL import Image

WEBHOOK = os.getenv("REPORT_WEBHOOK")

SOURCE_FILE = "daily-report.png"
SEND_FILE = "daily-report-send.jpg"

def compress_image():
    img = Image.open(SOURCE_FILE).convert("RGB")

    # 控制宽度，避免企业微信图片过大
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
    print(r.status_code)
    print(r.text)

    r.raise_for_status()

if __name__ == "__main__":
    send_image()
