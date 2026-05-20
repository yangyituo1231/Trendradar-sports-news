from playwright.sync_api import sync_playwright
import os

HTML_FILE = "daily-report-filled.html"
OUTPUT_FILE = "daily-report.png"

def generate_image():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        page = browser.new_page(
            viewport={"width": 1400, "height": 2600},
            device_scale_factor=2
        )

        file_path = f"file://{os.path.abspath(HTML_FILE)}"
        page.goto(file_path, wait_until="networkidle")

        page.evaluate("""
            document.body.style.background = '#ffffff';
            const el = document.querySelector('.page');
            if (el) {
                el.style.height = 'auto';
                el.style.maxHeight = 'none';
                el.style.overflow = 'visible';
            }
        """)

        page.locator(".page").screenshot(
            path=OUTPUT_FILE,
            type="png"
        )

        browser.close()

if __name__ == "__main__":
    generate_image()
