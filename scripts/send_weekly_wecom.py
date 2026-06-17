import os

import json

import hashlib

import base64

import requests

from pathlib import Path

WEBHOOK = os.getenv("REPORT_WEBHOOK")

WEEKLY_URL = os.getenv("WEEKLY_URL")

SOURCE_FILE = os.getenv("SOURCE_FILE", "weekly-report.png")

SEND_FILE = os.getenv("SEND_FILE", "weekly-report-send.jpg")

def send_markdown():

    content = f"""# 📊 361°儿童行业周报

本周行业周报已生成。

👉 点击查看完整网页版：

{WEEKLY_URL}

支持查看：

• 行业事件分级

• 竞品动态

• 商品机会信号

• 热门赛道

• 原文链接跳转

👇 周报长图同步推送

"""

    data = {

        "msgtype": "markdown",

        "markdown": {

            "content": content

        }

    }

    requests.post(

        WEBHOOK,

        headers={"Content-Type": "application/json"},

        data=json.dumps(data)

    )

def compress_image():

    from PIL import Image

    img = Image.open(SOURCE_FILE).convert("RGB")

    if img.width > 1200:

        ratio = 1200 / img.width

        img = img.resize(

            (1200, int(img.height * ratio))

        )

    img.save(

        SEND_FILE,

        format="JPEG",

        quality=85,

        optimize=True

    )

def send_image():

    with open(SEND_FILE, "rb") as f:

        image_data = f.read()

    md5 = hashlib.md5(image_data).hexdigest()

    payload = {

        "msgtype": "image",

        "image": {

            "base64": base64.b64encode(image_data).decode(),

            "md5": md5

        }

    }

    requests.post(

        WEBHOOK,

        headers={"Content-Type": "application/json"},

        data=json.dumps(payload)

    )

if __name__ == "__main__":

    if not WEBHOOK:

        raise RuntimeError("REPORT_WEBHOOK missing")

    if not Path(SOURCE_FILE).exists():

        raise RuntimeError(f"{SOURCE_FILE} not found")

    send_markdown()

    compress_image()

    send_image()

    print("weekly report sent")
