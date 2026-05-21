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
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        pass

    # 优先取数组，再取对象，避免对象正则吞掉数组内对象
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    match = re.search(r"\{.*\}", text, re.S)
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
            temperature=0.22,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content.strip()
        return extract_json(text)
    except Exception as e:
        print("DeepSeek JSON error:", repr(e))
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
    except Exception as e:
        print("DeepSeek text error:", repr(e))
        return None

# =========================
# 区域评分
# =========================

def news_heat_score(keywords):
    score = 0
    for t in titles:
        if any(k in t for k in keywords):
            score += 5
        if any(k in t for k in ["618", "大促", "防晒", "凉感", "童装", "儿童", "亲子", "商场", "商圈", "客流", "户外", "骑行", "赛事", "跑步", "马拉松", "GDP", "社零", "消费", "就业", "政策", "文旅", "AI"]):
            score += 1
    return min(score, 25)

def business_keyword_score():
    score = 0
    for k in ["防晒", "凉感", "童装", "儿童", "亲子", "618", "商场", "商圈", "客流", "户外", "骑行", "小红书", "抖音", "保暖", "防滑", "赛事", "跑步", "马拉松", "GDP", "社零", "消费", "就业", "政策", "文旅", "AI", "出海"]:
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

def topic_key(title):
    title = clean_title(title)
    title = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]「」“”\"'《》]", "", title)

    groups = {
        "品牌PK": ["安踏", "李宁", "特步", "361", "度", "PK", "对比", "谁更", "成绩单", "克阿迪"],
        "平台大促": ["618", "大促", "预售", "战报", "抖音", "天猫", "京东", "唯品", "直播"],
        "防晒凉感": ["防晒", "凉感", "速干", "高温", "夏天", "防晒衣"],
        "户外跑步": ["户外", "跑步", "跑鞋", "骑行", "露营", "徒步", "马拉松", "越野跑"],
        "童装儿童": ["童装", "儿童", "亲子", "校园", "童鞋", "青少年", "Kappa Kids"],
        "商圈客流": ["商场", "商圈", "门店", "客流", "会员", "奥莱", "购物中心"],
        "宏观消费": ["GDP", "社零", "消费", "就业", "收入", "政策", "补贴", "内需"],
        "文旅出行": ["文旅", "旅游", "暑期", "出行", "景区", "亲子游"],
        "AI科技": ["AI", "人工智能", "机器人", "智能", "大模型", "科技"],
    }

    for k, words in groups.items():
        if any(w in title for w in words):
            return k

    return title[:12]


CATEGORY_RULES = {
    "电商平台": {
        "keywords": ["618", "双11", "双十一", "双12", "大促", "预售", "电商", "直播", "抖音", "小红书", "种草", "百亿补贴", "战报", "平台", "店播"],
        "tag": "大促/电商", "logo": "大促", "icon": "🛒", "class": "logo-blue",
        "desc": "平台流量与大促节奏变化，重点观察夏季品类曝光、直播转化与终端承接。",
    },
    "品牌竞争": {
        "keywords": ["品牌", "Nike", "耐克", "阿迪", "安踏", "李宁", "特步", "361", "Kappa", "HOKA", "昂跑", "亚瑟士", "C位", "市场份额", "PK"],
        "tag": "品牌竞争", "logo": "品牌", "icon": "🏷️", "class": "logo-purple",
        "desc": "品牌动作反映行业竞争重心，需关注价格带、产品心智与渠道打法变化。",
    },
    "童装儿童": {
        "keywords": ["童装", "儿童", "亲子", "校园", "儿童运动", "运动童装", "Kids", "KIDS", "童鞋", "青少年"],
        "tag": "童装/儿童运动", "logo": "童装", "icon": "🧒", "class": "logo-sky",
        "desc": "儿童消费从单品购买转向亲子、校园、户外和运动场景综合经营。",
    },
    "天气消费": {
        "keywords": ["高温", "防晒", "凉感", "速干", "暴雨", "强对流", "降雨", "天气", "防雨", "夏日", "夏季", "降雪", "结冰", "低温", "防滑", "保暖"],
        "tag": "天气/功能消费", "logo": "天气", "icon": "☀️", "class": "logo-sky",
        "desc": "天气变化影响客流和主推节奏，防晒、凉感、防雨、防滑及保暖品类需动态前置。",
    },
    "户外运动": {
        "keywords": ["户外", "骑行", "露营", "文旅", "出行", "夜经济", "跑步", "轻户外", "徒步", "马拉松", "越野跑", "赛事", "训练", "跑鞋"],
        "tag": "户外/运动场景", "logo": "户外", "icon": "🚴", "class": "logo-green",
        "desc": "户外、跑步、骑行、赛事和夜间消费延伸运动场景，带动装备与亲子需求。",
    },
    "商圈零售": {
        "keywords": ["商场", "商圈", "门店", "客流", "奥莱", "折扣", "会员", "零售", "本地生活", "购物中心"],
        "tag": "商圈/零售经营", "logo": "商圈", "icon": "🏬", "class": "logo-dark",
        "desc": "商圈活动、会员运营和折扣零售影响周末客流与终端转化效率。",
    },
    "宏观消费": {
        "keywords": ["GDP", "社零", "社会消费品", "消费", "CPI", "PPI", "经济", "收入", "就业", "信心", "政策", "补贴", "以旧换新", "内需"],
        "tag": "宏观消费", "logo": "宏观", "icon": "📊", "class": "logo-dark",
        "desc": "宏观消费与收入预期影响零售信心，需关注客单、折扣和会员活跃变化。",
    },
    "文旅出行": {
        "keywords": ["文旅", "旅游", "暑期", "出行", "景区", "演唱会", "赛事", "周末", "亲子游", "酒店", "交通"],
        "tag": "文旅出行", "logo": "文旅", "icon": "🧳", "class": "logo-green",
        "desc": "文旅与城市出行带动周末客流，亲子、轻户外和功能鞋服存在连带机会。",
    },
    "AI科技": {
        "keywords": ["AI", "人工智能", "机器人", "智能", "科技", "算法", "大模型", "智能硬件"],
        "tag": "AI科技", "logo": "AI", "icon": "🤖", "class": "logo-blue",
        "desc": "AI与智能硬件热点提升科技心智，可观察运动科技、内容种草和人群触达机会。",
    },
    "政策监管": {
        "keywords": ["政策", "监管", "标准", "质量", "抽检", "合规", "补贴", "消费券", "促消费"],
        "tag": "政策监管", "logo": "政策", "icon": "📌", "class": "logo-red",
        "desc": "政策与监管变化影响渠道节奏、消费者信心和终端活动设计。",
    },
}

fallback_by_category = {
    "电商平台": {"title": "平台大促进入预热期，夏季功能品类承接需前置", "source": "平台资讯"},
    "品牌竞争": {"title": "运动品牌竞争加剧，产品心智与渠道效率成为关键", "source": "行业观察"},
    "童装儿童": {"title": "儿童运动消费场景外扩，亲子与校园需求继续升温", "source": "消费观察"},
    "天气消费": {"title": "天气变化影响客流节奏，功能品类进入动态调整窗口", "source": "公开气象信息"},
    "户外运动": {"title": "跑步、骑行与轻户外场景延续，运动装备需求扩张", "source": "消费观察"},
    "商圈零售": {"title": "商圈活动与会员运营联动，周末客流修复仍需关注", "source": "商业观察"},
    "宏观消费": {"title": "宏观消费信心分化，零售端需关注客单与折扣效率", "source": "宏观观察"},
    "文旅出行": {"title": "文旅出行热度延续，亲子轻户外场景值得承接", "source": "文旅观察"},
    "AI科技": {"title": "AI科技热度延续，运动品牌内容与效率工具值得关注", "source": "科技观察"},
    "政策监管": {"title": "促消费与监管信息需跟踪，终端活动应兼顾效率与合规", "source": "政策观察"},
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
        "小红书", "抖音", "Nike", "耐克", "阿迪", "安踏", "李宁", "特步", "HOKA",
        "昂跑", "亚瑟士", "361", "GDP", "社零", "消费", "就业", "政策", "文旅", "AI", "出海"
    ]

    for kw in value_words:
        if kw in title:
            score += 4

    bad_words = ["比分", "赛程", "夺冠", "冠军", "主教练", "球队", "球员", "转会", "受伤"]
    for kw in bad_words:
        if kw in title:
            score -= 16

    reliable_sources = ["界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报", "新华网", "澎湃新闻", "证券时报", "新京报", "新浪财经", "国家统计局", "央视新闻"]
    for src in reliable_sources:
        if src in source:
            score += 2

    return score


def pick_top_news_rule():
    used_titles = set()
    used_topics = set()
    used_cats = set()
    result = []

    priority = ["电商平台", "品牌竞争", "童装儿童", "天气消费", "户外运动", "商圈零售", "宏观消费", "文旅出行", "AI科技", "政策监管"]

    candidates = []

    for item in news_items:
        if not isinstance(item, dict):
            continue

        title = clean_title(item.get("title", ""))
        if not title:
            continue

        best_cat = max(priority, key=lambda c: item_score(item, c))
        score = item_score(item, best_cat)

        if score > 0:
            candidates.append((score, best_cat, item))

    candidates.sort(key=lambda x: x[0], reverse=True)

    for _, cat, item in candidates:
        if len(result) >= 5:
            break

        title = short(item.get("title", ""), 42)
        tk = topic_key(title)

        if not title or title in used_titles or tk in used_topics:
            continue

        if cat == "电商平台" and cat in used_cats:
            continue

        rule = CATEGORY_RULES[cat]

        result.append({
            "title": title,
            "tag": rule["tag"],
            "source": item.get("source", "公开资讯"),
            "desc": rule["desc"],
            "logo": rule["logo"],
            "icon": rule["icon"],
            "class": rule["class"],
            "link": item.get("link") or item.get("url") or item.get("href") or "",
        })

        used_titles.add(title)
        used_topics.add(tk)
        used_cats.add(cat)

    for cat in priority:
        if len(result) >= 5:
            break

        fb = fallback_by_category[cat]
        tk = topic_key(fb["title"])

        if fb["title"] in used_titles or tk in used_topics:
            continue

        rule = CATEGORY_RULES[cat]

        result.append({
            "title": fb["title"],
            "tag": rule["tag"],
            "source": fb["source"],
            "desc": rule["desc"],
            "logo": rule["logo"],
            "icon": rule["icon"],
            "class": rule["class"],
            "link": "",
        })

        used_titles.add(fb["title"])
        used_topics.add(tk)
        used_cats.add(cat)

    return result[:5]


def pick_top_news_deepseek():
    if not titles:
        return pick_top_news_rule()

    news_text = "\n".join(
        f"{i+1}. {clean_title(item.get('title',''))}｜{item.get('source','')}"
        for i, item in enumerate(news_items[:55])
        if isinstance(item, dict) and item.get("title")
    )

    allowed_categories = "、".join(CATEGORY_RULES.keys())

    prompt = f"""
你是运动鞋服行业资讯筛选助手。请从以下新闻中选出5条最适合361°儿童经营管理部每日阅读的重点资讯。

要求：
1. 必须基于今日新闻生成，不得使用历史模板和固定排序；
2. 优先选择当天最新、信息增量最大、对经营最有参考价值的新闻；
3. 不要让“618战报/抖音战报/大促战报”连续固定排第一，除非它确实是当天最重要新闻；
4. 如果多条新闻主题相似，只保留1条，优先发布时间更新、信息更具体的一条；
5. 覆盖范围要更广：电商平台、品牌竞争、童装儿童、天气消费、户外运动、商圈零售、宏观消费、GDP/社零、就业收入、文旅出行、AI科技、政策监管；
6. GDP、社零、就业、消费信心、促消费政策、文旅客流等宏观新闻，如果对零售经营有启示，可以优先入选；
7. 过滤纯体育比赛比分、球员转会、娱乐八卦；
8. 输出严格JSON数组，长度5；
9. 每项包含：title、category、reason；
10. category只能从以下选择：{allowed_categories}；
11. reason控制在28字以内，必须写经营启示，不要空话；
12. 同一主题只能入选1条，例如“安踏/李宁/特步/361对比PK”只能保留最有信息量的一条；
13. 5条应尽量分散在不同方向，不能4条都是品牌PK或618战报。

新闻：
{news_text}
"""

    arr = ask_deepseek_json(prompt, max_tokens=1100)

    if not isinstance(arr, list) or len(arr) < 3:
        result = pick_top_news_rule()
    else:
        source_lookup = {
            clean_title(x.get("title", "")): {
                "source": x.get("source", "公开资讯"),
                "link": x.get("link") or x.get("url") or x.get("href") or "",
            }
            for x in news_items
            if isinstance(x, dict)
        }

        result = []
        used_titles = set()
        used_topics = set()
        used_cats = set()

        for row in arr:
            if len(result) >= 5:
                break

            if not isinstance(row, dict):
                continue

            title = short(row.get("title", ""), 42)
            if not title:
                continue

            tk = topic_key(title)

            if title in used_titles or tk in used_topics:
                continue

            cat = clean_title(row.get("category", "商圈零售"))
            rule = CATEGORY_RULES.get(cat, CATEGORY_RULES["商圈零售"])

            if cat == "电商平台" and cat in used_cats:
                continue

            source = "公开资讯"
            link = ""

            for raw_title, info in source_lookup.items():
                if title[:10] in raw_title or raw_title[:10] in title:
                    source = info["source"]
                    link = info["link"]
                    break

            desc = short_cn(row.get("reason", ""), 32) or rule["desc"]

            result.append({
                "title": title,
                "tag": rule["tag"],
                "source": source,
                "desc": desc,
                "logo": rule["logo"],
                "icon": rule["icon"],
                "class": rule["class"],
                "link": link,
            })

            used_titles.add(title)
            used_topics.add(tk)
            used_cats.add(cat)

        fallback = pick_top_news_rule()

        for item in fallback:
            if len(result) >= 5:
                break

            tk = topic_key(item["title"])

            if item["title"] not in used_titles and tk not in used_topics:
                result.append(item)
                used_titles.add(item["title"])
                used_topics.add(tk)

    # 输出给企业微信markdown使用，避免markdown继续发原始重复新闻
    try:
        Path("output/news").mkdir(parents=True, exist_ok=True)
        Path("output/news/top_news.json").write_text(
            json.dumps({"items": result}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print("write top_news.json error:", repr(e))

    return result[:5]


top_news = pick_top_news_deepseek()

# =========================
# 区域经营雷达
# =========================

region_map = {
    "east": {"name": "华东", "city": "上海/江苏/浙江", "weather_key": "east", "keywords": ["上海", "杭州", "南京", "苏州", "宁波", "江苏", "浙江"]},
    "central": {"name": "华中", "city": "湖北/湖南/江西", "weather_key": "east", "keywords": ["武汉", "长沙", "南昌", "郑州", "湖北", "湖南", "江西", "河南"]},
    "south": {"name": "华南", "city": "广东/广西", "weather_key": "south", "keywords": ["广州", "深圳", "佛山", "南宁", "广东", "广西", "厦门", "福建"]},
    "southwest": {"name": "西南", "city": "四川/重庆/贵州", "weather_key": "southwest", "keywords": ["成都", "重庆", "贵阳", "昆明", "四川", "贵州", "云南"]},
    "northwest": {"name": "西北", "city": "陕西/甘肃/宁夏", "weather_key": "northwest", "keywords": ["西安", "兰州", "银川", "陕西", "甘肃", "宁夏", "新疆"]},
}

SCENE_POOLS = {
    "rain": {
        "hot": ["雨天到店承接", "降雨影响客流", "室内场景前置"],
        "flow": ["客流更容易向商场和室内运动场景集中"],
        "signal": ["防雨、防滑、轻防护和室内运动品类承接更关键"],
        "action": ["强化防雨防滑陈列，前置室内运动和试穿体验"],
    },
    "high_temp": {
        "hot": ["暑热带动功能消费", "防晒凉感窗口", "夏季品类前置"],
        "flow": ["防晒、凉感、速干和短裤T恤关注度提升"],
        "signal": ["防晒衣、凉感T、速干短裤和透气童鞋进入主推窗口"],
        "action": ["前置防晒凉感组合，强化夏季功能区和连带陈列"],
    },
    "promotion": {
        "hot": ["平台热度外溢", "大促心智强化", "直播同款承接"],
        "flow": ["线上内容种草可能外溢到门店试穿和比价"],
        "signal": ["大促和直播同款强化价格心智，门店需承接爆款和套装需求"],
        "action": ["强化爆款价格带、直播同款提示和导购转化话术"],
    },
    "kids": {
        "hot": ["亲子运动延伸", "校园场景活跃", "童装连带提升"],
        "flow": ["亲子、校园和周末运动场景带动童鞋童服组合"],
        "signal": ["儿童运动、校园和亲子场景继续带动鞋服组合需求"],
        "action": ["强化亲子校园陈列，提升童鞋服装和配件连带"],
    },
    "outdoor": {
        "hot": ["轻户外客群活跃", "城市出行升温", "文旅场景延伸"],
        "flow": ["骑行、露营、文旅和亲子户外带动装备需求"],
        "signal": ["轻户外、帽包配件、防晒装备和舒适鞋履存在连带空间"],
        "action": ["增加轻户外组合，强化出行场景和帽包配件展示"],
    },
    "mall": {
        "hot": ["商圈活动承接", "会员转化关键", "门店体验强化"],
        "flow": ["商场活动和会员运营影响到店停留与成交效率"],
        "signal": ["商圈客流修复仍依赖会员活动、陈列展示和导购试穿转化"],
        "action": ["加强会员活动、门口堆头、场景陈列和导购试穿转化"],
    },
    "macro": {
        "hot": ["消费信心分化", "宏观消费跟踪", "客单压力关注"],
        "flow": ["收入预期和社零变化可能影响客单、折扣敏感度和会员复购"],
        "signal": ["宏观消费分化下，中低价格带、功能刚需和会员精细化更关键"],
        "action": ["关注价格带结构，优化折扣节奏和会员分层触达"],
    },
    "tech": {
        "hot": ["AI科技热度外溢", "智能内容种草", "科技心智升温"],
        "flow": ["AI和智能硬件话题提升年轻家庭对科技运动装备的关注"],
        "signal": ["科技热点可转化为运动科技、功能面料和智能内容种草机会"],
        "action": ["强化运动科技卖点表达，结合短视频内容进行场景化种草"],
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
    if any(k in text for k in ["618", "大促", "预售", "战报", "直播", "抖音", "小红书"]):
        scenes.append("promotion")
    if any(k in text for k in ["童装", "儿童", "亲子", "校园", "青少年"]):
        scenes.append("kids")
    if any(k in text for k in ["户外", "骑行", "露营", "文旅", "出行", "赛事"]):
        scenes.append("outdoor")
    if any(k in text for k in ["商场", "商圈", "客流", "门店", "会员", "购物中心"]):
        scenes.append("mall")
    if any(k in text for k in ["GDP", "社零", "消费", "就业", "收入", "政策", "补贴", "内需"]):
        scenes.append("macro")
    if any(k in text for k in ["AI", "人工智能", "机器人", "智能", "科技"]):
        scenes.append("tech")

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
        local_text = " ".join(local_titles[:10]) or joined[:500]
        scenes = detect_scene_rule(local_text, cfg["weather_key"])

        reports[region] = {
            "change": pick_scene_word(scenes, "hot"),
            "impact": pick_scene_word(scenes, "flow"),
            "action": pick_scene_word(scenes, "signal"),
        }
        actions[region] = pick_scene_word(scenes, "action")

    return reports, actions

def region_news_text_for(cfg):
    local_titles = [t for t in titles if any(k in t for k in cfg["keywords"])]
    if not local_titles:
        local_titles = titles[:12]
    return "\n".join(local_titles[:12])

def build_one_region_deepseek(region, cfg, top_news_text, global_news_text):
    local_news_text = region_news_text_for(cfg)
    weather_text = f"{weather_desc(cfg['weather_key'])}；未来三天：{weather_day_label(cfg['weather_key'],0)}、{weather_day_label(cfg['weather_key'],1)}、{weather_day_label(cfg['weather_key'],2)}"

    prompt = f"""
你是361°儿童总部经营管理部的区域经营分析师。
请为【{cfg['name']}（{cfg['city']}）】生成日报表格中的一行“区域经营雷达”。

必须基于当天信息，不要套用固定区域模板。
优先使用本区域新闻；如果本区域新闻不足，再结合全国宏观消费、天气、平台热点和品类趋势推断，但必须写出具体触发因素。

输出严格JSON对象，不要解释，字段只能是：
hot, flow, signal, action

字段要求：
hot：14-22字，核心信号，必须体现一个具体触发因素。
flow：24-38字，判断客流从哪里来、往哪里去、什么场景更强。
signal：40-60字，结合天气/新闻/品类机会，说明消费机会或潜在风险。
action：40-60字，具体到门店、商品、陈列、会员、导购、直播同款或商圈承接动作。

限制：
1. 不要写“降雨扰动客流”“会员运营增强”“关注提升”这种模板词；
2. 必须出现至少一个具体因素：本地新闻、天气、平台大促、宏观消费、文旅出行、AI科技、品牌动作或品类机会；
3. 语气像总部给区域销售看的经营提醒，不像天气说明；
4. 短句、有信息密度，适合放进日报表格。

本区域新闻：
{local_news_text}

今日TOP资讯：
{top_news_text}

全局新闻摘要：
{global_news_text}

天气：
{weather_text}
"""
    obj = ask_deepseek_json(prompt, max_tokens=650)
    if not isinstance(obj, dict):
        return None

    required = ["hot", "flow", "signal", "action"]
    if not all(clean_title(obj.get(k, "")) for k in required):
        return None

    # 过滤明显模板化输出，失败则交给规则兜底
    bad_phrases = ["降雨扰动客流", "会员运营增强", "关注提升", "需求增加", "商场活动更关键"]
    joined_obj = "".join(clean_title(obj.get(k, "")) for k in required)
    if any(p in joined_obj for p in bad_phrases):
        return None

    return {
        "hot": short_cn(obj.get("hot", ""), 24),
        "flow": short_cn(obj.get("flow", ""), 42),
        "signal": short_cn(obj.get("signal", ""), 66),
        "action": short_cn(obj.get("action", ""), 66),
    }

def build_region_reports_deepseek():
    fallback_reports, fallback_actions = build_region_reports_rule()

    top_news_text = "\n".join([f"{i+1}. {x['title']}｜{x['tag']}" for i, x in enumerate(top_news)])
    global_news_text = "\n".join(titles[:30])

    reports = {}
    actions = {}

    for region, cfg in region_map.items():
        row = build_one_region_deepseek(region, cfg, top_news_text, global_news_text)

        if row is None:
            reports[region] = fallback_reports[region]
            actions[region] = fallback_actions[region]
            continue

        reports[region] = {
            "change": row["hot"],
            "impact": row["flow"],
            "action": row["signal"],
        }
        actions[region] = row["action"]

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
    if any(k in joined for k in ["GDP", "社零", "消费", "就业", "收入", "政策", "内需"]):
        return "宏观消费与平台流量共同影响零售节奏，价格带、客流与功能品类需同步跟踪。"
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
请基于以下新闻，写一句今日行业判断。
要求：
1. 可以覆盖运动鞋服、童装、宏观消费、社零/GDP、文旅出行、AI科技和平台流量；
2. 只讲资讯趋势，不写门店执行动作；
3. 45字以内；
4. 不要口号，不要空话。

新闻：
{chr(10).join(titles[:30])}
"""
    text = ask_deepseek_text(prompt, max_tokens=120)
    if not text:
        return make_today_insight_rule()
    return text[:70]

def make_ai_summary_rule():
    parts = []

    if any(k in joined for k in ["GDP", "社零", "消费", "就业", "收入", "政策", "内需"]):
        parts.append("宏观消费与收入预期影响零售信心")
    if any(k in joined for k in ["618", "大促", "预售", "战报"]):
        parts.append("大促与平台流量仍是短期主线")
    if any(k in joined for k in ["防晒", "凉感", "速干", "高温"]):
        parts.append("防晒、凉感、速干等夏季功能品类升温")
    if any(k in joined for k in ["童装", "儿童", "亲子", "校园"]):
        parts.append("儿童运动与亲子校园场景延续")
    if any(k in joined for k in ["户外", "骑行", "露营", "跑步", "赛事", "文旅"]):
        parts.append("轻户外与文旅场景带动鞋服装备关注")
    if any(weather_business_type(k) in ["rain", "storm"] for k in ["north", "east", "south", "southwest", "northwest"]):
        parts.append("降雨天气可能影响区域客流")

    if not parts:
        parts.append("今日行业信息整体平稳，关注商圈客流、商品节奏和区域差异")

    return "；".join(parts[:4]) + "。"

def make_ai_summary_deepseek():
    news_text = "\n".join(titles[:35])
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
2. 可覆盖：宏观消费/GDP社零、平台流量、大促、夏季功能品类、儿童运动、文旅出行、AI科技、天气对客流影响；
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

def make_ai_warnings():
    news_text = "\n".join(titles[:30])
    weather_text = "；".join([
        weather_desc("north"),
        weather_desc("east"),
        weather_desc("south"),
        weather_desc("southwest"),
        weather_desc("northwest"),
    ])

    prompt = f"""
你是361°儿童经营管理负责人。

请基于：
1. 今日行业新闻
2. 全国天气
3. 电商大促
4. 区域消费趋势
5. 宏观消费、政策、社零/GDP、文旅出行、AI科技热点

生成3条经营风险/机会预警。

要求：
1. 输出严格JSON数组；
2. 每条30-50字；
3. 必须像总部经营预警；
4. 不要空话；
5. 必须具体到客流、品类、会员、直播、天气、商圈、区域、价格带或政策影响。

新闻：
{news_text}

天气：
{weather_text}
"""
    arr = ask_deepseek_json(prompt, max_tokens=400)

    if not isinstance(arr, list):
        return [
            "平台流量和促消费信息交织，需关注核心SKU库存、价格带和直播同款承接。",
            "局地降雨影响到店节奏，室内客流承接能力将影响周末门店转化效率。",
            "轻户外与亲子场景持续升温，帽包、防晒与运动凉鞋存在连带增长机会。"
        ]

    result = []
    for x in arr:
        t = clean_title(str(x))
        if t:
            result.append(t[:60])

    while len(result) < 3:
        result.append("区域消费与天气变化仍需动态关注。")

    return result[:3]

warnings = make_ai_warnings()

# =========================
# 第四部分
# =========================

def build_ai_trends_rule():
    # 兜底也要基于当日新闻关键词，不再返回固定模板
    candidates = []
    if any(k in joined for k in ["GDP", "社零", "消费", "就业", "政策", "收入"]):
        candidates.append({
            "title": "宏观消费影响客单",
            "desc": "消费与收入预期变化影响客单和折扣敏感度，门店需优化价格带与会员转化。",
            "tag": "宏观趋势"
        })
    if any(k in joined for k in ["618", "大促", "预售", "直播", "抖音", "小红书"]):
        candidates.append({
            "title": "平台热度外溢门店",
            "desc": "大促和内容种草带动比价与试穿需求，需承接直播同款和核心爆款。",
            "tag": "平台趋势"
        })
    if any(k in joined for k in ["防晒", "凉感", "速干", "高温", "降雨", "防雨"]):
        candidates.append({
            "title": "天气驱动功能陈列",
            "desc": "天气变化带动防晒、凉感、防雨与速干需求，门店陈列需随区域动态调整。",
            "tag": "天气趋势"
        })
    if any(k in joined for k in ["童装", "儿童", "亲子", "校园"]):
        candidates.append({
            "title": "亲子校园带动连带",
            "desc": "儿童运动、亲子和校园场景带动套装与童鞋组合，导购需强化搭配转化。",
            "tag": "儿童趋势"
        })
    if any(k in joined for k in ["户外", "骑行", "露营", "文旅", "出行", "赛事"]):
        candidates.append({
            "title": "文旅户外延伸场景",
            "desc": "文旅、骑行和轻户外带动出行装备需求，帽包、防晒和舒适鞋履可连带。",
            "tag": "场景趋势"
        })
    if any(k in joined for k in ["AI", "人工智能", "机器人", "智能", "科技"]):
        candidates.append({
            "title": "AI热点带动科技心智",
            "desc": "AI和智能硬件话题提升年轻家庭关注，运动科技和功能面料卖点需加强表达。",
            "tag": "科技趋势"
        })

    fallback = [
        {
            "title": "区域客流需要细分",
            "desc": "天气、商圈活动与平台热点影响到店节奏，重点商圈需强化会员和试穿转化。",
            "tag": "客流趋势"
        },
        {
            "title": "夏季商品节奏前置",
            "desc": "夏季功能品类进入高频曝光阶段，防晒、凉感、速干和舒适鞋履需前置陈列。",
            "tag": "季节趋势"
        },
        {
            "title": "会员运营承接流量",
            "desc": "线上种草和商圈活动带来短期客流，门店需用会员活动提升复购和转化。",
            "tag": "会员趋势"
        },
        {
            "title": "亲子出行关注提升",
            "desc": "周末亲子与户外出行场景仍有需求，童装、童鞋和帽包配件可组合推荐。",
            "tag": "亲子趋势"
        },
    ]

    result = []
    for x in candidates + fallback:
        if len(result) >= 4:
            break
        if x["title"] not in [r["title"] for r in result]:
            result.append(x)
    return result[:4]

def build_ai_trends():
    news_text = "\n".join(titles[:40])
    weather_text = "；".join([
        weather_desc("north"),
        weather_desc("east"),
        weather_desc("south"),
        weather_desc("southwest"),
        weather_desc("northwest"),
    ])

    prompt = f"""
你是361°儿童总部经营管理部经营分析负责人。

请基于：
1. 今日行业新闻
2. 天气变化
3. 电商平台动态
4. 运动与户外消费
5. 商圈客流
6. 宏观消费/GDP社零/就业收入/促消费政策
7. 文旅出行、AI科技、品牌竞争

生成4条“经营观察与动作建议”。

要求：
1. 必须基于今日新闻生成，不得使用通用模板；
2. 每条必须体现当天新闻、天气变化、平台变化、宏观消费或科技/文旅热点；
3. 每条标题不能使用“大促节点提前蓄水、儿童运动场景扩张、商圈客流恢复分化、夏季功能品类升温”等固定模板；
4. 每条内容要能看出今天发生了什么、对经营有什么影响；
5. 输出严格JSON数组，长度4；
6. 每条包含 title、desc、tag；
7. title控制在10-18字；
8. desc控制在30-48字；
9. tag控制在4-6字；
10. 不要空话，不要泛泛写“需求提升、场景升温、持续关注”。

如果今日新闻里没有足够增量，也要从“宏观消费、天气变化、平台活动、区域客流、品牌动作、文旅出行、AI科技”里提炼差异，不允许回到固定模板。

新闻：
{news_text}

天气：
{weather_text}
"""

    arr = ask_deepseek_json(prompt, max_tokens=1200)

    if not isinstance(arr, list) or len(arr) < 4:
        return build_ai_trends_rule()

    result = []
    bad_titles = ["大促节点提前蓄水", "儿童运动场景扩张", "商圈客流恢复分化", "夏季功能品类升温"]

    for row in arr:
        if len(result) >= 4:
            break
        if not isinstance(row, dict):
            continue
        title = short_cn(row.get("title", ""), 18)
        desc = short_cn(row.get("desc", ""), 80)
        tag = short_cn(row.get("tag", ""), 8)
        if not title or title in bad_titles:
            continue
        result.append({"title": title, "desc": desc, "tag": tag})

    if len(result) < 4:
        for item in build_ai_trends_rule():
            if len(result) >= 4:
                break
            if item["title"] not in [r["title"] for r in result]:
                result.append(item)

    return result[:4]

trend_items = build_ai_trends()

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

    "AI": "AI", "人工智能": "人工智能", "机器人": "智能机器人", "智能机器人": "智能机器人",
    "国际化": "国际化", "出海": "出海", "00后": "00后", "年轻人": "年轻人",
    "体育精神": "体育精神", "热爱": "热爱运动", "成长": "关注成长",
    "住房": "住房福利", "福利": "员工福利", "健身房": "健身房福利", "蓬勃": "蓬勃发展",
    "多品牌": "多品牌", "解压": "运动最解压", "健康": "健康生活",
    "消费": "消费趋势", "政策": "政策信号", "教育": "教育关注", "就业": "就业趋势",
    "暑期": "暑期消费", "旅游": "文旅消费", "亲子游": "亲子出行",
    "GDP": "GDP", "社零": "社零", "银发": "银发经济", "下沉": "下沉市场",
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
        "AI", "出海", "国际化", "体育精神", "年轻人", "情绪消费", "城市骑行", "健康生活",
        "智能机器人", "运动最解压", "直播带货", "店播增长", "会员裂变", "多品牌",
        "功能面料", "校园体育", "亲子出行", "智能穿戴", "运动社交", "户外露营",
        "山系穿搭", "速干T", "防晒衣", "凉感科技", "碳板跑鞋", "透气跑鞋",
        "新消费", "性价比", "松弛感", "悦己", "国潮", "她经济", "下沉市场", "银发经济",
        "GDP", "社零", "暑假消费"
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
    news_text = "\n".join([
        clean_title(x.get("title", ""))
        for x in news_items[:50]
        if isinstance(x, dict)
    ])

    top_text = "\n".join([
        f"{i+1}. {x['title']}｜{x['tag']}"
        for i, x in enumerate(top_news)
    ])

    weather_text = "；".join([
        weather_desc("north"),
        weather_desc("east"),
        weather_desc("south"),
        weather_desc("southwest"),
        weather_desc("northwest"),
    ])

    prompt = f"""
你是运动鞋服行业情报系统。

请基于：
1. 今日行业新闻
2. TOP重点资讯
3. 全国天气
4. 当前消费趋势
5. 宏观消费、GDP/社零、就业收入、文旅出行、AI科技、社会热点

生成18个适合“行业热词雷达”的真实热词。

要求：
1. 输出严格JSON数组
2. 每个词2-8字
3. 必须更像“当天行业热点”
4. 不要大量重复：儿童运动、品牌站位、户外运动
5. 必须覆盖：鞋服、童装、户外跑步、电商平台、品牌竞争、天气消费、AI科技、年轻人、体育精神、国际化、出海、城市消费、健康生活、社会热点、情绪消费、女性消费、校园体育、智能硬件、多品牌、功能面料、运动社交、健身生活、泛娱乐热点、宏观消费
6. 至少包含：3个当天真实热点、3个运动行业词、3个社会趋势词、2个年轻人消费词、1个宏观/消费信号词
7. 热词风格参考：商业媒体词云、微博热榜、36氪、晚点、虎嗅、抖音热点、消费趋势报告风格。
8. 不要只生成“鞋服品类词”，而是生成“运动行业 × 社会情绪 × 消费趋势 × 科技热点 × 宏观消费”的融合热词。
9. 优先选择能体现“经营趋势中台BI”感的词。
10. 尽量像：防晒衣、凉感科技、运动凉鞋、店播增长、618战报、城市骑行、速干T、山系穿搭、AI、出海、国际化、体育精神、年轻人、情绪消费、健康生活、多品牌、智能机器人、运动最解压、GDP、社零、下沉市场。

TOP资讯：
{top_text}

新闻：
{news_text}

天气：
{weather_text}
"""

    arr = ask_deepseek_json(prompt, max_tokens=650)
    words = []

    if isinstance(arr, list):
        for w in arr:
            w = clean_title(str(w))
            bad_words = [
                "儿童运动", "品牌站位", "户外运动", "运动消费", "消费趋势",
                "行业趋势", "运动品牌", "运动行业"
            ]

            if (
                2 <= len(w) <= 8
                and w not in bad_words
                and w not in words
            ):
                words.append(w)

    for w in build_words_rule():
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

    "warning1": warnings[0],
    "warning2": warnings[1],
    "warning3": warnings[2],

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
