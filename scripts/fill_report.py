from pathlib import Path
from datetime import datetime, timedelta
import random
import json
import re
from collections import Counter

template = Path("daily-report.html").read_text(encoding="utf-8")

now = datetime.now()
today = now
day2 = today + timedelta(days=1)
day3 = today + timedelta(days=2)

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

def report_for_weather_type(weather_key):
    t = weather_business_type(weather_key)
    mapping = {
        "snow_ice": {"change": "雨雪结冰影响出行", "impact": "防滑鞋、保暖服饰与室内客流关注提升", "action": "建议强化防滑鞋、保暖外套及室内运动陈列"},
        "cold": {"change": "低温天气影响户外停留", "impact": "棉服、羽绒、帽类及保暖运动鞋需求提升", "action": "建议加强保暖系列与童鞋连带销售"},
        "storm": {"change": "强降雨扰动商圈客流", "impact": "室内运动与防雨、防滑品类关注提升", "action": "建议强化防雨、防滑及轻外套陈列"},
        "rain": {"change": "降雨天气扰动客流", "impact": "室内运动与轻防护品类关注提升", "action": "建议强化防雨、轻外套及室内运动场景陈列"},
        "very_hot": {"change": "高温天气带动夏季消费", "impact": "防晒、凉感、速干类需求提升", "action": "建议加强防晒单品与短裤连带销售"},
        "hot": {"change": "气温偏高带动轻薄品类", "impact": "短T、短裤、凉感及防晒需求提升", "action": "建议前置凉感、速干及夏季主推陈列"},
        "wind": {"change": "大风天气影响户外活动", "impact": "轻外套、帽类及防风装备关注提升", "action": "建议加强轻外套、帽类及户外配件组合"},
        "spring_mild": {"change": "春季出行与亲子活动恢复", "impact": "轻外套、运动童装与户外场景需求提升", "action": "建议强化春季轻外套与亲子搭配展示"},
        "autumn_mild": {"change": "秋季运动与开学场景延续", "impact": "长袖、长裤、轻外套及校园运动需求提升", "action": "建议前置校园运动与秋季轻外套组合"},
        "winter_mild": {"change": "冬季基础保暖需求延续", "impact": "保暖基础款、运动鞋及室内运动需求稳定", "action": "建议关注保暖基础款与童鞋连带销售"},
        "normal": {"change": "天气平稳利于户外恢复", "impact": "亲子活动、轻户外与运动休闲需求增加", "action": "建议增加轻户外及亲子运动场景曝光"},
    }
    return mapping.get(t, mapping["normal"])

NEWS_REPORTS = [
    {"change": "商圈活动与会员运营增加", "impact": "周末客流与互动活跃度提升", "action": "建议加强会员活动引流"},
    {"change": "亲子与校园运动场景升温", "impact": "儿童运动与轻户外需求增加", "action": "建议强化校园运动与亲子搭配展示"},
    {"change": "轻户外与骑行热度提升", "impact": "骑行、露营、徒步消费增加", "action": "建议增加轻户外系列曝光"},
    {"change": "赛事与跑步热度提升", "impact": "专业跑鞋、训练装备与运动科技关注增加", "action": "建议放大跑步鞋与训练装备场景陈列"},
    {"change": "内容平台种草影响增强", "impact": "小红书、抖音带动新品关注与到店转化", "action": "建议加强爆款同款与内容陈列承接"},
    {"change": "大促节点带动关注", "impact": "爆款、价格带与直播同款转化更关键", "action": "建议强化大促爆款、价格带及门口堆头"},
]

def report_by_news_text(text):
    if any(k in text for k in ["618", "双11", "双十一", "双12", "大促", "预售"]):
        return NEWS_REPORTS[5]
    if any(k in text for k in ["商场", "商圈", "客流", "会员", "奥莱"]):
        return NEWS_REPORTS[0]
    if any(k in text for k in ["童装", "儿童", "亲子", "校园"]):
        return NEWS_REPORTS[1]
    if any(k in text for k in ["骑行", "户外", "露营", "文旅", "出行"]):
        return NEWS_REPORTS[2]
    if any(k in text for k in ["赛事", "跑步", "马拉松", "训练", "越野跑"]):
        return NEWS_REPORTS[3]
    if any(k in text for k in ["抖音", "小红书", "种草", "直播"]):
        return NEWS_REPORTS[4]
    return None

region_map = {
    "east": {"city": "上海/江苏/浙江", "weather_key": "east", "keywords": ["上海", "杭州", "南京", "苏州", "宁波", "江苏", "浙江"]},
    "central": {"city": "湖北/湖南/江西", "weather_key": "east", "keywords": ["武汉", "长沙", "南昌", "郑州", "湖北", "湖南", "江西"]},
    "south": {"city": "广东/广西", "weather_key": "south", "keywords": ["广州", "深圳", "佛山", "南宁", "广东", "广西", "厦门", "福建"]},
    "southwest": {"city": "四川/重庆/贵州", "weather_key": "southwest", "keywords": ["成都", "重庆", "贵阳", "昆明", "四川", "贵州", "云南"]},
    "northwest": {"city": "陕西/甘肃/宁夏", "weather_key": "northwest", "keywords": ["西安", "兰州", "银川", "陕西", "甘肃", "宁夏", "新疆"]},
}

# =========================
# 动态经营建议引擎（AI经营逻辑）
# =========================

def detect_business_scene(text, weather_key):
    text = str(text)

    t = weather_business_type(weather_key)

    scenes = []

    # 天气
    if t in ["very_hot", "hot"]:
        scenes.append("high_temp")

    if t in ["storm", "rain"]:
        scenes.append("rain")

    if t in ["snow_ice", "cold"]:
        scenes.append("cold")

    # 大促
    if any(k in text for k in [
        "618", "双11", "双十一", "双12",
        "99大促", "38大促", "预售", "百亿补贴"
    ]):
        scenes.append("promotion")

    # 内容平台
    if any(k in text for k in [
        "抖音", "小红书", "种草", "直播", "达人"
    ]):
        scenes.append("content")

    # 亲子儿童
    if any(k in text for k in [
        "童装", "儿童", "亲子", "校园"
    ]):
        scenes.append("kids")

    # 户外
    if any(k in text for k in [
        "户外", "露营", "骑行", "徒步", "Citywalk"
    ]):
        scenes.append("outdoor")

    # 跑步赛事
    if any(k in text for k in [
        "跑步", "马拉松", "赛事",
        "越野跑", "训练", "跑鞋"
    ]):
        scenes.append("running")

    # 商圈
    if any(k in text for k in [
        "商场", "商圈", "客流",
        "门店", "会员", "奥莱"
    ]):
        scenes.append("mall")

    return list(set(scenes))


def generate_store_strategy(region_name, weather_key, local_text):
    scenes = detect_business_scene(local_text, weather_key)

    hot_parts = []
    flow_parts = []
    signal_parts = []
    action_parts = []

    # =====================
    # 高温
    # =====================

    if "high_temp" in scenes:
        hot_parts.append("高温天气带动夏季消费")
        flow_parts.append("防晒、凉感与短裤需求提升")
        signal_parts.append("夏季功能型商品热度上升")
        action_parts.append("前置防晒、凉感与短裤陈列")

    # =====================
    # 雨天
    # =====================

    if "rain" in scenes:
        hot_parts.append("降雨天气扰动客流")
        flow_parts.append("室内消费与轻防护需求增加")
        signal_parts.append("防雨、防滑与轻外套需求提升")
        action_parts.append("加强防雨、防滑及室内场景承接")

    # =====================
    # 冬季
    # =====================

    if "cold" in scenes:
        hot_parts.append("低温天气影响户外停留")
        flow_parts.append("保暖与室内运动需求增加")
        signal_parts.append("棉服、防滑鞋与帽类需求提升")
        action_parts.append("强化保暖、防滑及童鞋连带")

    # =====================
    # 大促
    # =====================

    if "promotion" in scenes:
        hot_parts.append("平台大促热度提升")
        flow_parts.append("直播与价格带关注增强")
        signal_parts.append("爆款与直播同款转化提升")
        action_parts.append("强化爆款堆头与价格带陈列")

    # =====================
    # 内容平台
    # =====================

    if "content" in scenes:
        hot_parts.append("内容平台种草影响增强")
        flow_parts.append("线上内容影响到店转化")
        signal_parts.append("短视频同款关注提升")
        action_parts.append("加强内容同款与新品承接")

    # =====================
    # 儿童
    # =====================

    if "kids" in scenes:
        hot_parts.append("亲子与校园场景持续升温")
        flow_parts.append("儿童运动需求增加")
        signal_parts.append("童鞋与运动短裤热度提升")
        action_parts.append("强化亲子与校园场景陈列")

    # =====================
    # 户外
    # =====================

    if "outdoor" in scenes:
        hot_parts.append("轻户外与骑行热度提升")
        flow_parts.append("户外休闲消费增加")
        signal_parts.append("帽包与轻户外装备关注提升")
        action_parts.append("增加轻户外与配件组合展示")

    # =====================
    # 跑步
    # =====================

    if "running" in scenes:
        hot_parts.append("跑步与赛事场景热度提升")
        flow_parts.append("专业运动装备需求增加")
        signal_parts.append("跑鞋与训练系列关注提升")
        action_parts.append("强化跑鞋与训练场景表达")

    # =====================
    # 商圈
    # =====================

    if "mall" in scenes:
        hot_parts.append("商圈活动与会员运营增加")
        flow_parts.append("周末客流恢复增强")
        signal_parts.append("互动活动与连带消费增加")
        action_parts.append("加强会员活动与门口堆头")

    # fallback

    if not hot_parts:
        hot_parts.append("区域消费节奏整体平稳")

    if not flow_parts:
        flow_parts.append("户外与商圈消费保持恢复")

    if not signal_parts:
        signal_parts.append("运动休闲与亲子消费维持增长")

    if not action_parts:
        action_parts.append("关注夏季主推与客流承接")

    return {
        "hot": "、".join(hot_parts[:2]),
        "flow": "、".join(flow_parts[:2]),
        "signal": "、".join(signal_parts[:2]),
        "action": "、".join(action_parts[:2]),
    }


def build_region_reports():

    reports = {}
    actions = {}

    for region, cfg in region_map.items():

        local_titles = [
            t for t in titles
            if any(k in t for k in cfg["keywords"])
        ]

        local_text = " ".join(local_titles[:10])

        result = generate_store_strategy(
            cfg["city"],
            cfg["weather_key"],
            local_text
        )

        reports[region] = {
            "change": result["hot"],
            "impact": result["flow"],
            "action": result["signal"],
        }

        actions[region] = result["action"]

    return reports, actions


reports, actions = build_region_reports()

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
# 第五部分：实时热词
# =========================

KEYWORD_MAP = {
    "抖音": "抖音直播",
    "直播": "直播带货",
    "小红书": "小红书种草",
    "种草": "内容种草",
    "618": "618",
    "成绩单": "618战报",
    "战报": "618战报",
    "品牌": "品牌站位",
    "C位": "品牌站位",
    "双11": "双11预售",
    "双十一": "双11预售",
    "双12": "双12",
    "99大促": "99大促",
    "38大促": "38大促",
    "大促": "大促预售",
    "预售": "大促预售",
    "防晒": "防晒品类",
    "防晒衣": "防晒衣",
    "凉感": "凉感科技",
    "速干": "速干",
    "短裤": "短裤",
    "童装": "运动童装",
    "儿童": "儿童运动",
    "亲子": "亲子运动",
    "校园": "校园体育",
    "商场": "商场活动",
    "商圈": "商圈客流",
    "客流": "客流修复",
    "门店": "门店陈列",
    "会员": "会员运营",
    "户外": "户外运动",
    "轻户外": "轻户外",
    "骑行": "城市骑行",
    "露营": "露营经济",
    "文旅": "文旅客流",
    "夜经济": "夜经济",
    "赛事": "体育赛事",
    "跑步": "跑步经济",
    "马拉松": "马拉松",
    "越野跑": "越野跑",
    "训练": "训练装备",
    "跑鞋": "专业跑鞋",
    "运动科技": "运动科技",
    "耐克": "Nike",
    "Nike": "Nike",
    "阿迪达斯": "阿迪达斯",
    "Adidas": "阿迪达斯",
    "亚瑟士": "亚瑟士",
    "ASICS": "亚瑟士",
    "昂跑": "On昂跑",
    "On": "On昂跑",
    "HOKA": "HOKA",
    "安踏": "安踏",
    "李宁": "李宁",
    "特步": "特步",
    "361": "361儿童",
    "乔丹": "乔丹",
    "lululemon": "lululemon",
    "防雨": "防雨装备",
    "低温": "保暖",
    "保暖": "保暖",
    "防滑": "防滑鞋",
    "降雪": "防滑鞋",
    "结冰": "防滑鞋",
}

def build_words():
    counter = Counter()

    top_titles = [item["title"] for item in top_news if item.get("title")]
    top_joined = " ".join(top_titles)

    top_keyword_boost = {
        "618": "618战报",
        "成绩单": "618战报",
        "战报": "618战报",
        "品牌": "品牌站位",
        "C位": "品牌站位",
        "童装": "运动童装",
        "儿童": "儿童运动",
        "防晒": "防晒品类",
        "凉感": "凉感科技",
        "户外": "户外运动",
        "抖音": "抖音直播",
        "直播": "直播带货",
        "商圈": "商圈客流",
        "客流": "客流修复",
    }

    for raw, mapped in top_keyword_boost.items():
        if raw in top_joined:
            counter[mapped] += 5

    for t in titles[:100]:
        for raw, mapped in KEYWORD_MAP.items():
            if raw in t:
                counter[mapped] += 2

    phrase_patterns = [
        r"618[^，。！？、\s]{0,6}",
        r"抖音[^，。！？、\s]{0,6}",
        r"小红书[^，。！？、\s]{0,6}",
        r"防晒[^，。！？、\s]{0,6}",
        r"凉感[^，。！？、\s]{0,6}",
        r"户外[^，。！？、\s]{0,6}",
        r"亲子[^，。！？、\s]{0,6}",
        r"儿童[^，。！？、\s]{0,6}",
        r"跑步[^，。！？、\s]{0,6}",
        r"骑行[^，。！？、\s]{0,6}",
        r"露营[^，。！？、\s]{0,6}",
        r"商场[^，。！？、\s]{0,6}",
        r"客流[^，。！？、\s]{0,6}",
        r"品牌[^，。！？、\s]{0,6}",
        r"运动[^，。！？、\s]{0,6}",
        r"训练[^，。！？、\s]{0,6}",
        r"跑鞋[^，。！？、\s]{0,6}",
    ]

    bad_phrases = ["运动品牌行业", "品牌行业资讯", "运动品牌", "儿童运动消费场景"]

    for t in titles[:60]:
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

    sport_context_words = {
        "跑步经济": ["跑步", "跑鞋", "马拉松", "训练"],
        "专业跑鞋": ["跑步", "跑鞋", "马拉松", "HOKA", "亚瑟士", "On"],
        "城市骑行": ["骑行", "城市骑行"],
        "户外运动": ["户外", "露营", "徒步", "轻户外"],
        "轻户外": ["轻户外", "户外", "露营"],
        "训练装备": ["训练", "跑步", "赛事"],
        "运动科技": ["运动科技", "科技", "缓震", "碳板"],
        "儿童体适能": ["儿童", "校园", "体适能"],
        "校园体育": ["校园", "儿童运动"],
        "女子运动": ["女性", "女子", "女神节", "38"],
        "潮流运动": ["潮流", "联名", "街头"],
        "运动康复": ["康复", "恢复", "护具"],
    }

    for mapped, triggers in sport_context_words.items():
        if any(tg in joined for tg in triggers):
            counter[mapped] += 2

    for generic in ["儿童运动", "户外运动", "运动童装"]:
        if counter[generic] > 4:
            counter[generic] = 4

    seasonal_fallback = {
        "spring": ["春季出行", "轻外套", "亲子运动", "校园体育", "城市骑行"],
        "summer": ["防晒品类", "凉感科技", "速干", "短裤", "618"],
        "autumn": ["开学季", "校园体育", "轻外套", "户外运动", "99大促"],
        "winter": ["保暖", "防滑鞋", "童鞋", "室内运动", "训练装备"],
    }.get(SEASON, [])

    broad_fallback = [
        "618战报", "品牌站位", "直播带货", "门店陈列", "客流修复",
        "运动童装", "儿童运动", "轻户外", "抖音直播", "小红书种草",
        "跑步经济", "专业跑鞋", "户外运动", "运动科技", "训练装备",
        "Nike", "阿迪达斯", "安踏", "李宁", "特步", "On昂跑", "HOKA"
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

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",

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
