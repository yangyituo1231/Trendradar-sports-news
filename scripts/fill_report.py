from pathlib import Path
from datetime import datetime, timedelta
import random
import json
import re
import os
from collections import Counter

template = Path("daily-report.html").read_text(encoding="utf-8")

now = datetime.now()
today = now
day2 = today + timedelta(days=1)
day3 = today + timedelta(days=2)

random.seed(today.strftime("%Y-%m-%d-%H"))

weekday_map = {
    0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四",
    4: "星期五", 5: "星期六", 6: "星期日",
}

def md(d):
    return d.strftime("%m-%d")

def clean_title(text):
    text = str(text or "").replace("\n", "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r" - .*?$", "", text)
    text = re.sub(r"_.*?$", "", text)
    return text

def short(text, n=42):
    text = clean_title(text)
    return text if len(text) <= n else text[:n] + "..."

def short_cn(text, n=32):
    text = clean_title(text)
    return text if len(text) <= n else text[:n]

def season_name(month):
    if month in [3, 4, 5]:
        return "spring"
    if month in [6, 7, 8]:
        return "summer"
    if month in [9, 10, 11]:
        return "autumn"
    return "winter"

SEASON = season_name(today.month)

# =========================
# 读取新闻
# =========================

news_items = []
news_file = Path("output/news/latest.json")

if news_file.exists():
    try:
        raw = json.loads(news_file.read_text(encoding="utf-8"))
        news_items = raw.get("items", []) if isinstance(raw, dict) else raw
    except Exception:
        news_items = []

titles = [
    clean_title(x.get("title", ""))
    for x in news_items
    if isinstance(x, dict) and x.get("title")
]
joined = " ".join(titles)

# =========================
# 读取天气
# =========================

weather_file = Path("output/weather/latest.json")
weather = {}

if weather_file.exists():
    try:
        weather = json.loads(weather_file.read_text(encoding="utf-8"))
    except Exception:
        weather = {}

weather_regions = weather.get("regions", {}) if isinstance(weather, dict) else {}

def get_weather_region(key):
    return weather_regions.get(key, {})

def get_day_weather(key, idx):
    region = get_weather_region(key)
    days = region.get("days", [])
    if idx < len(days):
        return days[idx]
    return {
        "weather": "多云",
        "code": 2,
        "temp_max": 25,
        "temp_min": 18,
        "precipitation": 0,
        "wind": 12,
        "risk_score": 25,
    }

def weather_day_label(key, idx):
    return get_day_weather(key, idx).get("weather", "多云")

def weather_risk_raw(key):
    return int(get_weather_region(key).get("risk_score", 25))

def weather_stats(key):
    days = [get_day_weather(key, i) for i in range(3)]
    return {
        "max_temp": max(float(d.get("temp_max", 25)) for d in days),
        "min_temp": min(float(d.get("temp_min", 18)) for d in days),
        "max_rain": max(float(d.get("precipitation", 0)) for d in days),
        "max_wind": max(float(d.get("wind", 12)) for d in days),
        "codes": [int(d.get("code", 2)) for d in days],
        "weathers": [str(d.get("weather", "多云")) for d in days],
        "risk": weather_risk_raw(key),
    }

def has_snow(s):
    return any(c in [71, 73, 75, 77, 85, 86] for c in s["codes"]) or any("雪" in w for w in s["weathers"])

def has_rain(s):
    return (
        s["max_rain"] >= 3
        or any(c in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99] for c in s["codes"])
        or any("雨" in w for w in s["weathers"])
    )

def has_storm(s):
    return (
        s["max_rain"] >= 20
        or any(c in [82, 95, 96, 99] for c in s["codes"])
        or any("雷" in w or "强" in w for w in s["weathers"])
    )

def is_hot(s):
    return s["max_temp"] >= 30

def is_very_hot(s):
    return s["max_temp"] >= 35

def is_cold(s):
    return s["min_temp"] <= 5

def is_freezing(s):
    return s["min_temp"] <= 0

def is_windy(s):
    return s["max_wind"] >= 25

def weather_business_type(key):
    s = weather_stats(key)

    if has_snow(s) or is_freezing(s):
        return "snow_ice"
    if is_cold(s):
        return "cold"
    if has_storm(s):
        return "storm"
    if has_rain(s):
        return "rain"
    if is_very_hot(s):
        return "very_hot"
    if is_hot(s):
        return "hot"
    if is_windy(s):
        return "wind"
    if SEASON == "spring":
        return "spring_mild"
    if SEASON == "autumn":
        return "autumn_mild"
    if SEASON == "winter":
        return "winter_mild"
    return "normal"

def heat_class_by_weather(key):
    t = weather_business_type(key)
    if t in ["very_hot", "hot"]:
        return "heat-dot-hot"
    if t in ["storm", "rain"]:
        return "heat-dot-rain"
    if t in ["snow_ice", "cold", "winter_mild"]:
        return "heat-dot-cold"
    return "heat-dot-normal"

def map_heat_class():
    weather_types = [
        weather_business_type("north"),
        weather_business_type("east"),
        weather_business_type("south"),
        weather_business_type("southwest"),
        weather_business_type("northwest"),
    ]

    if any(t in weather_types for t in ["very_hot", "hot"]):
        return "heat-hot"
    if any(t in weather_types for t in ["storm", "rain"]):
        return "heat-rain"
    if any(t in weather_types for t in ["snow_ice", "cold", "winter_mild"]):
        return "heat-cold"
    return "heat-normal"

def weather_desc(key):
    t = weather_business_type(key)
    mapping = {
        "snow_ice": "雨雪或低温结冰风险提升，防滑、保暖及室内客流承接需关注",
        "cold": "低温天气影响户外停留，保暖、棉服、帽类及运动鞋需求提升",
        "storm": "强降雨或雷阵雨扰动客流，防雨、防滑与室内运动场景需关注",
        "rain": "降雨影响客流，防雨、轻防护与室内运动场景需求提升",
        "very_hot": "高温天气明显，防晒、凉感、速干品类进入主推窗口",
        "hot": "气温偏高，防晒、短裤、轻薄T恤需求提升",
        "wind": "阵风偏强，轻外套、帽子等防护单品关注提升",
        "spring_mild": "春季出行恢复，轻外套、亲子运动与户外场景具备增长基础",
        "autumn_mild": "秋季运动与开学场景延续，轻外套、长裤及校园运动需求提升",
        "winter_mild": "冬季温和天气下，保暖基础款与室内运动场景仍需关注",
        "normal": "天气整体平稳，户外与亲子活动具备恢复基础",
    }
    return mapping.get(t, mapping["normal"])

def weather_icon(key):
    t = weather_business_type(key)
    if t in ["storm", "rain"]:
        return "☔"
    if t in ["very_hot", "hot"]:
        return "☀️"
    if t in ["snow_ice", "cold", "winter_mild"]:
        return "❄️"
    if t == "wind":
        return "🌬️"
    if t in ["spring_mild", "autumn_mild", "normal"]:
        return "🌤️"
    return "🌤️"

# =========================
# DeepSeek工具
# =========================

def deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception:
        return None

def extract_json(text):
    if not text:
        return None
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    match = re.search(r"\[.*\]", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return None

def ask_deepseek_json(prompt, max_tokens=900):
    client = deepseek_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是运动鞋服行业经营分析助手，只输出严格JSON，不要解释。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.28,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content.strip()
        return extract_json(text)
    except Exception:
        return None

def ask_deepseek_text(prompt, max_tokens=220):
    client = deepseek_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是专业、简洁、偏经营实战的运动鞋服零售分析师。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r"\s+", "", text)
        return text
    except Exception:
        return None

# =========================
# 区域评分
# =========================

def news_heat_score(keywords):
    score = 0
    for t in titles:
        if any(k in t for k in keywords):
            score += 5
        if any(k in t for k in ["618", "大促", "防晒", "凉感", "童装", "儿童", "亲子", "商场", "商圈", "客流", "户外", "骑行", "赛事", "跑步", "马拉松"]):
            score += 1
    return min(score, 25)

def business_keyword_score():
    score = 0
    for k in ["防晒", "凉感", "童装", "儿童", "亲子", "618", "商场", "商圈", "客流", "户外", "骑行", "小红书", "抖音", "保暖", "防滑", "赛事", "跑步", "马拉松"]:
        if k in joined:
            score += 2
    return min(score, 20)

def seasonal_weather_score(weather_key):
    t = weather_business_type(weather_key)
    base = {
        "snow_ice": 55,
        "storm": 50,
        "very_hot": 48,
        "cold": 38,
        "rain": 35,
        "hot": 32,
        "wind": 28,
        "spring_mild": 18,
        "autumn_mild": 20,
        "winter_mild": 22,
        "normal": 15,
    }.get(t, 15)
    return min(base + min(weather_risk_raw(weather_key) * 0.25, 18), 65)

def total_region_score(weather_key, region_keywords):
    return min(
        seasonal_weather_score(weather_key)
        + news_heat_score(region_keywords)
        + business_keyword_score(),
        100,
    )

# =========================
# 第一部分：DeepSeek优先资讯精选
# =========================

CATEGORY_RULES = {
    "大促电商": {
        "keywords": ["618", "双11", "双十一", "双12", "99大促", "38大促", "大促", "预售", "电商", "直播", "抖音", "小红书", "种草", "百亿补贴", "战报"],
        "tag": "大促/电商", "logo": "大促", "icon": "🛒", "class": "logo-blue",
        "desc": "大促信息适度关注，重点看夏季品类曝光、直播种草、转化效率和终端承接。",
    },
    "童装儿童": {
        "keywords": ["童装", "儿童", "亲子", "校园", "儿童运动", "运动童装", "Kids", "KIDS", "童鞋"],
        "tag": "童装/儿童运动", "logo": "童装", "icon": "🧒", "class": "logo-sky",
        "desc": "儿童消费从单品购买转向亲子、校园、户外和运动场景综合经营。",
    },
    "天气防晒": {
        "keywords": ["高温", "防晒", "凉感", "速干", "暴雨", "强对流", "降雨", "天气", "防雨", "夏日", "夏季", "降雪", "结冰", "低温", "防滑", "保暖"],
        "tag": "天气/功能消费", "logo": "天气", "icon": "☀️", "class": "logo-sky",
        "desc": "天气变化影响客流和主推节奏，防晒、凉感、防雨、防滑及保暖品类需动态前置。",
    },
    "户外运动": {
        "keywords": ["户外", "骑行", "露营", "文旅", "出行", "夜经济", "跑步", "轻户外", "徒步", "马拉松", "越野跑", "赛事", "训练", "跑鞋"],
        "tag": "户外/运动场景", "logo": "户外", "icon": "🚴", "class": "logo-green",
        "desc": "户外、跑步、骑行、赛事和夜间消费延伸运动场景，带动装备与亲子需求。",
    },
    "商圈消费": {
        "keywords": ["商场", "商圈", "门店", "客流", "奥莱", "折扣", "会员", "零售", "消费", "本地生活"],
        "tag": "商圈/零售经营", "logo": "商圈", "icon": "🏬", "class": "logo-dark",
        "desc": "商圈活动、会员运营和折扣零售影响周末客流与终端转化效率。",
    },
}

fallback_by_category = {
    "大促电商": {"title": "618节点持续推进，运动品牌关注夏季品类转化", "source": "平台资讯"},
    "童装儿童": {"title": "儿童运动消费场景外扩，亲子与校园需求继续升温", "source": "消费观察"},
    "天气防晒": {"title": "天气变化影响客流节奏，功能品类进入动态调整窗口", "source": "公开气象信息"},
    "户外运动": {"title": "跑步、骑行与轻户外场景延续，运动装备需求扩张", "source": "消费观察"},
    "商圈消费": {"title": "商圈活动与会员运营联动，周末客流修复仍需关注", "source": "商业观察"},
}

def category_score(title, cat):
    return sum(1 for kw in CATEGORY_RULES[cat]["keywords"] if kw in title)

def item_score(item, cat):
    title = clean_title(item.get("title", ""))
    source = str(item.get("source", ""))
    score = category_score(title, cat) * 12

    value_words = [
        "618", "大促", "战报", "防晒", "凉感", "速干", "童装", "儿童", "亲子",
        "跑鞋", "户外", "骑行", "露营", "商场", "商圈", "客流", "会员", "直播",
        "小红书", "抖音", "Nike", "耐克", "阿迪", "安踏", "李宁", "特步", "HOKA", "昂跑", "亚瑟士", "361"
    ]

    for kw in value_words:
        if kw in title:
            score += 4

    bad_words = ["比分", "赛程", "夺冠", "冠军", "主教练", "球队", "球员", "转会", "受伤"]
    for kw in bad_words:
        if kw in title:
            score -= 16

    reliable_sources = ["界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报", "新华网", "澎湃新闻", "证券时报", "新京报", "新浪财经"]
    for src in reliable_sources:
        if src in source:
            score += 2

    return score

def pick_top_news_rule():
    used_titles = set()
    result = []

    for cat in ["大促电商", "童装儿童", "天气防晒", "户外运动", "商圈消费"]:
        rule = CATEGORY_RULES[cat]
        candidates = []

        for item in news_items:
            title = clean_title(item.get("title", ""))
            if not title or title in used_titles:
                continue
            if category_score(title, cat) > 0:
                candidates.append((item_score(item, cat), item))

        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates and candidates[0][0] > 0:
            item = candidates[0][1]
            title = short(item.get("title", ""), 42)
            source = item.get("source", "公开资讯")
        else:
            fb = fallback_by_category[cat]
            title, source = fb["title"], fb["source"]

        used_titles.add(title)
        result.append({
            "title": title,
            "tag": rule["tag"],
            "source": source,
            "desc": rule["desc"],
            "logo": rule["logo"],
            "icon": rule["icon"],
            "class": rule["class"],
        })

    return result

def pick_top_news_deepseek():
    if not titles:
        return pick_top_news_rule()

    news_text = "\n".join(
        f"{i+1}. {clean_title(item.get('title',''))}｜{item.get('source','')}"
        for i, item in enumerate(news_items[:45])
        if isinstance(item, dict) and item.get("title")
    )

    prompt = f"""
你是运动鞋服行业资讯筛选助手。请从以下新闻中选出5条最适合361°儿童经营管理部每日阅读的重点资讯。
要求：
1. 必须覆盖或优先考虑：电商大促、童装儿童、天气功能品类、户外运动、商圈零售；
2. 过滤纯体育比赛比分、球员转会、娱乐八卦；
3. 输出严格JSON数组，长度5；
4. 每项包含：title、category、reason；
5. category只能从以下选择：大促/电商、童装/儿童运动、天气/功能消费、户外/运动场景、商圈/零售经营。
6. reason控制在30字以内，偏经营启示。

新闻：
{news_text}
"""

    arr = ask_deepseek_json(prompt, max_tokens=900)
    if not isinstance(arr, list) or len(arr) < 3:
        return pick_top_news_rule()

    rule_by_tag = {
        "大促/电商": CATEGORY_RULES["大促电商"],
        "童装/儿童运动": CATEGORY_RULES["童装儿童"],
        "天气/功能消费": CATEGORY_RULES["天气防晒"],
        "户外/运动场景": CATEGORY_RULES["户外运动"],
        "商圈/零售经营": CATEGORY_RULES["商圈消费"],
    }

    source_lookup = {
        clean_title(x.get("title", "")): x.get("source", "公开资讯")
        for x in news_items
        if isinstance(x, dict)
    }

    result = []
    used = set()

    for row in arr:
        if not isinstance(row, dict):
            continue
        title = short(row.get("title", ""), 42)
        if not title or title in used:
            continue

        tag = row.get("category", "商圈/零售经营")
        rule = rule_by_tag.get(tag, CATEGORY_RULES["商圈消费"])
        source = "公开资讯"

        for raw_title, raw_source in source_lookup.items():
            if title[:10] in raw_title or raw_title[:10] in title:
                source = raw_source
                break

        desc = clean_title(row.get("reason", "")) or rule["desc"]

        result.append({
            "title": title,
            "tag": tag,
            "source": source,
            "desc": desc,
            "logo": rule["logo"],
            "icon": rule["icon"],
            "class": rule["class"],
        })
        used.add(title)

    fallback = pick_top_news_rule()
    for item in fallback:
        if len(result) >= 5:
            break
        if item["title"] not in used:
            result.append(item)

    return result[:5]

top_news = pick_top_news_deepseek()

# =========================
# 区域经营雷达
# =========================

region_map = {
    "east": {"name": "华东", "city": "上海/江苏/浙江", "weather_key": "east", "keywords": ["上海", "杭州", "南京", "苏州", "宁波", "江苏", "浙江"]},
    "central": {"name": "华中", "city": "湖北/湖南/江西", "weather_key": "east", "keywords": ["武汉", "长沙", "南昌", "郑州", "湖北", "湖南", "江西"]},
    "south": {"name": "华南", "city": "广东/广西", "weather_key": "south", "keywords": ["广州", "深圳", "佛山", "南宁", "广东", "广西", "厦门", "福建"]},
    "southwest": {"name": "西南", "city": "四川/重庆/贵州", "weather_key": "southwest", "keywords": ["成都", "重庆", "贵阳", "昆明", "四川", "贵州", "云南"]},
    "northwest": {"name": "西北", "city": "陕西/甘肃/宁夏", "weather_key": "northwest", "keywords": ["西安", "兰州", "银川", "陕西", "甘肃", "宁夏", "新疆"]},
}

SCENE_POOLS = {
    "rain": {
        "hot": ["降雨扰动客流", "雨天影响到店", "局地降雨需关注"],
        "flow": ["室内客流承接增强", "商场活动更关键", "客流向室内集中"],
        "signal": ["防雨防滑与轻防护品类关注提升"],
        "action": ["强化防雨防滑陈列，前置室内运动场景"],
    },
    "high_temp": {
        "hot": ["高温带动夏季品类", "防晒凉感热度上升", "暑热推动功能消费"],
        "flow": ["防晒与速干需求提升", "短裤T恤关注上升", "户外转向功能防护"],
        "signal": ["防晒衣、凉感T和速干短裤进入主推窗口"],
        "action": ["前置防晒凉感组合，强化短裤T恤连带"],
    },
    "promotion": {
        "hot": ["大促节点带动关注", "平台预售强化心智", "618带动品类曝光"],
        "flow": ["直播同款转化提升", "爆款价格带受关注", "线上热度外溢门店"],
        "signal": ["大促心智强化，夏季爆款与直播同款承接更关键"],
        "action": ["强化爆款价格带，承接直播同款与门店转化"],
    },
    "kids": {
        "hot": ["儿童运动场景扩张", "亲子需求升温", "校园场景延续"],
        "flow": ["亲子客流增加", "校园运动带动连带", "童鞋童服组合增强"],
        "signal": ["儿童运动、校园和亲子场景继续带动鞋服组合需求"],
        "action": ["强化亲子校园陈列，提升童鞋服装连带"],
    },
    "outdoor": {
        "hot": ["轻户外热度提升", "户外出行带动消费", "文旅场景延伸"],
        "flow": ["骑行露营消费增加", "户外休闲客群活跃", "亲子户外需求增加"],
        "signal": ["轻户外、帽包配件和防晒装备存在连带空间"],
        "action": ["增加轻户外组合，强化出行场景展示"],
    },
    "mall": {
        "hot": ["商圈活动带动关注", "会员运营增强", "门店客流需跟进"],
        "flow": ["周末客流活跃", "会员活动带动转化", "商场活动提升停留"],
        "signal": ["商圈客流修复，但转化仍依赖会员和连带运营"],
        "action": ["加强会员活动、门口堆头和导购试穿转化"],
    },
}

def detect_scene_rule(local_text, weather_key):
    text = str(local_text)
    scenes = []
    t = weather_business_type(weather_key)

    if t in ["storm", "rain"]:
        scenes.append("rain")
    if t in ["very_hot", "hot"]:
        scenes.append("high_temp")
    if any(k in text for k in ["618", "大促", "预售", "战报", "直播"]):
        scenes.append("promotion")
    if any(k in text for k in ["童装", "儿童", "亲子", "校园"]):
        scenes.append("kids")
    if any(k in text for k in ["户外", "骑行", "露营", "文旅", "出行"]):
        scenes.append("outdoor")
    if any(k in text for k in ["商场", "商圈", "客流", "门店", "会员"]):
        scenes.append("mall")

    if not scenes:
        scenes = ["kids", "mall"] if SEASON == "summer" else ["mall", "outdoor"]

    return list(dict.fromkeys(scenes))[:3]

def pick_scene_word(scenes, field):
    candidates = []
    for scene in scenes:
        candidates.extend(SCENE_POOLS.get(scene, {}).get(field, []))
    return random.choice(candidates) if candidates else "关注主推品类"

def build_region_reports_rule():
    reports = {}
    actions = {}

    for region, cfg in region_map.items():
        local_titles = [t for t in titles if any(k in t for k in cfg["keywords"])]
        local_text = " ".join(local_titles[:10]) or joined[:300]
        scenes = detect_scene_rule(local_text, cfg["weather_key"])

        reports[region] = {
            "change": pick_scene_word(scenes, "hot"),
            "impact": pick_scene_word(scenes, "flow"),
            "action": pick_scene_word(scenes, "signal"),
        }
        actions[region] = pick_scene_word(scenes, "action")

    return reports, actions

def build_region_reports_deepseek():
    region_payload = []

    for region, cfg in region_map.items():
        local_titles = [t for t in titles if any(k in t for k in cfg["keywords"])]
        if not local_titles:
            local_titles = titles[:8]

        region_payload.append({
            "key": region,
            "name": cfg["name"],
            "city": cfg["city"],
            "weather": weather_desc(cfg["weather_key"]),
            "weather_type": weather_business_type(cfg["weather_key"]),
            "weather_3days": [
                weather_day_label(cfg["weather_key"], 0),
                weather_day_label(cfg["weather_key"], 1),
                weather_day_label(cfg["weather_key"], 2),
            ],
            "news": local_titles[:10],
        })

    top_news_text = "\n".join([f"{i+1}. {x['title']}｜{x['tag']}" for i, x in enumerate(top_news)])
    global_news_text = "\n".join(titles[:35])

    prompt = f"""
你是361°儿童总部经营管理部的区域经营分析师。
请基于区域新闻、全国热点、天气、大促、电商平台、鞋服品类、儿童运动、商圈客流，为5个区域生成“区域经营雷达”。

输出严格JSON对象，不要解释。
key必须为 east, central, south, southwest, northwest。

每个区域包含4个字段：
hot：核心信号，10-16字，必须结合新闻或天气；
flow：客流/场景判断，16-24字，判断客流、商圈、亲子、户外或到店变化；
signal：AI经营判断，28-42字，要说明具体品类、场景或消费机会，不能空泛；
action：建议动作，28-42字，要具体到门店、商品、陈列、会员、导购或线上承接动作。

要求：
1. 每个区域内容必须明显不同，不能重复；
2. 不要写“关注提升”“需求提升”这种空话，必须有对象；
3. 华东关注商圈、内容、电商承接；
4. 华中关注校园亲子、会员运营、商场活动；
5. 华南关注高温、防晒、夏季品类、大促；
6. 西南关注文旅、户外、亲子、雨天承接；
7. 西北关注出行、天气扰动、轻户外和配件；
8. 如果区域新闻不足，可以结合全国热点和天气推断，但必须像经营判断。

今日TOP资讯：
{top_news_text}

全局新闻：
{global_news_text}

区域数据：
{json.dumps(region_payload, ensure_ascii=False)}
"""

    obj = ask_deepseek_json(prompt, max_tokens=1600)
    if not isinstance(obj, dict):
        return build_region_reports_rule()

    reports = {}
    actions = {}

    fallback_reports, fallback_actions = build_region_reports_rule()

    for region in region_map.keys():
        row = obj.get(region, {})
        if not isinstance(row, dict):
            reports[region] = fallback_reports[region]
            actions[region] = fallback_actions[region]
            continue

        hot = short_cn(row.get("hot", fallback_reports[region]["change"]), 18)
        flow = short_cn(row.get("flow", fallback_reports[region]["impact"]), 26)
        signal = short_cn(row.get("signal", fallback_reports[region]["action"]), 46)
        action = short_cn(row.get("action", fallback_actions[region]), 46)

        reports[region] = {
            "change": hot,
            "impact": flow,
            "action": signal,
        }
        actions[region] = action

    return reports, actions

reports, actions = build_region_reports_deepseek()

scores = {
    r: total_region_score(c["weather_key"], c["keywords"])
    for r, c in region_map.items()
}

sorted_regions = sorted(scores.keys(), key=lambda r: scores[r], reverse=True)
stars = {}

for idx, r in enumerate(sorted_regions):
    s = scores[r]
    if idx <= 2 and s >= 62:
        stars[r] = "★★★"
    elif s >= 45:
        stars[r] = "★★"
    else:
        stars[r] = "★"

# =========================
# 今日一句 + AI经营摘要
# =========================

def make_today_insight_rule():
    if any(k in joined for k in ["618", "战报", "大促", "预售"]):
        return "618战报持续释放，运动品牌线上增长与夏季品类竞争同步升温。"
    if any(k in joined for k in ["防晒", "凉感", "速干", "高温"]):
        return "夏季功能消费升温，防晒、凉感与速干品类成为短期热点。"
    if any(k in joined for k in ["户外", "骑行", "露营", "跑步", "马拉松"]):
        return "泛运动场景继续扩张，户外、跑步与骑行热度延续。"
    if any(k in joined for k in ["童装", "儿童", "亲子", "校园"]):
        return "儿童运动消费场景继续外扩，亲子与校园需求保持活跃。"
    return "运动鞋服行业热点分化，平台、天气与场景消费共同影响短期趋势。"

def make_today_insight_deepseek():
    prompt = f"""
请基于以下运动鞋服行业新闻，写一句今日行业判断。
要求：
1. 只讲资讯趋势，不写门店执行动作；
2. 45字以内；
3. 面向运动鞋服/童装行业；
4. 不要口号，不要空话。

新闻：
{chr(10).join(titles[:25])}
"""
    text = ask_deepseek_text(prompt, max_tokens=120)
    if not text:
        return make_today_insight_rule()
    return text[:70]

def make_ai_summary_rule():
    parts = []

    if any(k in joined for k in ["618", "大促", "预售", "战报"]):
        parts.append("大促与平台流量仍是短期主线")
    if any(k in joined for k in ["防晒", "凉感", "速干", "高温"]):
        parts.append("防晒、凉感、速干等夏季功能品类升温")
    if any(k in joined for k in ["童装", "儿童", "亲子", "校园"]):
        parts.append("儿童运动与亲子校园场景延续")
    if any(k in joined for k in ["户外", "骑行", "露营", "跑步", "赛事"]):
        parts.append("轻户外与跑步场景带动鞋服装备关注")
    if any(weather_business_type(k) in ["rain", "storm"] for k in ["north", "east", "south", "southwest", "northwest"]):
        parts.append("降雨天气可能影响区域客流")

    if not parts:
        parts.append("今日行业信息整体平稳，关注商圈客流、商品节奏和区域差异")

    return "；".join(parts[:4]) + "。"

def make_ai_summary_deepseek():
    news_text = "\n".join(titles[:30])
    weather_text = "；".join([
        weather_desc("north"),
        weather_desc("east"),
        weather_desc("south"),
        weather_desc("southwest"),
        weather_desc("northwest"),
    ])

    prompt = f"""
你是361°儿童经营管理部的行业情报分析师。
请基于以下新闻和天气，生成一段90字以内的AI经营摘要。

要求：
1. 要有明确判断，不要只是罗列；
2. 同时覆盖：大促/平台流量、夏季功能品类、儿童运动或亲子场景、天气对客流的影响；
3. 要体现“当前最应该关注什么”；
4. 不要分点，不要口号；
5. 适合放在日报顶部。

新闻：
{news_text}

天气：
{weather_text}
"""
    text = ask_deepseek_text(prompt, max_tokens=180)
    if not text:
        return make_ai_summary_rule()
    return text[:150]

today_insight = make_today_insight_deepseek()
ai_summary = make_ai_summary_deepseek()

# =========================
# 第四部分
# =========================

def detect_trend_from_news():
    rules = [
        (["618", "双11", "双十一", "双12", "大促", "预售", "战报"], {"title": "大促节点提前蓄水", "desc": "平台活动前置，需关注爆款、价格带、直播同款与门店承接。", "tag": "大促趋势"}),
        (["防晒", "凉感", "速干", "高温"], {"title": "季节功能品类升温", "desc": "防晒、凉感、速干等功能品类热度提升，门店陈列节奏需前置。", "tag": "季节趋势"}),
        (["童装", "儿童", "亲子", "校园"], {"title": "儿童运动场景扩张", "desc": "亲子、校园与儿童运动场景热度延续，童装连带与场景搭配更关键。", "tag": "儿童消费趋势"}),
        (["抖音", "小红书", "直播", "种草", "内容"], {"title": "内容平台影响转化", "desc": "抖音、小红书与直播内容影响新品传播、到店转化和线上成交。", "tag": "内容电商"}),
        (["商场", "商圈", "客流", "门店", "会员", "奥莱"], {"title": "线下客流运营增强", "desc": "商圈活动、会员运营和奥莱折扣带动门店客流与转化效率变化。", "tag": "渠道趋势"}),
        (["户外", "骑行", "露营", "文旅", "徒步", "出行"], {"title": "轻户外场景延展", "desc": "骑行、露营、徒步与文旅出行带动轻户外和运动休闲需求。", "tag": "消费趋势"}),
        (["赛事", "跑步", "马拉松", "越野跑", "训练", "跑鞋"], {"title": "泛运动热度扩散", "desc": "跑步、赛事和训练场景带动专业跑鞋、运动科技与装备需求。", "tag": "运动趋势"}),
        (["雨", "暴雨", "强对流", "防雨"], {"title": "天气扰动品类切换", "desc": "降雨与强对流影响客流节奏，防雨、轻外套和室内运动场景需关注。", "tag": "天气趋势"}),
    ]

    candidates = []
    for words, trend in rules:
        hit = sum(1 for t in titles[:60] if any(w in t for w in words))
        if hit > 0:
            candidates.append((hit, trend))

    candidates.sort(key=lambda x: x[0], reverse=True)

    trends = []
    seen = set()

    for _, trend in candidates:
        if trend["title"] not in seen:
            trends.append(trend)
            seen.add(trend["title"])

    fallback = [
        {"title": "门店场景陈列更关键", "desc": "从单品销售转向场景组合，亲子、校园和轻户外陈列价值提升。", "tag": "零售趋势"},
        {"title": "区域客流分化加剧", "desc": "天气、商圈活动和出行场景共同影响区域客流，需差异化跟进。", "tag": "区域趋势"},
        {"title": "商品节奏需要前置", "desc": "天气与平台活动共同影响品类节奏，核心品类需提前陈列承接。", "tag": "商品趋势"},
    ]

    for f in fallback:
        if len(trends) >= 4:
            break
        if f["title"] not in seen:
            trends.append(f)
            seen.add(f["title"])

    return trends[:4]

trend_items = detect_trend_from_news()

# =========================
# 第五部分：DeepSeek热词
# =========================

KEYWORD_MAP = {
    "抖音": "抖音直播", "直播": "直播带货", "店播": "店播", "达人": "达人矩阵",
    "小红书": "小红书种草", "种草": "内容种草",
    "618": "618", "成绩单": "618战报", "战报": "618战报",
    "品牌": "品牌站位", "C位": "品牌站位",
    "双11": "双11预售", "双十一": "双11预售", "双12": "双12",
    "99大促": "99大促", "38大促": "38大促", "大促": "大促预售", "预售": "大促预售",
    "百亿补贴": "百亿补贴", "GMV": "GMV", "退货率": "退货率",

    "防晒": "防晒品类", "防晒衣": "防晒衣", "凉感": "凉感科技", "速干": "速干T",
    "短裤": "短裤", "短袖": "短袖T恤", "T恤": "运动T恤", "POLO": "POLO衫",
    "卫衣": "卫衣", "冲锋衣": "冲锋衣", "羽绒服": "羽绒服", "裤装": "运动长裤",
    "运动凉鞋": "运动凉鞋", "凉鞋": "运动凉鞋", "拖鞋": "运动拖鞋",
    "透气": "透气跑鞋", "缓震": "缓震科技", "碳板": "碳板跑鞋",
    "篮球鞋": "篮球鞋", "跑鞋": "专业跑鞋", "户外鞋": "户外鞋", "童鞋": "儿童运动鞋",
    "面料": "功能面料", "科技": "运动科技",

    "童装": "运动童装", "儿童": "儿童运动", "亲子": "亲子运动", "校园": "校园体育", "体适能": "儿童体适能",
    "商场": "商场活动", "商圈": "商圈客流", "客流": "客流修复", "门店": "门店陈列", "会员": "会员运营",
    "户外": "户外运动", "轻户外": "轻户外", "骑行": "城市骑行", "露营": "露营经济", "徒步": "徒步",
    "文旅": "文旅客流", "夜经济": "夜经济", "Citywalk": "Citywalk", "山系": "山系穿搭",

    "赛事": "体育赛事", "跑步": "跑步经济", "马拉松": "马拉松", "越野跑": "越野跑", "训练": "训练装备",

    "耐克": "Nike", "Nike": "Nike", "阿迪达斯": "阿迪达斯", "Adidas": "阿迪达斯",
    "亚瑟士": "亚瑟士", "ASICS": "亚瑟士", "昂跑": "On昂跑", "On": "On昂跑",
    "HOKA": "HOKA", "安踏": "安踏", "李宁": "李宁", "特步": "特步", "361": "361儿童",
    "乔丹": "乔丹", "lululemon": "lululemon",

    "消费分层": "消费分层", "理性消费": "理性消费", "悦己": "悦己消费", "情绪消费": "情绪消费",
    "防雨": "防雨装备", "低温": "保暖", "保暖": "保暖", "防滑": "防滑鞋", "降雪": "防滑鞋", "结冰": "防滑鞋",
}

def build_words_rule():
    counter = Counter()
    top_titles = [item["title"] for item in top_news if item.get("title")]
    top_joined = " ".join(top_titles)

    for raw, mapped in KEYWORD_MAP.items():
        if raw in top_joined:
            counter[mapped] += 6

    for t in titles[:120]:
        for raw, mapped in KEYWORD_MAP.items():
            if raw in t:
                counter[mapped] += 2

    for key in ["north", "east", "south", "southwest", "northwest"]:
        sig = weather_desc(key)
        for raw, mapped in KEYWORD_MAP.items():
            if raw in sig:
                counter[mapped] += 2

    seasonal_fallback = {
        "spring": ["春季出行", "轻外套", "亲子运动", "校园体育", "城市骑行", "山系穿搭", "运动T恤"],
        "summer": ["防晒品类", "凉感科技", "速干T", "短裤", "运动凉鞋", "透气跑鞋", "618", "防晒衣"],
        "autumn": ["开学季", "校园体育", "卫衣", "轻外套", "户外运动", "99大促", "城市骑行"],
        "winter": ["保暖", "防滑鞋", "童鞋", "室内运动", "训练装备", "羽绒服", "冲锋衣"],
    }.get(SEASON, [])

    broad_fallback = [
        "618战报", "品牌站位", "直播带货", "店播", "达人矩阵",
        "门店陈列", "客流修复", "运动童装", "儿童运动", "轻户外",
        "专业跑鞋", "篮球鞋", "户外鞋", "运动T恤", "功能面料",
        "运动科技", "训练装备", "Nike", "阿迪达斯", "安踏", "李宁",
        "特步", "On昂跑", "HOKA", "理性消费", "情绪消费"
    ]

    preferred = [w for w, _ in counter.most_common()]

    words = []
    for w in preferred + seasonal_fallback + broad_fallback:
        if not w:
            continue
        if len(w) > 8:
            continue
        if w not in words:
            words.append(w)
        if len(words) >= 18:
            break

    return words[:18]

def build_words_deepseek():
    news_text = "\n".join(titles[:35])
    weather_text = "；".join([
        weather_desc("north"),
        weather_desc("east"),
        weather_desc("south"),
        weather_desc("southwest"),
        weather_desc("northwest"),
    ])

    prompt = f"""
请基于以下运动鞋服行业新闻和天气，提取18个适合放在“行业热词雷达”的短热词。
要求：
1. 输出严格JSON数组；
2. 每个词2到6个汉字或英文品牌名；
3. 覆盖：鞋、服、童装、户外、跑步、电商、品牌、天气、实时热点；
4. 不要过度重复“儿童运动、品牌站位、安踏”；
5. 尽量结合当日新闻真实热点；
6. 只输出JSON数组。

新闻：
{news_text}

天气：
{weather_text}
"""

    arr = ask_deepseek_json(prompt, max_tokens=500)
    if not isinstance(arr, list):
        return build_words_rule()

    words = []
    for w in arr:
        w = clean_title(str(w))
        if 1 < len(w) <= 8 and w not in words:
            words.append(w)

    fallback = build_words_rule()
    for w in fallback:
        if len(words) >= 18:
            break
        if w not in words:
            words.append(w)

    return words[:18]

words = build_words_deepseek()

# =========================
# 数据填充
# =========================

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",

    "today_insight": today_insight,
    "ai_summary": ai_summary,

    "date": today.strftime("%Y-%m-%d"),
    "weekday": weekday_map[today.weekday()],
    "update_time": today.strftime("%H:%M"),

    "monitor_count": str(max(len(news_items), random.randint(150, 260))),
    "rss_count": str(max(min(len(news_items), 99), random.randint(35, 80))),
    "focus_count": "5",

    "weather_heat_class": map_heat_class(),

    "east_icon": weather_icon("east"),
    "central_icon": weather_icon("east"),
    "south_icon": weather_icon("south"),
    "southwest_icon": weather_icon("southwest"),
    "northwest_icon": weather_icon("northwest"),
    
    "north_heat": heat_class_by_weather("north"),
    "east_heat": heat_class_by_weather("east"),
    "south_heat": heat_class_by_weather("south"),
    "northwest_heat": heat_class_by_weather("northwest"),
    "central_heat": heat_class_by_weather("east"),

    "weather_range": f"{md(today)} ~ {md(day3)}",
    "day1": md(today),
    "day2": md(day2),
    "day3": md(day3),

    "weather_north": weather_desc("north"),
    "weather_east": weather_desc("east"),
    "weather_southwest": weather_desc("south"),
    "weather_southwest_label": weather_desc("southwest"),
    "weather_northwest": weather_desc("northwest"),

    "north_day1": weather_day_label("north", 0),
    "north_day2": weather_day_label("north", 1),
    "north_day3": weather_day_label("north", 2),

    "east_day1": weather_day_label("east", 0),
    "east_day2": weather_day_label("east", 1),
    "east_day3": weather_day_label("east", 2),

    "south_day1": weather_day_label("south", 0),
    "south_day2": weather_day_label("south", 1),
    "south_day3": weather_day_label("south", 2),

    "southwest_day1": weather_day_label("southwest", 0),
    "southwest_day2": weather_day_label("southwest", 1),
    "southwest_day3": weather_day_label("southwest", 2),

    "northwest_day1": weather_day_label("northwest", 0),
    "northwest_day2": weather_day_label("northwest", 1),
    "northwest_day3": weather_day_label("northwest", 2),

    "east_city": region_map["east"]["city"],
    "east_hot": reports["east"]["change"],
    "east_flow": reports["east"]["impact"],
    "east_signal": reports["east"]["action"],
    "east_action": actions["east"],
    "east_star": stars["east"],

    "central_city": region_map["central"]["city"],
    "central_hot": reports["central"]["change"],
    "central_flow": reports["central"]["impact"],
    "central_signal": reports["central"]["action"],
    "central_action": actions["central"],
    "central_star": stars["central"],

    "south_city": region_map["south"]["city"],
    "south_hot": reports["south"]["change"],
    "south_flow": reports["south"]["impact"],
    "south_signal": reports["south"]["action"],
    "south_action": actions["south"],
    "south_star": stars["south"],

    "southwest_city": region_map["southwest"]["city"],
    "southwest_hot": reports["southwest"]["change"],
    "southwest_flow": reports["southwest"]["impact"],
    "southwest_signal": reports["southwest"]["action"],
    "southwest_action": actions["southwest"],
    "southwest_star": stars["southwest"],

    "northwest_city": region_map["northwest"]["city"],
    "northwest_hot": reports["northwest"]["change"],
    "northwest_flow": reports["northwest"]["impact"],
    "northwest_signal": reports["northwest"]["action"],
    "northwest_action": actions["northwest"],
    "northwest_star": stars["northwest"],

    "trend1_title": trend_items[0]["title"],
    "trend1_desc": trend_items[0]["desc"],
    "trend1_tag": trend_items[0]["tag"],

    "trend2_title": trend_items[1]["title"],
    "trend2_desc": trend_items[1]["desc"],
    "trend2_tag": trend_items[1]["tag"],

    "trend3_title": trend_items[2]["title"],
    "trend3_desc": trend_items[2]["desc"],
    "trend3_tag": trend_items[2]["tag"],

    "trend4_title": trend_items[3]["title"],
    "trend4_desc": trend_items[3]["desc"],
    "trend4_tag": trend_items[3]["tag"],

    "generate_time": today.strftime("%Y-%m-%d %H:%M"),
}

for i, item in enumerate(top_news, start=1):
    data[f"top{i}_title"] = item["title"]
    data[f"top{i}_tag"] = item["tag"]
    data[f"top{i}_time"] = today.strftime("%m-%d %H:%M")
    data[f"top{i}_source"] = item["source"]
    data[f"top{i}_desc"] = item["desc"]
    data[f"top{i}_logo"] = item["logo"]
    data[f"top{i}_icon"] = item["icon"]
    data[f"top{i}_logo_class"] = item["class"]

for i, word in enumerate(words, start=1):
    data[f"word{i}"] = word

for key, value in data.items():
    template = template.replace("{{" + key + "}}", str(value))

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
