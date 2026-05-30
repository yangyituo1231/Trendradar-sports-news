from pathlib import Path
import json
from datetime import datetime

HISTORY_DIR = Path("output/history")
WEEKLY_DIR = Path("output/weekly")

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

history_files = sorted(HISTORY_DIR.glob("*.json"))

if len(history_files) == 0:
    print("No history data found")
    exit()

week_data = {
    "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "days": [],
    "top_news": [],
    "keywords": [],
    "regions": []
}

for file in history_files[-7:]:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))

        week_data["days"].append(data.get("date"))

        week_data["top_news"].extend(
            data.get("top_news", [])
        )

        week_data["keywords"].extend(
            data.get("words", [])
        )

        week_data["regions"].append(
            data.get("region_reports", {})
        )

    except Exception as e:
        print(f"error:{file}")
        print(e)

week_file = WEEKLY_DIR / "latest_week.json"

week_file.write_text(
    json.dumps(
        week_data,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

print(f"weekly saved:{week_file}")
