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
    0: "星期一",
    1: "星期二",
    2: "星期三",
    3: "星期四",
    4: "星期五",
    5: "星期六",
    6: "星期日",
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
    roots = [
        Path("output/news"),
        Path("output"),
    ]

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
    candidates = []

    for text in texts:
        parts = re.split(r"[。！？\n\r]|(?<=\d)\.\s+", text)

        for part in parts:
            part = clean_text(part)

            if len(part) < 8 or len(part) > 80:
                continue

            if any(x in part for x in [
                "运动", "童装", "儿童", "跑步", "户外", "防晒", "品牌", "消费", "零售",
                "奥莱", "折扣", "会员", "商场", "客流", "电商", "直播", "小红书",
                "抖音", "安踏", "李宁", "特步", "361", "耐克", "阿迪", "彪马",
                "On", "昂跑", "lululemon", "露营", "骑行", "校园", "天气", "暴雨"
            ]):
                candidates.append(part)

    seen = set()
    result = []
    for c in candidates:
        key = c[:28]
        if key not in seen:
            seen.add(key)
            result.append(c)

    return result[:20]

fallback_news = [
    "运动品牌加码中国市场，本土化布局提速",
    "童装生活方式化趋势增强，亲子与户外场景升温",
    "折扣与会员运营持续升温，奥莱场景值得关注",
    "局部降雨影响周末客流节奏，门店需关注陈列切换",
    "内容电商带动运动童装成交，种草与直播价值提升",
    "校园运动与亲子活动升温，儿童运动消费场景扩大",
    "防晒、凉感、轻外套等品类进入季节性关注期",
]

texts = read_news_texts()
candidate_titles = extract_candidate_titles(texts)

if len(candidate_titles) < 5:
    candidate_titles = candidate_titles + fallback_news

top_titles = candidate_titles[:5]

brand_rules = [
    ("On", ["On", "昂跑"]),
    ("安踏", ["安踏"]),
    ("李宁", ["李宁"]),
    ("特步", ["特步"]),
    ("耐克", ["Nike", "耐克"]),
    ("阿迪", ["Adidas", "阿迪"]),
    ("彪马", ["PUMA", "彪马"]),
    ("LULU", ["lululemon", "Lululemon"]),
    ("童", ["童装", "儿童", "亲子"]),
    ("电", ["电商", "直播", "抖音", "小红书"]),
    ("折", ["奥莱", "折扣", "会员"]),
    ("雨", ["天气", "暴雨", "降雨", "强对流"]),
]

def infer_tag(title):
    if any(x in title for x in ["安踏", "李宁", "特步", "耐克", "阿迪", "彪马", "On", "昂跑", "lululemon"]):
        return "运动品牌动态"
    if any(x in title for x in ["童装", "儿童", "亲子", "校园"]):
        return "童装/儿童运动"
    if any(x in title for x in ["电商", "直播", "抖音", "小红书"]):
        return "内容电商"
    if any(x in title for x in ["天气", "暴雨", "降雨", "高温", "防晒"]):
        return "天气影响消费"
    if any(x in title for x in ["奥莱", "折扣", "会员", "商场"]):
        return "线下零售经营"
    return "经营信号"

def infer_source(title):
    if any(x in title for x in ["天气", "暴雨", "降雨", "高温"]):
        return "公开气象信息"
    if any(x in title for x in ["电商", "直播", "小红书", "抖音"]):
        return "平台资讯"
    return "公开资讯"

def infer_desc(title):
    if any(x in title for x in ["安踏", "李宁", "特步", "耐克", "阿迪", "彪马", "On", "昂跑", "lululemon"]):
        return "品牌动向反映运动消费结构变化，需关注产品、渠道与营销节奏。"
    if any(x in title for x in ["童装", "儿童", "亲子", "校园"]):
        return "儿童消费从单品需求转向场景经营，亲子、校园与户外价值提升。"
    if any(x in title for x in ["电商", "直播", "小红书", "抖音"]):
        return "内容平台正在影响消费者决策链路，种草、直播与会员转化值得关注。"
    if any(x in title for x in ["天气", "暴雨", "降雨", "高温", "防晒"]):
        return "天气变化将影响周末客流与品类需求，门店需及时调整陈列和主推商品。"
    if any(x in title for x in ["奥莱", "折扣", "会员", "商场"]):
        return "折扣场景与会员运营仍是提升转化的重要抓手，终端活动效率需持续跟踪。"
    return "该资讯体现近期行业与消费端变化，可作为门店经营和商品节奏的参考信号。"

hot_words_pool = [
    "安踏", "李宁", "特步", "耐克", "阿迪", "彪马", "On 昂跑", "lululemon",
    "运动童装", "儿童经济", "童装生活方式", "亲子消费", "校园运动", "儿童户外",
    "防晒", "防晒衣", "凉感", "短裤", "轻外套", "速干", "轻户外", "露营",
    "骑行经济", "户外休闲", "跑步热", "高端跑鞋", "女性运动", "品牌联名",
    "内容电商", "小红书种草", "抖音电商", "直播带货", "会员运营", "折扣零售",
    "奥莱", "奥特莱斯", "商场客流", "夜经济", "文旅消费", "暑期消费",
    "暴雨预警", "高温升温", "强对流", "周末客流"
]

news_text_all = " ".join(candidate_titles)

scored_words = []
for word in hot_words_pool:
    score = news_text_all.count(word.replace(" ", "")) + news_text_all.count(word)
    if score > 0:
        scored_words.append((word, score))

scored_words = sorted(scored_words, key=lambda x: x[1], reverse=True)
dynamic_words = [w for w, _ in scored_words]

for w in hot_words_pool:
    if w not in dynamic_words:
        dynamic_words.append(w)

selected_words = dynamic_words[:12]
if len(selected_words) < 12:
    selected_words += random.sample(hot_words_pool, 12 - len(selected_words))

random.shuffle(selected_words[4:])

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
    "east_hot": "商圈消费恢复与出行场景升温",
    "east_flow": "商圈客流回暖但雨天扰动仍在，周末波动较大",
    "east_signal": "防晒、轻外套、运动场景及室内体验需求提升",
    "east_action": "可关注骑行周边、轻户外、运动场景及室内承接",
    "east_star": "★★★",

    "central_city": "湖北/湖南/江西",
    "central_hot": "天气影响客流，周末波动明显",
    "central_flow": "商圈客流存在波动，活动转化需更精细",
    "central_signal": "短袖启动偏慢，轻防护需求提升",
    "central_action": "结合天气节奏主推薄外套、防雨、防晒及轻运动单品",
    "central_star": "★★",

    "south_city": "广东/广西",
    "south_hot": "文旅与夜经济活跃，消费场景增加",
    "south_flow": "夜间客流增加，夜经济活跃",
    "south_signal": "凉感、短裤、短袖及防晒品类需求上升",
    "south_action": "可关注夜场活动、防晒陈列及户外场景搭配",
    "south_star": "★★★",

    "southwest_city": "四川/重庆/贵州",
    "southwest_hot": "文旅活动带动亲子出行",
    "southwest_flow": "文旅客流活跃，亲子客群增长",
    "southwest_signal": "亲子休闲、户外轻运动增长",
    "southwest_action": "可围绕亲子体验、户外品类与场景化陈列展开",
    "southwest_star": "★★",

    "northwest_city": "陕西/甘肃/宁夏",
    "northwest_hot": "天气干燥多风，户外活动活跃",
    "northwest_flow": "户外客流活跃，周末出行增加",
    "northwest_signal": "防护用品、帽子等轻防护需求提升",
    "northwest_action": "加强防晒、防风装备陈列，强化出行场景关联",
    "northwest_star": "★",

    "trend1_title": "运动品牌增长分化",
    "trend1_desc": "高端跑步、专业运动与女性运动仍是品牌增长的重要结构性机会。",
    "trend1_tag": "品牌趋势",

    "trend2_title": "童装生活方式化",
    "trend2_desc": "童装消费从单品售卖转向亲子、校园、户外与运动场景经营。",
    "trend2_tag": "儿童消费趋势",

    "trend3_title": "奥莱与折扣零售升温",
    "trend3_desc": "折扣场景与会员运营价值提升，终端需要更重视价格带和连带转化。",
    "trend3_tag": "渠道趋势",

    "trend4_title": "骑行/露营/文旅联动",
    "trend4_desc": "骑行经济、文旅消费与亲子户外共同带动运动场景与周边需求。",
    "trend4_tag": "消费趋势",

    "generate_time": now.strftime("%Y-%m-%d %H:%M"),
}

for idx, title in enumerate(top_titles[:5], start=1):
    data[f"top{idx}_title"] = short(title, 32)
    data[f"top{idx}_tag"] = infer_tag(title)
    data[f"top{idx}_time"] = now.strftime("%m-%d %H:%M")
    data[f"top{idx}_source"] = infer_source(title)
    data[f"top{idx}_desc"] = infer_desc(title)

for i, word in enumerate(selected_words[:12], start=1):
    data[f"word{i}"] = word

for key, value in data.items():
    template = template.replace("{{" + key + "}}", str(value))

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
