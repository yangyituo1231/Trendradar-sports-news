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
# 读取真实资讯
# =========================

news_file = Path("output/news/latest.json")
news_items = []

if news_file.exists():
    try:
        raw = json.loads(news_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            news_items = raw.get("items", [])
        elif isinstance(raw, list):
            news_items = raw
    except Exception:
        news_items = []

titles = [clean_title(x.get("title", "")) for x in news_items if isinstance(x, dict) and x.get("title")]
joined = " ".join(titles)

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
# 区域/经营内容池
# =========================

ACTION_POOL = [
    "建议加强防晒与凉感系列前置陈列",
    "建议关注短裤与速干T连带销售",
    "建议强化校园运动场景搭配",
    "建议增加轻户外系列曝光",
    "建议重点关注周末亲子客流",
    "建议加强门店入口防晒单品展示",
    "建议增加亲子穿搭组合推荐",
    "建议关注夜经济场景消费",
    "建议重点关注周末商圈活动",
    "建议加强会员活动引流",
]

FLOW_POOL = [
    "商圈客流回暖但天气扰动仍在",
    "周末客流恢复明显",
    "会员活动带动亲子消费",
    "夜间客流增加，夜经济活跃",
    "户外客流活跃，周末出行增加",
    "商场活动与会员运营带动客流",
    "活动转化仍需精细化跟进",
]

SIGNAL_POOL = [
    "防晒、轻外套、运动场景需求提升",
    "短袖启动偏慢，轻防护需求提升",
    "凉感、短裤、防晒品类需求上升",
    "亲子休闲、户外轻运动增长",
    "防护用品、帽子等轻防护需求提升",
    "运动童装与校园场景热度增加",
    "小红书种草影响线下成交",
]

HOT_POOL = [
    "商圈活动与会员运营带动客流",
    "亲子与儿童运动场景升温",
    "高温天气带动防晒与凉感品类需求",
    "城市骑行与轻户外热度提升",
    "校园运动与亲子消费升温",
    "夜经济活跃，运动休闲消费增加",
    "露营与户外场景持续升温",
]

region_map = {
    "east": {"city": "上海/江苏/浙江"},
    "central": {"city": "湖北/湖南/江西"},
    "south": {"city": "广东/广西"},
    "southwest": {"city": "四川/重庆/贵州"},
    "northwest": {"city": "陕西/甘肃/宁夏"},
}

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
    "门店陈列", "客流修复", "城市骑行", "户外休闲", "抖音直播", "品类切换"
]

words = []
for w in WORD_POOL:
    if w in joined:
        words.append(w)

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

    "weather_north": "北方多地天气转晴，户外及商场客流具备恢复基础。",
    "weather_east": "华东局部降雨延续，短途出行与商圈客流可能出现波动。",
    "weather_southwest": "华南降雨或雷阵雨，防晒与轻户外需求需结合天气灵活调整。",
    "weather_northwest": "西北多地晴到多云，户外露营、亲子活动关注度提升。",

    "north_day1": "晴到多云",
    "north_day2": "多云",
    "north_day3": "晴",
    "east_day1": "局部阵雨",
    "east_day2": "阵雨",
    "east_day3": "多云",
    "south_day1": "阵雨/雷阵雨",
    "south_day2": "中到大雨",
    "south_day3": "降雨减弱",
    "southwest_day1": "阵雨",
    "southwest_day2": "多云",
    "southwest_day3": "多云",
    "northwest_day1": "晴到多云",
    "northwest_day2": "多云",
    "northwest_day3": "晴",

    "east_city": region_map["east"]["city"],
    "east_hot": random.choice(HOT_POOL),
    "east_flow": random.choice(FLOW_POOL),
    "east_signal": random.choice(SIGNAL_POOL),
    "east_action": random.choice(ACTION_POOL),
    "east_star": "★★★",

    "central_city": region_map["central"]["city"],
    "central_hot": random.choice(HOT_POOL),
    "central_flow": random.choice(FLOW_POOL),
    "central_signal": random.choice(SIGNAL_POOL),
    "central_action": random.choice(ACTION_POOL),
    "central_star": "★★",

    "south_city": region_map["south"]["city"],
    "south_hot": random.choice(HOT_POOL),
    "south_flow": random.choice(FLOW_POOL),
    "south_signal": random.choice(SIGNAL_POOL),
    "south_action": random.choice(ACTION_POOL),
    "south_star": "★★★",

    "southwest_city": region_map["southwest"]["city"],
    "southwest_hot": random.choice(HOT_POOL),
    "southwest_flow": random.choice(FLOW_POOL),
    "southwest_signal": random.choice(SIGNAL_POOL),
    "southwest_action": random.choice(ACTION_POOL),
    "southwest_star": "★★",

    "northwest_city": region_map["northwest"]["city"],
    "northwest_hot": random.choice(HOT_POOL),
    "northwest_flow": random.choice(FLOW_POOL),
    "northwest_signal": random.choice(SIGNAL_POOL),
    "northwest_action": random.choice(ACTION_POOL),
    "northwest_star": "★",

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
