import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

OUT_DIR = Path("output/weather")
OUT_FILE = OUT_DIR / "latest.json"

REGIONS = {
    "north": {
        "name": "华北/东北",
        "city": "Beijing",
        "lat": 39.9042,
        "lon": 116.4074,
    },
    "east": {
        "name": "华中/华东",
        "city": "Shanghai",
        "lat": 31.2304,
        "lon": 121.4737,
    },
    "south": {
        "name": "华南",
        "city": "Guangzhou",
        "lat": 23.1291,
        "lon": 113.2644,
    },
    "southwest": {
        "name": "西南",
        "city": "Chengdu",
        "lat": 30.5728,
        "lon": 104.0668,
    },
    "northwest": {
        "name": "西北",
        "city": "Xi'an",
        "lat": 34.3416,
        "lon": 108.9398,
    },
}

WEATHER_CODE_MAP = {
    0: "晴",
    1: "晴到多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾",
    51: "小雨",
    53: "小雨",
    55: "中雨",
    56: "冻雨",
    57: "冻雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪",
    80: "阵雨",
    81: "阵雨",
    82: "强阵雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷阵雨",
    96: "雷阵雨",
    99: "强雷阵雨",
}


def fetch_region_weather(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "wind_speed_10m_max",
        ]),
        "forecast_days": 3,
        "timezone": "Asia/Shanghai",
    }

    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def weather_text(code):
    return WEATHER_CODE_MAP.get(int(code), "多云")


def calc_risk(day):
    score = 0

    max_temp = day["temp_max"]
    rain = day["precipitation"]
    wind = day["wind"]

    if max_temp >= 35:
        score += 35
    elif max_temp >= 30:
        score += 20

    if rain >= 30:
        score += 35
    elif rain >= 10:
        score += 22
    elif rain >= 3:
        score += 12

    if wind >= 35:
        score += 15
    elif wind >= 25:
        score += 8

    code = day["code"]
    if code in [95, 96, 99]:
        score += 25
    elif code in [80, 81, 82, 61, 63, 65]:
        score += 12

    return min(score, 100)


def make_signal(day):
    max_temp = day["temp_max"]
    rain = day["precipitation"]
    wind = day["wind"]
    code = day["code"]

    if rain >= 10 or code in [80, 81, 82, 95, 96, 99]:
        return "降雨影响客流，防雨、防滑与轻防护品类需关注"

    if max_temp >= 35:
        return "高温天气明显，防晒、凉感、速干品类进入主推窗口"

    if max_temp >= 30:
        return "气温偏高，防晒、短裤、轻薄T恤需求提升"

    if wind >= 25:
        return "阵风偏强，轻外套、帽子等防护单品关注提升"

    return "天气整体平稳，户外与亲子活动具备恢复基础"


def main():
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "Open-Meteo",
        "regions": {},
    }

    for key, cfg in REGIONS.items():
        raw = fetch_region_weather(cfg["lat"], cfg["lon"])
        daily = raw.get("daily", {})

        days = []
        for i in range(3):
            day = {
                "date": daily["time"][i],
                "code": int(daily["weather_code"][i]),
                "weather": weather_text(daily["weather_code"][i]),
                "temp_max": round(float(daily["temperature_2m_max"][i]), 1),
                "temp_min": round(float(daily["temperature_2m_min"][i]), 1),
                "precipitation": round(float(daily["precipitation_sum"][i]), 1),
                "wind": round(float(daily["wind_speed_10m_max"][i]), 1),
            }
            day["risk_score"] = calc_risk(day)
            day["signal"] = make_signal(day)
            days.append(day)

        result["regions"][key] = {
            "name": cfg["name"],
            "city": cfg["city"],
            "days": days,
            "risk_score": max(d["risk_score"] for d in days),
            "signal": days[0]["signal"],
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved weather data to {OUT_FILE}")


if __name__ == "__main__":
    main()
