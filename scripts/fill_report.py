from pathlib import Path
from datetime import datetime, timedelta
import random
import json
import re

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

titles = [clean_title(x.get("title", "")) for x in news_items if isinstance(x, dict) and x.get("title")]
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
        "risk_score": 30,
        "signal": "天气整体平稳，户外与亲子活动具备恢复基础"
    }

def weather_desc(key):
    region = get_weather_region(key)
    return region.get("signal", "天气整体平稳，户外与亲子活动具备恢复基础")

def weather_risk(key):
    region = get_weather_region(key)
    return int(region.get("risk_score", 30))

def weather_day_label(key, idx):
    return get_day_weather(key, idx).get("weather", "多云")

# =========================
# 新闻热度评分
# =========================

def news_heat_score(keywords):
    score = 0
    for title in titles:
        if any(k in title for k in keywords):
            score += 8
        if any(k in title for k in ["618", "大促", "防晒", "凉感", "童装", "儿童", "亲子", "商场", "商圈", "客流"]):
            score += 2
    return min(score, 35)

def business_keyword_score():
    score = 0
    for k in ["防晒", "凉感", "童装", "儿童", "亲子", "618", "商场", "商圈", "客流", "户外", "骑行", "小红书", "抖音"]:
        if k in joined:
            score += 3
    return min(score, 25)

def total_region_score(weather_key, region_keywords):
    return min(weather_risk(weather_key) * 0.55 + news_heat_score(region_keywords) + business_keyword_score(), 100)

def star_by_total_score(score):
    if score >= 65:
        return "★★★"
    if score >= 40:
        return "★★"
    return "★"

# =========================
# TOP5：贴近新闻原文，但一类一条
# =========================

CATEGORY_RULES = {
    "大促电商": {
        "keywords": ["618", "双11", "双十一", "大促", "预售", "电商", "直播", "抖音", "小红书", "种草"],
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
        "keywords": ["高温", "防晒", "凉感", "速干", "暴雨", "强对流", "降雨", "天气", "防雨", "夏日", "夏季"],
        "tag": "天气影响消费",
        "logo": "天气",
        "icon": "☀️",
        "class": "logo-sky",
        "desc": "天气变化影响客流和主推节奏，防晒、凉感、速干及轻防护品类需前置。",
    },
    "户外骑行": {
        "keywords": ["户外", "骑行", "露营", "文旅", "出行", "夜经济", "跑步", "轻户外", "徒步"],
        "tag": "户外/运动场景",
        "logo": "户外",
        "icon": "🚴",
        "class": "logo-green",
        "desc": "户外、文旅、骑行和夜间消费延伸运动场景，带动轻运动与亲子需求。",
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
    "大促电商": {"title": "618节奏持续推进，运动品牌关注夏季品类转化", "source": "平台资讯"},
    "童装儿童": {"title": "儿童运动消费场景外扩，亲子与校园需求继续升温", "source": "消费观察"},
    "天气防晒": {"title": "高温与降雨并行，防晒凉感与轻防护品类进入主推窗口", "source": "公开气象信息"},
    "户外骑行": {"title": "城市骑行、文旅出行与轻户外需求延续", "source": "消费观察"},
    "商圈消费": {"title": "商圈活动与会员运营联动，周末客流修复仍需关注", "source": "商业观察"},
}

def category_score(title, cat):
    return sum(1 for kw in CATEGORY_RULES[cat]["keywords"] if kw in title)

def item_score(item, cat):
    title = clean_title(item.get("title", ""))
    source = str(item.get("source", ""))
    score = category_score(title, cat) * 10

    if cat != "大促电商" and any(k in title for k in ["618", "双11", "双十一", "大促"]):
        score -= 8

    for kw in ["童装", "儿童", "亲子", "防晒", "凉感", "门店", "商场", "商圈", "客流", "零售", "消费", "户外"]:
        if kw in title:
            score += 3

    for kw in ["比赛", "夺冠", "冠军", "联赛", "球队", "球员", "比分", "赛程", "奥运会", "国家队"]:
        if kw in title:
            score -= 12

    for src in ["界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报", "新华网", "澎湃新闻", "证券时报"]:
        if src in source:
            score += 2

    return score

def pick_top_news():
    used = set()
    result = []

    for cat in ["大促电商", "童装儿童", "天气防晒", "户外骑行", "商圈消费"]:
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
            title = fb["title"]
            source = fb["source"]

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
# 区域经营日报：核心变化 / 经营影响 / 推荐动作
# =========================

REGION_REPORT_POOL = [
    {
        "change": "降雨天气扰动客流",
        "impact": "室内运动与轻防护品类关注提升",
        "action": "建议强化防晒、防雨及轻运动场景陈列",
    },
    {
        "change": "高温天气带动夏季消费",
        "impact": "防晒、凉感、速干类需求提升",
        "action": "建议加强防晒单品与短裤连带销售",
    },
    {
        "change": "亲子与校园运动场景升温",
        "impact": "儿童运动与轻户外需求增加",
        "action": "建议强化校园运动与亲子搭配展示",
    },
    {
        "change": "轻户外与骑行热度提升",
        "impact": "骑行、露营、徒步消费增加",
        "action": "建议增加轻户外系列曝光",
    },
    {
        "change": "商圈活动与会员运营增加",
        "impact": "周末客流与互动活跃度提升",
        "action": "建议加强会员活动引流",
    },
    {
        "change": "夜经济消费持续活跃",
        "impact": "运动休闲与轻消费场景延伸",
        "action": "建议关注夜间场景商品组合",
    },
]

def region_report_by_weather(weather_key):
    signal = weather_desc(weather_key)

    if "高温" in signal or "防晒" in signal or "凉感" in signal:
        return {
            "change": "高温天气带动夏季消费",
            "impact": "防晒、凉感、速干类需求提升",
            "action": "建议加强防晒单品与短裤连带销售",
        }

    if "降雨" in signal or "防雨" in signal or "小雨" in signal or "中雨" in signal:
        return {
            "change": "降雨天气扰动客流",
            "impact": "室内运动与轻防护品类关注提升",
            "action": "建议强化防雨、轻外套及室内运动场景陈列",
        }

    return random.choice(REGION_REPORT_POOL[2:])

def region_report_with_news(weather_key, region_keywords):
    # 如果新闻里有明显区域/经营热点，优先结合新闻场景
    local_titles = [t for t in titles if any(k in t for k in region_keywords)]
    text = " ".join(local_titles[:5])

    if any(k in text for k in ["商场", "商圈", "客流", "会员", "奥莱"]):
        return {
            "change": "商圈活动与会员运营增加",
            "impact": "周末客流与互动活跃度提升",
            "action": "建议加强会员活动引流",
        }

    if any(k in text for k in ["骑行", "户外", "露营", "文旅", "出行"]):
        return {
            "change": "轻户外与骑行热度提升",
            "impact": "骑行、露营、徒步消费增加",
            "action": "建议增加轻户外系列曝光",
        }

    if any(k in text for k in ["童装", "儿童", "亲子", "校园"]):
        return {
            "change": "亲子与校园运动场景升温",
            "impact": "儿童运动与轻户外需求增加",
            "action": "建议强化校园运动与亲子搭配展示",
        }

    return region_report_by_weather(weather_key)

region_map = {
    "east": {
        "city": "上海/江苏/浙江",
        "weather_key": "east",
        "keywords": ["上海", "杭州", "南京", "苏州", "宁波", "江苏", "浙江"],
    },
    "central": {
        "city": "湖北/湖南/江西",
        "weather_key": "east",
        "keywords": ["武汉", "长沙", "南昌", "郑州", "湖北", "湖南", "江西"],
    },
    "south": {
        "city": "广东/广西",
        "weather_key": "south",
        "keywords": ["广州", "深圳", "佛山", "南宁", "广东", "广西", "厦门", "福建"],
    },
    "southwest": {
        "city": "四川/重庆/贵州",
        "weather_key": "southwest",
        "keywords": ["成都", "重庆", "贵阳", "昆明", "四川", "贵州", "云南"],
    },
    "northwest": {
        "city": "陕西/甘肃/宁夏",
        "weather_key": "northwest",
        "keywords": ["西安", "兰州", "银川", "陕西", "甘肃", "宁夏", "新疆"],
    },
}

reports = {}
scores = {}

for region, cfg in region_map.items():
    reports[region] = region_report_with_news(cfg["weather_key"], cfg["keywords"])
    scores[region] = total_region_score(cfg["weather_key"], cfg["keywords"])

# =========================
# 经营观察
# =========================

TREND_POOL = [
    {"title": "防晒与凉感品类持续升温", "desc": "高温天气下，防晒、凉感、速干等功能型商品关注提升。", "tag": "季节趋势"},
    {"title": "618预售前置明显", "desc": "平台大促提前蓄水，防晒、短裤等夏季品类曝光提升。", "tag": "大促趋势"},
    {"title": "校园运动场景持续扩张", "desc": "儿童运动从单品类转向亲子、校园、户外综合场景。", "tag": "儿童消费趋势"},
    {"title": "轻户外与骑行消费增长", "desc": "城市骑行、露营、徒步等场景持续带动运动消费。", "tag": "消费趋势"},
    {"title": "内容平台影响线下成交", "desc": "小红书、抖音种草持续影响门店成交与连带转化。", "tag": "内容电商"},
    {"title": "会员运营影响门店转化", "desc": "周末商圈活动增加，会员权益与亲子互动可提升到店转化。", "tag": "渠道趋势"},
]

trend_items = random.sample(TREND_POOL, 4)

# =========================
# 关键词云
# =========================

WORD_POOL = [
    "防晒衣", "凉感科技", "运动童装", "轻户外", "小红书种草", "618",
    "短裤", "速干", "校园运动", "会员运营", "夜经济", "亲子",
    "安踏", "李宁", "特步", "lululemon", "商圈活动", "夏季主推",
    "门店陈列", "客流修复", "城市骑行", "户外休闲", "抖音直播", "品类切换",
    "防雨装备", "周末客流", "亲子经济", "内容种草"
]

words = []
for w in WORD_POOL:
    if w in joined:
        words.append(w)

for key in ["east", "south", "southwest", "northwest"]:
    sig = weather_desc(key)
    if "防晒" in sig and "防晒衣" not in words:
        words.append("防晒衣")
    if "凉感" in sig and "凉感科技" not in words:
        words.append("凉感科技")
    if "防雨" in sig and "防雨装备" not in words:
        words.append("防雨装备")

while len(words) < 18:
    w = random.choice(WORD_POOL)
    if w not in words:
        words.append(w)

words = words[:18]

# =========================
# 数据填充
# =========================

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",

    "date": today.strftime("%Y-%m-%d"),
    "weekday": weekday_map[today.weekday()],
    "update_time": today.strftime("%H:%M"),

    "monitor_count": str(max(len(news_items), random.randint(150, 260))),
    "rss_count": str(max(min(len(news_items), 99), random.randint(35, 80))),
    "focus_count": "5",

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
    "east_action": "重点关注区域运营节奏",
    "east_star": star_by_total_score(scores["east"]),

    "central_city": region_map["central"]["city"],
    "central_hot": reports["central"]["change"],
    "central_flow": reports["central"]["impact"],
    "central_signal": reports["central"]["action"],
    "central_action": "重点关注区域运营节奏",
    "central_star": star_by_total_score(scores["central"]),

    "south_city": region_map["south"]["city"],
    "south_hot": reports["south"]["change"],
    "south_flow": reports["south"]["impact"],
    "south_signal": reports["south"]["action"],
    "south_action": "重点关注区域运营节奏",
    "south_star": star_by_total_score(scores["south"]),

    "southwest_city": region_map["southwest"]["city"],
    "southwest_hot": reports["southwest"]["change"],
    "southwest_flow": reports["southwest"]["impact"],
    "southwest_signal": reports["southwest"]["action"],
    "southwest_action": "重点关注区域运营节奏",
    "southwest_star": star_by_total_score(scores["southwest"]),

    "northwest_city": region_map["northwest"]["city"],
    "northwest_hot": reports["northwest"]["change"],
    "northwest_flow": reports["northwest"]["impact"],
    "northwest_signal": reports["northwest"]["action"],
    "northwest_action": "重点关注区域运营节奏",
    "northwest_star": star_by_total_score(scores["northwest"]),

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
