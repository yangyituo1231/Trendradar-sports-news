import os
import json
import base64
import hashlib
import requests
from pathlib import Path

webhook = os.environ.get("REPORT_WEBHOOK")
img_path = Path("daily-report.png")

if not webhook:
    raise RuntimeError("REPORT_WEBHOOK is empty")

if not img_path.exists():
    raise RuntimeError("daily-report.png not found")

data = img_path.read_bytes()
img_base64 = base64.b64encode(data).decode("utf-8")
img_md5 = hashlib.md5(data).hexdigest()

payload = {
    "msgtype": "image",
    "image": {
        "base64": img_base64,
        "md5": img_md5
    }
}

resp = requests.post(webhook, json=payload, timeout=20)
print(resp.text)
resp.raise_for_status()
