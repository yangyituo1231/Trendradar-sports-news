from pathlib import Path
import json
from datetime import datetime

HISTORY_DIR = Path("output/history")
WEEKLY_DIR = Path("output/weekly")
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

history_files = sorted(HISTORY_DIR.glob("*.json"))[-7:]

if not history_files:
    print("No history data found")
    exit()

week_data = {
    "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "start_date": "",
    "end_date": "",
    "days": [],
    "top_news": [],
    "competitor_news": [],
    "keywords": [],
    "regions": [],
    "warnings": [],
    "trend_items": [],
    "weather": []
}

for file in history_files:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))

        week_data["days"].append(data.get("date", ""))

        week_data["top_news"].extend(data.get("top_news", []))
        week_data["competitor_news"].extend(data.get("competitor_news", []))
        week_data["keywords"].extend(data.get("words", []))
        week_data["regions"].append(data.get("region_reports", {}))
        week_data["warnings"].extend(data.get("warnings", []))
        week_data["trend_items"].extend(data.get("trend_items", []))
        week_data["weather"].append(data.get("weather", {}))

    except Exception as e:
        print(f"error: {file}")
        print(e)

valid_days = [d for d in week_data["days"] if d]
if valid_days:
    week_data["start_date"] = valid_days[0]
    week_data["end_date"] = valid_days[-1]

week_file = WEEKLY_DIR / "latest_week.json"
week_file.write_text(
    json.dumps(week_data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(f"weekly saved: {week_file}")
