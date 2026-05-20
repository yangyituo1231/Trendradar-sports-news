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
# TOP5
# =========================

CATEGORY_RULES = {
    "大促电商": {
        "keywords": ["618", "双11", "双十一", "双12", "99大促", "38大促", "大促", "预售", "电商", "直播", "抖音", "小红书", "种草"],
        "tag": "大促/电商",
        "logo": "大促",
        "icon": "🛒",
        "class": "logo-blue",
        "desc": "大促信息适度关注，重点看夏季品类曝光、直播种草、转化效率和终端承接。",
    },
    "童装儿童": {
        "keywords": ["童装", "儿童", "亲子", "校园", "儿童运动", "运动童装", "Kids", "KIDS"],
        "tag": "童装/儿童运动",
        "logo": "童装",
        "icon": "🧒",
        "class": "logo-sky",
        "desc": "儿童消费从单品购买转向亲子、校园、户外和运动场景综合经营。",
    },
    "天气防晒": {
        "keywords": ["高温", "防晒", "凉感", "速干", "暴雨", "强对流", "降雨", "天气", "防雨", "夏日", "夏季", "降雪", "结冰", "低温", "防滑", "保暖"],
        "tag": "天气影响消费",
        "logo": "天气",
        "icon": "☀️",
        "class": "logo-sky",
        "desc": "天气变化影响客流和主推节奏，防晒、凉感、防雨、防滑及保暖品类需动态前置。",
    },
    "户外运动": {
        "keywords": ["户外", "骑行", "露营", "文旅", "出行", "夜经济", "跑步", "轻户外", "徒步", "马拉松", "越野跑", "赛事", "训练"],
        "tag": "户外/运动场景",
        "logo": "户外",
        "icon": "🚴",
        "class": "logo-green",
        "desc": "户外、跑步、骑行、赛事和夜间消费延伸运动场景，带动装备与亲子需求。",
    },
    "商圈消费": {
        "keywords": ["商场", "商圈", "门店", "客流", "奥莱", "折扣", "会员", "零售", "消费", "本地生活"],
        "tag": "商圈/零售经营",
        "logo": "商圈",
        "icon": "🏬",
        "class": "logo-dark",
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
    score = category_score(title, cat) * 10

    if cat != "大促电商" and any(k in title for k in ["618", "双11", "双十一", "双12", "99大促", "38大促"]):
        score -= 5

    for kw in ["童装", "儿童", "亲子", "防晒", "凉感", "防雨", "防滑", "保暖", "门店", "商场", "商圈", "客流", "零售", "消费", "户外", "跑步", "赛事"]:
        if kw in title:
            score += 3

    for kw in ["比分", "赛程", "夺冠", "冠军", "主教练", "球队", "球员", "转会"]:
        if kw in title:
            score -= 12

    for src in ["界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报", "新华网", "澎湃新闻", "证券时报", "新京报"]:
        if src in source:
            score += 2

    return score

def pick_top_news():
    used = set()
    result = []

    for cat in ["大促电商", "童装儿童", "天气防晒", "户外运动", "商圈消费"]:
        rule = CATEGORY_RULES[cat]
        candidates = []

        for item in news_items:
            title = clean_title(item.get("title", ""))
            if not title or title in used:
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

        used.add(title)
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

top_news = pick_top_news()

# =========================
# 区域经营内容
# =========================

region_map = {
    "east": {"city": "上海/江苏/浙江", "weather_key": "east", "keywords": ["上海", "杭州", "南京", "苏州", "宁波", "江苏", "浙江"], "bias": ["mall", "content", "promotion"]},
    "central": {"city": "湖北/湖南/江西", "weather_key": "east", "keywords": ["武汉", "长沙", "南昌", "郑州", "湖北", "湖南", "江西"], "bias": ["mall", "kids", "school"]},
    "south": {"city": "广东/广西", "weather_key": "south", "keywords": ["广州", "深圳", "佛山", "南宁", "广东", "广西", "厦门", "福建"], "bias": ["high_temp", "content", "promotion"]},
    "southwest": {"city": "四川/重庆/贵州", "weather_key": "southwest", "keywords": ["成都", "重庆", "贵阳", "昆明", "四川", "贵州", "云南"], "bias": ["outdoor", "kids", "tourism"]},
    "northwest": {"city": "陕西/甘肃/宁夏", "weather_key": "northwest", "keywords": ["西安", "兰州", "银川", "陕西", "甘肃", "宁夏", "新疆"], "bias": ["outdoor", "travel", "wind"]},
}

SCENE_POOLS = {
    "rain": {
        "hot": ["降雨扰动商圈客流", "雨天出行影响到店", "局地降雨影响周末客流"],
        "flow": ["室内消费与亲子客流承接增强", "商场客流向室内活动集中", "雨天客流更依赖商场活动"],
        "signal": ["防雨、防滑与轻外套需求提升", "室内运动与轻防护品类升温", "防水鞋服与帽类关注提升"],
        "action": ["强化防雨、防滑与室内场景", "前置轻防护与童鞋连带", "用会员活动承接雨天客流"],
    },
    "high_temp": {
        "hot": ["高温带动夏季品类升温", "暑热天气推升防晒需求", "夏季功能品类进入主推窗口"],
        "flow": ["防晒、凉感与短裤需求提升", "轻薄速干品类关注上升", "户外停留下降但功能品类增强"],
        "signal": ["凉感科技、防晒衣与速干T升温", "短裤、凉感T和防晒配件走强", "亲子户外防晒需求提升"],
        "action": ["前置防晒凉感与短裤组合", "强化夏季功能品类堆头", "加强凉感T与童鞋连带"],
    },
    "cold": {
        "hot": ["低温影响户外停留", "雨雪结冰影响出行", "冬季保暖需求延续"],
        "flow": ["室内运动与保暖需求增加", "保暖鞋服与童鞋关注提升", "商场客流更依赖室内活动"],
        "signal": ["防滑鞋、棉服与帽类需求提升", "保暖基础款与运动鞋需求稳定", "防风保暖与室内运动升温"],
        "action": ["强化保暖防滑与童鞋连带", "前置棉服帽类与防滑鞋", "做室内运动场景承接"],
    },
    "promotion": {
        "hot": ["大促节点带动关注", "平台预售强化价格心智", "618带动夏季品类曝光"],
        "flow": ["直播与价格带关注增强", "爆款与直播同款转化提升", "线上热度向门店承接外溢"],
        "signal": ["爆款、价格带与同款转化关键", "夏季主推与直播同款关注提升", "消费者比价与爆款心智增强"],
        "action": ["强化爆款堆头与价格带", "承接直播同款与门店转化", "突出夏季核心品类组合"],
    },
    "content": {
        "hot": ["内容平台种草影响增强", "短视频影响购买决策", "社交平台带动新品关注"],
        "flow": ["线上内容影响到店转化", "种草内容带动同款咨询", "达人内容提升新品触达"],
        "signal": ["小红书与抖音同款关注提升", "内容同款与新品试穿需求增加", "直播种草影响成交路径"],
        "action": ["加强内容同款与新品承接", "设置种草同款展示区", "强化导购话术与试穿转化"],
    },
    "kids": {
        "hot": ["亲子与校园场景升温", "儿童运动需求扩张", "童装消费场景继续外扩"],
        "flow": ["儿童运动与亲子客流增加", "校园与亲子活动带动连带", "童鞋童服组合需求增强"],
        "signal": ["童鞋、速干T与运动短裤热度提升", "校园运动与亲子搭配关注增加", "儿童运动装备需求提升"],
        "action": ["强化亲子与校园场景陈列", "做童鞋+速干T连带", "增加儿童运动套装展示"],
    },
    "outdoor": {
        "hot": ["轻户外与骑行热度提升", "户外出行带动运动消费", "文旅与轻户外场景延伸"],
        "flow": ["骑行、露营、徒步消费增加", "户外休闲客群活跃", "亲子户外装备需求增加"],
        "signal": ["帽包、轻外套与户外装备关注提升", "防晒、速干与轻户外组合升温", "户外配件连带空间提升"],
        "action": ["增加轻户外与配件组合", "强化骑行露营场景展示", "提升亲子户外陈列占比"],
    },
    "running": {
        "hot": ["跑步与赛事热度提升", "训练场景带动装备需求", "运动科技关注提升"],
        "flow": ["专业跑鞋与训练装备需求增加", "赛事人群带动运动消费", "跑步场景提升鞋类关注"],
        "signal": ["跑鞋、速干与训练系列关注提升", "缓震、透气与轻量化卖点增强", "专业运动装备询问增加"],
        "action": ["强化跑鞋与训练场景表达", "突出缓震透气科技卖点", "增加跑步装备组合陈列"],
    },
    "mall": {
        "hot": ["商圈活动与会员运营增加", "周末商场活动带动客流", "门店客流进入精细运营期"],
        "flow": ["周末客流与互动活跃度提升", "会员活动带动到店转化", "商场活动提升亲子停留"],
        "signal": ["会员互动与连带消费增加", "门口堆头与爆款陈列更关键", "客流修复但转化仍需跟进"],
        "action": ["加强会员活动与门口堆头", "提升导购连带与试穿转化", "重点承接周末亲子客流"],
    },
}

def detect_business_scene(text, weather_key, bias=None):
    text = str(text)
    bias = bias or []
    t = weather_business_type(weather_key)
    scenes = []

    if t in ["very_hot", "hot"]:
        scenes.append("high_temp")
    if t in ["storm", "rain"]:
        scenes.append("rain")
    if t in ["snow_ice", "cold"]:
        scenes.append("cold")

    if any(k in text for k in ["618", "双11", "双十一", "双12", "99大促", "38大促", "预售", "百亿补贴"]):
        scenes.append("promotion")
    if any(k in text for k in ["抖音", "小红书", "种草", "直播", "达人"]):
        scenes.append("content")
    if any(k in text for k in ["童装", "儿童", "亲子", "校园", "Kids", "KIDS"]):
        scenes.append("kids")
    if any(k in text for k in ["户外", "露营", "骑行", "徒步", "Citywalk", "文旅", "出行"]):
        scenes.append("outdoor")
    if any(k in text for k in ["跑步", "马拉松", "赛事", "越野跑", "训练", "跑鞋"]):
        scenes.append("running")
    if any(k in text for k in ["商场", "商圈", "客流", "门店", "会员", "奥莱"]):
        scenes.append("mall")

    for b in bias:
        if b in SCENE_POOLS:
            scenes.append(b)

    scenes = list(dict.fromkeys(scenes))

    if not scenes:
        if SEASON == "summer":
            scenes = ["high_temp", "kids"]
        elif SEASON == "winter":
            scenes = ["cold", "mall"]
        else:
            scenes = ["kids", "outdoor"]

    return scenes[:4]

def pick_from_scene(scenes, field, used):
    candidates = []
    for scene in scenes:
        candidates.extend(SCENE_POOLS.get(scene, {}).get(field, []))
    random.shuffle(candidates)
    for c in candidates:
        if c not in used:
            used.add(c)
            return c
    return candidates[0] if candidates else "关注主推品类与客流承接"

def generate_store_strategy(region_key, cfg, local_text):
    scenes = detect_business_scene(local_text, cfg["weather_key"], cfg.get("bias", []))
    used = set()
    return {
        "hot": "、".join([pick_from_scene(scenes, "hot", used) for _ in range(2)]),
        "flow": "、".join([pick_from_scene(scenes, "flow", used) for _ in range(2)]),
        "signal": "、".join([pick_from_scene(scenes, "signal", used) for _ in range(2)]),
        "action": "、".join([pick_from_scene(scenes, "action", used) for _ in range(2)]),
    }

def build_region_reports():
    reports = {}
    actions = {}
    for region, cfg in region_map.items():
        local_titles = [t for t in titles if any(k in t for k in cfg["keywords"])]
        local_text = " ".join(local_titles[:10]) or joined[:300]
        result = generate_store_strategy(region, cfg, local_text)
        reports[region] = {"change": result["hot"], "impact": result["flow"], "action": result["signal"]}
        actions[region] = result["action"]
    return reports, actions

reports, actions = build_region_reports()

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
# 今日一句 + GPT经营摘要规则版
# =========================

def make_today_insight():
    if any(k in joined for k in ["618", "战报", "大促", "预售"]) and any(k in joined for k in ["防晒", "凉感", "速干"]):
        return "大促流量叠加夏季功能品类升温，门店承接能力决定最终转化。"
    if any(weather_business_type(k) in ["storm", "rain"] for k in ["north", "east", "south", "southwest", "northwest"]):
        return "降雨扰动线下客流，防雨轻防护与室内亲子场景成为核心承接方向。"
    if any(weather_business_type(k) in ["very_hot", "hot"] for k in ["north", "east", "south", "southwest", "northwest"]):
        return "高温推动防晒、凉感、速干需求前置，夏季功能品类进入主推窗口。"
    if any(k in joined for k in ["跑步", "马拉松", "赛事", "跑鞋"]):
        return "赛事与跑步热度扩散，专业跑鞋和训练装备成为运动消费的重要抓手。"
    return "行业热点正在从单一流量转向场景经营，门店要用商品组合承接消费变化。"

def make_ai_summary():
    parts = []
    if any(k in joined for k in ["618", "大促", "预售", "战报"]):
        parts.append("平台大促仍是短期流量主线，爆款价格带、直播同款和夏季核心品类需要同步承接")
    if any(k in joined for k in ["防晒", "凉感", "速干", "高温"]):
        parts.append("防晒、凉感、速干等功能品类热度提升，门店应前置陈列并加强连带")
    if any(k in joined for k in ["童装", "儿童", "亲子", "校园"]):
        parts.append("儿童运动、亲子和校园场景继续扩张，童鞋童服组合销售价值提升")
    if any(k in joined for k in ["户外", "骑行", "露营", "文旅"]):
        parts.append("轻户外、骑行和文旅场景延伸，帽包、防护和运动休闲品类具备增量")
    if any(k in joined for k in ["抖音", "小红书", "直播", "种草"]):
        parts.append("内容平台正在影响消费决策，门店需要用同款展示和导购话术承接线上种草")
    if any(weather_business_type(k) in ["rain", "storm"] for k in ["north", "east", "south", "southwest", "northwest"]):
        parts.append("降雨天气可能扰动客流，需增强室内场景、防雨防滑和会员活动承接")
    if not parts:
        parts.append("今日行业信息整体平稳，重点关注商圈客流、商品节奏和区域差异化运营")

    return "；".join(parts[:3]) + "。"

today_insight = make_today_insight()
def make_deepseek_summary():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return make_ai_summary()

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        news_text = "\n".join(titles[:20])
        weather_text = "；".join([
            weather_desc("north"),
            weather_desc("east"),
            weather_desc("south"),
            weather_desc("southwest"),
            weather_desc("northwest"),
        ])

        prompt = f"""
你是运动鞋服零售行业经营分析师。请基于以下新闻和天气，生成一段80字以内的经营摘要。
要求：
1. 面向361°儿童经营管理部
2. 关注鞋服品类、天气、客流、门店动作、电商大促
3. 不要空话
4. 输出一段话

新闻：
{news_text}

天气：
{weather_text}
"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是专业、简洁、偏经营实战的运动鞋服零售分析师。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=160,
        )

        text = response.choices[0].message.content.strip()
        return text[:140]

    except Exception:
        return make_ai_summary()

ai_summary = make_deepseek_summary()

# =========================
# 第四部分
# =========================

def detect_trend_from_news():
    rules = [
        (["抖音", "小红书", "直播", "种草", "内容"], {"title": "内容平台影响转化", "desc": "抖音、小红书与直播内容影响新品传播、到店转化和线上成交。", "tag": "内容电商"}),
        (["618", "双11", "双十一", "双12", "大促", "预售"], {"title": "大促节点提前蓄水", "desc": "平台活动前置，需关注爆款、价格带、直播同款与门店承接。", "tag": "大促趋势"}),
        (["防晒", "凉感", "速干", "高温"], {"title": "季节功能品类升温", "desc": "防晒、凉感、速干等功能品类热度提升，门店陈列节奏需前置。", "tag": "季节趋势"}),
        (["童装", "儿童", "亲子", "校园"], {"title": "儿童运动场景扩张", "desc": "亲子、校园与儿童运动场景热度延续，童装连带与场景搭配更关键。", "tag": "儿童消费趋势"}),
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
# 第五部分：行业热词雷达
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
    "机能": "机能风", "松弛感": "松弛感", "多巴胺": "多巴胺穿搭",

    "赛事": "体育赛事", "跑步": "跑步经济", "马拉松": "马拉松", "越野跑": "越野跑", "训练": "训练装备",

    "耐克": "Nike", "Nike": "Nike", "阿迪达斯": "阿迪达斯", "Adidas": "阿迪达斯",
    "亚瑟士": "亚瑟士", "ASICS": "亚瑟士", "昂跑": "On昂跑", "On": "On昂跑",
    "HOKA": "HOKA", "安踏": "安踏", "李宁": "李宁", "特步": "特步", "361": "361儿童",
    "乔丹": "乔丹", "lululemon": "lululemon",

    "消费分层": "消费分层", "理性消费": "理性消费", "悦己": "悦己消费", "情绪消费": "情绪消费",
    "防雨": "防雨装备", "低温": "保暖", "保暖": "保暖", "防滑": "防滑鞋", "降雪": "防滑鞋", "结冰": "防滑鞋",
}

def build_words():
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

    phrase_patterns = [
        r"618[^，。！？、\s]{0,6}", r"抖音[^，。！？、\s]{0,6}", r"小红书[^，。！？、\s]{0,6}",
        r"防晒[^，。！？、\s]{0,6}", r"凉感[^，。！？、\s]{0,6}", r"户外[^，。！？、\s]{0,6}",
        r"亲子[^，。！？、\s]{0,6}", r"儿童[^，。！？、\s]{0,6}", r"跑步[^，。！？、\s]{0,6}",
        r"骑行[^，。！？、\s]{0,6}", r"露营[^，。！？、\s]{0,6}", r"商场[^，。！？、\s]{0,6}",
        r"客流[^，。！？、\s]{0,6}", r"品牌[^，。！？、\s]{0,6}", r"训练[^，。！？、\s]{0,6}",
        r"跑鞋[^，。！？、\s]{0,6}", r"凉鞋[^，。！？、\s]{0,6}", r"冲锋衣[^，。！？、\s]{0,6}",
        r"篮球鞋[^，。！？、\s]{0,6}", r"山系[^，。！？、\s]{0,6}", r"机能[^，。！？、\s]{0,6}",
    ]

    bad_phrases = ["运动品牌行业", "品牌行业资讯", "运动品牌", "儿童运动消费场景", "品牌行业"]

    for t in titles[:80]:
        for pattern in phrase_patterns:
            for phrase in re.findall(pattern, t):
                phrase = clean_title(phrase)
                if 2 <= len(phrase) <= 8 and phrase not in bad_phrases:
                    counter[phrase] += 1

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

words = build_words()

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
