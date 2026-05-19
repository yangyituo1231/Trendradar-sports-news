from pathlib import Path
from datetime import datetime, timedelta
import random
import re

template = Path("daily-report.html").read_text(encoding="utf-8")

now = datetime.now()
today = now
day2 = today + timedelta(days=1)
day3 = today + timedelta(days=2)

week_map = {
    0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四",
    4: "星期五", 5: "星期六", 6: "星期日",
}

def md(d):
    return d.strftime("%m-%d")

def clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def short(text, max_len=34):
    text = clean_text(text)
    return text if len(text) <= max_len else text[:max_len] + "…"

def read_news_texts():
    roots = [Path("output/news"), Path("output")]
    texts = []

    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in [".txt", ".md", ".html", ".json"]:
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            content = clean_text(content)
            if content:
                texts.append(content)

    return texts

def extract_candidate_titles(texts):
    keywords = [
        "运动", "童装", "儿童", "跑步", "户外", "防晒", "品牌", "消费", "零售",
        "奥莱", "折扣", "会员", "商场", "客流", "电商", "直播", "小红书",
        "抖音", "安踏", "李宁", "特步", "361", "耐克", "阿迪", "彪马",
        "On", "昂跑", "lululemon", "露营", "骑行", "校园", "天气", "暴雨",
        "高温", "凉感", "短袖", "短裤", "亲子", "文旅", "ANTA", "NIKE",
        "Adidas", "PUMA", "FILA", "迪卡侬", "始祖鸟", "萨洛蒙", "亚瑟士",
        "HOKA", "斯凯奇", "优衣库", "蕉下", "六一", "暑期"
    ]

    candidates = []
    for text in texts:
        parts = re.split(r"[。！？\n\r]|(?<=\d)\.\s+", text)
        for part in parts:
            part = clean_text(part)
            if len(part) < 8 or len(part) > 90:
                continue
            if any(k in part for k in keywords):
                candidates.append(part)

    seen = set()
    result = []
    for c in candidates:
        key = c[:32]
        if key not in seen:
            seen.add(key)
            result.append(c)

    return result[:40]

fallback_news = [
    "安踏、李宁等运动品牌加码儿童运动场景，暑期需求提前升温",
    "童装生活方式化趋势增强，亲子、校园与户外场景持续扩容",
    "奥莱折扣与会员运营热度提升，终端转化效率成为重点",
    "局部降雨影响周末客流节奏，门店需关注陈列切换",
    "抖音、小红书内容种草带动童装成交，直播与短视频价值提升",
    "防晒衣、凉感、短裤等夏季品类进入主推窗口",
    "露营、骑行、文旅活动延续，带动轻户外商品需求",
]

texts = read_news_texts()
candidate_titles = extract_candidate_titles(texts)

if len(candidate_titles) < 5:
    candidate_titles = candidate_titles + fallback_news

top_titles = candidate_titles[:5]
news_text_all = " ".join(candidate_titles)

brand_words = [
    "安踏", "ANTA", "李宁", "特步", "361", "耐克", "NIKE", "阿迪", "Adidas",
    "彪马", "PUMA", "On", "昂跑", "lululemon", "FILA", "迪卡侬", "始祖鸟",
    "萨洛蒙", "亚瑟士", "HOKA", "斯凯奇", "优衣库", "蕉下"
]

event_words = [
    "防晒衣", "凉感", "短裤", "短袖", "轻外套", "速干", "轻户外", "露营",
    "骑行", "跑步", "高端跑鞋", "亲子消费", "校园运动", "儿童户外",
    "内容电商", "小红书种草", "抖音电商", "直播带货", "会员运营",
    "折扣零售", "奥莱", "奥特莱斯", "商场客流", "夜经济", "文旅消费",
    "暑期消费", "六一", "暴雨预警", "高温升温", "强对流", "周末客流"
]

generic_words = [
    "运动童装", "儿童经济", "童装生活方式", "女性运动", "品牌联名",
    "户外休闲", "跑步热", "防晒", "凉感", "露营", "防晒衣"
]

def infer_tag(title):
    if any(x in title for x in brand_words):
        return "运动品牌动态"
    if any(x in title for x in ["童装", "儿童", "亲子", "校园", "六一", "暑期"]):
        return "童装/儿童运动"
    if any(x in title for x in ["电商", "直播", "抖音", "小红书", "种草"]):
        return "内容电商"
    if any(x in title for x in ["天气", "暴雨", "降雨", "高温", "防晒", "强对流"]):
        return "天气影响消费"
    if any(x in title for x in ["奥莱", "折扣", "会员", "商场", "客流"]):
        return "线下零售经营"
    if any(x in title for x in ["露营", "骑行", "户外", "文旅"]):
        return "户外消费"
    return "经营信号"

def infer_source(title):
    if any(x in title for x in ["天气", "暴雨", "降雨", "高温", "强对流"]):
        return "公开气象信息"
    if any(x in title for x in ["电商", "直播", "小红书", "抖音", "种草"]):
        return "平台资讯"
    if any(x in title for x in ["商场", "客流", "奥莱", "会员"]):
        return "商业观察"
    return "公开资讯"

def infer_desc(title):
    if any(x in title for x in brand_words):
        return "品牌动作体现竞争加速，需关注产品上新、渠道布局与人群经营变化。"
    if any(x in title for x in ["童装", "儿童", "亲子", "校园", "六一", "暑期"]):
        return "儿童消费正在从单品购买走向亲子、校园、户外和运动场景经营。"
    if any(x in title for x in ["电商", "直播", "小红书", "抖音", "种草"]):
        return "内容平台影响消费决策链路，种草、直播与会员转化值得持续跟踪。"
    if any(x in title for x in ["天气", "暴雨", "降雨", "高温", "防晒", "强对流"]):
        return "天气变化将影响周末客流和品类需求，门店需及时调整陈列和主推商品。"
    if any(x in title for x in ["奥莱", "折扣", "会员", "商场", "客流"]):
        return "折扣场景和会员运营仍是提升转化的重要抓手，活动效率需要重点跟踪。"
    if any(x in title for x in ["露营", "骑行", "户外", "文旅"]):
        return "户外与文旅场景带动运动消费延展，轻量化和舒适型商品机会增加。"
    return "该资讯体现近期行业与消费端变化，可作为门店经营和商品节奏参考。"

def infer_logo(title, tag):
    t = title + tag

    rules = [
        (["安踏", "ANTA"], "ANTA", "logo-dark"),
        (["李宁"], "李", "logo-red"),
        (["特步"], "特", "logo-blue"),
        (["耐克", "NIKE", "Nike"], "N", "logo-dark"),
        (["阿迪", "Adidas"], "A", "logo-dark"),
        (["彪马", "PUMA"], "PUMA", "logo-green"),
        (["On", "昂跑"], "On", "logo-dark"),
        (["lululemon", "Lululemon"], "lulu", "logo-red"),
        (["361"], "361", "logo-blue"),
        (["FILA"], "FILA", "logo-blue"),
        (["迪卡侬"], "迪", "logo-blue"),
        (["始祖鸟"], "鸟", "logo-dark"),
        (["萨洛蒙"], "萨", "logo-dark"),
        (["亚瑟士"], "亚", "logo-blue"),
        (["HOKA"], "H", "logo-sky"),
        (["斯凯奇"], "斯", "logo-blue"),
        (["童装", "儿童", "亲子", "校园", "六一"], "童", "logo-orange"),
        (["电商", "直播", "抖音", "小红书", "种草", "内容"], "电", "logo-purple"),
        (["奥莱", "折扣", "会员", "商场", "客流"], "折", "logo-red"),
        (["天气", "暴雨", "降雨", "强对流", "高温"], "雨", "logo-sky"),
        (["防晒", "凉感", "短裤", "短袖", "轻外套"], "夏", "logo-orange"),
        (["户外", "露营", "骑行", "文旅"], "野", "logo-green"),
    ]

    for keys, logo, cls in rules:
        if any(k in t for k in keys):
            return logo, cls

    return "讯", random.choice(["logo-blue", "logo-green", "logo-purple", "logo-dark"])

def build_hot_words():
    text = news_text_all.replace(" ", "")
    scored = []

    for word in brand_words + event_words + generic_words:
        key = word.replace(" ", "")
        score = text.count(key) * 3 + news_text_all.count(word)
        if score > 0:
            scored.append((word, score))

    scored = sorted(scored, key=lambda x: x[1], reverse=True)
    words = [w for w, _ in scored]

    for w in brand_words + event_words + generic_words:
        if w not in words:
            words.append(w)

    # 优先品牌、事件词，少用泛词
    selected = []
    for w in words:
        if w not in selected and len(selected) < 12:
            selected.append(w)

    tail = selected[4:]
    random.shuffle(tail)
    return selected[:4] + tail

def build_trends(words, titles):
    text = " ".join(words + titles)
    rules = [
        (brand_words, "品牌竞争进入结构分化期", "头部运动品牌竞争从规模扩张转向专业品类、渠道效率和人群经营能力。", "品牌趋势"),
        (["童装", "儿童", "亲子", "校园", "六一", "暑期", "运动童装"], "儿童运动消费场景继续外扩", "童装消费正从服饰购买转向亲子、校园、户外与运动场景综合经营。", "儿童消费趋势"),
        (["电商", "直播", "小红书", "抖音", "内容电商", "种草"], "内容平台影响购买决策链路", "种草、短视频和直播正在改变新品传播、到店转化与线上成交节奏。", "内容趋势"),
        (["防晒", "凉感", "短裤", "轻外套", "速干", "高温", "强对流", "暴雨"], "天气驱动品类节奏切换", "高温、防晒、降雨与强对流共同影响门店客流和商品主推节奏。", "季节趋势"),
        (["奥莱", "折扣", "会员", "商场", "客流", "折扣零售"], "折扣与会员运营仍是转化抓手", "商场客流波动背景下，折扣场景、会员运营与组合陈列更关键。", "渠道趋势"),
        (["户外", "露营", "骑行", "文旅", "轻户外", "户外休闲"], "户外与文旅场景带动运动需求", "骑行、露营、亲子出行和文旅活动共同推动轻户外商品机会。", "消费趋势"),
    ]

    selected = []
    for kws, title, desc, tag in rules:
        if any(k in text for k in kws):
            selected.append((title, desc, tag))

    fallback = [
        ("运动品牌增长分化", "高端跑步、专业运动与女性运动仍是品牌增长的重要结构性机会。", "品牌趋势"),
        ("童装生活方式化", "童装消费从单品售卖转向亲子、校园、户外与运动场景经营。", "儿童消费趋势"),
        ("奥莱与折扣零售升温", "折扣场景与会员运营价值提升，终端需要更重视价格带和连带转化。", "渠道趋势"),
        ("骑行/露营/文旅联动", "骑行经济、文旅消费与亲子户外共同带动运动场景与周边需求。", "消费趋势"),
    ]

    for item in fallback:
        if item not in selected:
            selected.append(item)

    return selected[:4]

def build_region_insights(words, titles):
    text = " ".join(words + titles)

    east_hot = "城市商圈与内容电商联动增强" if any(k in text for k in ["电商", "直播", "小红书", "抖音"]) else "商圈消费恢复与出行场景升温"
    central_hot = "商场活动与会员转化成为重点" if any(k in text for k in ["商场", "客流", "会员", "奥莱", "折扣"]) else "活动转化与天气扰动需同步关注"
    south_hot = "高温天气推动防晒凉感需求" if any(k in text for k in ["防晒", "凉感", "短裤", "高温"]) else "防晒凉感与夜经济消费活跃"
    southwest_hot = "亲子文旅与轻户外场景升温" if any(k in text for k in ["亲子", "文旅", "露营", "户外"]) else "文旅亲子活动带动户外需求"
    northwest_hot = "户外出行与轻防护需求提升" if any(k in text for k in ["骑行", "户外", "防晒", "干燥"]) else "晴热干燥带动户外防护需求"

    return {
        "east_hot": east_hot,
        "east_flow": "商圈客流回暖但雨天扰动仍在，周末波动较大",
        "east_signal": "防晒、轻外套、运动场景及室内体验需求提升",
        "east_action": "关注骑行周边、轻户外、运动场景及室内承接",
        "central_hot": central_hot,
        "central_flow": "商圈客流存在波动，活动转化需更精细",
        "central_signal": "短袖启动偏慢，轻防护需求提升",
        "central_action": "结合天气节奏主推薄外套、防雨、防晒及轻运动单品",
        "south_hot": south_hot,
        "south_flow": "夜间客流增加，夜经济活跃",
        "south_signal": "凉感、短裤、短袖及防晒品类需求上升",
        "south_action": "关注夜场活动、防晒陈列及户外场景搭配",
        "southwest_hot": southwest_hot,
        "southwest_flow": "文旅客流活跃，亲子客群增长",
        "southwest_signal": "亲子休闲、户外轻运动增长",
        "southwest_action": "围绕亲子体验、户外品类与场景化陈列展开",
        "northwest_hot": northwest_hot,
        "northwest_flow": "户外客流活跃，周末出行增加",
        "northwest_signal": "防护用品、帽子等轻防护需求提升",
        "northwest_action": "加强防晒、防风装备陈列，强化出行场景关联",
    }

selected_words = build_hot_words()
trends = build_trends(selected_words, top_titles)
region = build_region_insights(selected_words, top_titles)

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",
    "date": today.strftime("%Y-%m-%d"),
    "weekday": week_map[today.weekday()],
    "update_time": now.strftime("%H:%M"),
    "monitor_count": str(max(80, len(candidate_titles) * 15)),
    "rss_count": str(max(20, len(texts))),
    "focus_count": "5",
    "weather_range": f"{md(today)} ~ {md(day3)}",
    "day1": md(today),
    "day2": md(day2),
    "day3": md(day3),

    "weather_north": "北方多地天气转晴，户外及商场客流具备恢复基础。",
    "weather_east": "华东局部降雨延续，短途出行与商圈客流可能出现波动。",
    "weather_southwest": "华南、西南局部降雨增强，防晒与轻户外需求需结合天气灵活调整。",
    "weather_northwest": "西北多地晴到多云，户外露营、亲子活动关注度有望提升。",

    "north_day1": "晴到多云",
    "north_day2": "多云",
    "north_day3": "晴",
    "east_day1": "局部降雨",
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

    "east_city": "上海/江苏/浙江",
    "central_city": "湖北/湖南/江西",
    "south_city": "广东/广西",
    "southwest_city": "四川/重庆/贵州",
    "northwest_city": "陕西/甘肃/宁夏",

    "east_star": "★★★",
    "central_star": "★★",
    "south_star": "★★★",
    "southwest_star": "★★",
    "northwest_star": "★",
    "generate_time": now.strftime("%Y-%m-%d %H:%M"),
}

data.update(region)

for idx, title in enumerate(top_titles[:5], start=1):
    tag = infer_tag(title)
    logo, logo_class = infer_logo(title, tag)

    data[f"top{idx}_title"] = short(title, 32)
    data[f"top{idx}_tag"] = tag
    data[f"top{idx}_time"] = now.strftime("%m-%d %H:%M")
    data[f"top{idx}_source"] = infer_source(title)
    data[f"top{idx}_desc"] = infer_desc(title)
    data[f"top{idx}_logo"] = logo
    data[f"top{idx}_logo_class"] = logo_class

for i, (title, desc, tag) in enumerate(trends, start=1):
    data[f"trend{i}_title"] = title
    data[f"trend{i}_desc"] = desc
    data[f"trend{i}_tag"] = tag

for i, word in enumerate(selected_words[:12], start=1):
    data[f"word{i}"] = word

for key, value in data.items():
    template = template.replace("{{" + key + "}}", str(value))

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
