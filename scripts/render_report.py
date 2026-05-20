from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
import os

HTML_FILE = "daily-report-filled.html"
OUTPUT_FILE = "daily-report.png"

def trim_white(path):
    img = Image.open(path).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()

    if bbox:
        left, top, right, bottom = bbox
        pad = 20
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(img.width, right + pad)
        bottom = min(img.height, bottom + pad)
        img = img.crop((left, top, right, bottom))

    img.save(path, "PNG")

def generate_image():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        page = browser.new_page(
            viewport={"width": 1400, "height": 3200},
            device_scale_factor=2
        )

        file_path = f"file://{os.path.abspath(HTML_FILE)}"
        page.goto(file_path, wait_until="networkidle")

        page.evaluate("""
            document.body.style.background = '#ffffff';
            document.documentElement.style.height = 'auto';
            document.body.style.height = 'auto';
        """)

        page.screenshot(
            path=OUTPUT_FILE,
            full_page=True,
            type="png"
        )

        browser.close()

    trim_white(OUTPUT_FILE)

if __name__ == "__main__":
    generate_image()
