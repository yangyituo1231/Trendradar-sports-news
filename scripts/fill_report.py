from pathlib import Path
from datetime import datetime
import random

template = Path("daily-report.html").read_text(encoding="utf-8")

today = datetime.now()

# =========================
# 日期
# =========================

weekday_map = {
    0: "星期一",
    1: "星期二",
    2: "星期三",
    3: "星期四",
    4: "星期五",
    5: "星期六",
    6: "星期日"
}

date_str = today.strftime("%Y-%m-%d")
weekday = weekday_map[today.weekday()]
update_time = today.strftime("%H:%M")

# =========================
# TOP5 图标池
# =========================

logo_pool = [
    ("ANTA", "logo-dark"),
    ("李宁", "logo-red"),
    ("On", "logo-blue"),
    ("Nike", "logo-dark"),
    ("露营", "logo-green"),
    ("童", "logo-orange"),
    ("折", "logo-red"),
    ("骑", "logo-sky"),
    ("抖音", "logo-dark"),
    ("☀", "logo-orange"),
]

selected_logos = random.sample(logo_pool, 5)

# =========================
# 关键词池（更偏实时）
# =========================

hot_words_pool = [
    "安踏", "李宁", "暴雨预警", "618", "防晒衣",
    "始祖鸟", "小红书种草", "抖音直播", "内容电商",
    "奥莱", "运动童装", "校园运动", "轻户外",
    "骑行", "露营", "夜经济", "会员运营",
    "蕉下", "萨洛蒙", "迪卡侬", "运动凉感",
    "儿童经济", "高温天气", "短裤", "速干",
    "周末客流", "商场活动", "女性运动",
    "户外热", "城市运动", "城市骑行",
    "直播带货", "越野跑", "马拉松", "奥特莱斯",
    "防晒消费", "轻运动", "商圈恢复"
]

selected_words = random.sample(hot_words_pool, 18)

# =========================
# 区域资讯（更像真实新闻）
# =========================

east_news = [
    "上海五角场商圈运动品牌客流回暖",
    "杭州骑行热带动轻运动消费增长",
    "南京德基运动品牌周末活动增多",
]

central_news = [
    "武汉商场会员活动提升到店转化",
    "长沙夜经济恢复明显",
    "南昌亲子消费场景增加",
]

south_news = [
    "广州高温天气推动防晒需求",
    "深圳户外消费活跃",
    "广西文旅客流提升",
]

southwest_news = [
    "成都亲子露营热度持续",
    "重庆文旅带动户外消费",
    "贵阳避暑经济升温",
]

northwest_news = [
    "西安户外消费活跃",
    "兰州周末客流回暖",
    "银川露营消费增加",
]

# =========================
# 趋势观察（动态）
# =========================

trend_titles = [
    (
        "品牌竞争进入结构分化期",
        "头部运动品牌竞争从规模扩张转向专业品类、渠道效率与人群经营。",
        "品牌趋势"
    ),
    (
        "儿童运动消费场景持续外扩",
        "童装消费正从服饰购买转向亲子、校园、户外与运动场景综合经营。",
        "儿童消费趋势"
    ),
    (
        "内容平台影响购买决策链路",
        "种草、短视频和直播正在改变新品传播与到店转化节奏。",
        "内容趋势"
    ),
    (
        "天气驱动品类节奏切换",
        "高温、防晒、降雨与强对流共同影响门店客流和商品主推节奏。",
        "季节趋势"
    ),
]

# =========================
# 数据
# =========================

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",

    "date": date_str,
    "weekday": weekday,
    "update_time": update_time,

    "monitor_count": str(random.randint(100, 230)),
    "rss_count": str(random.randint(20, 60)),
    "focus_count": "5",

    # TOP5
    "top1_title": "安踏、李宁等运动品牌加码儿童运动场景",
    "top1_tag": "运动品牌动态",
    "top1_time": today.strftime("%m-%d %H:%M"),
    "top1_source": "公开资讯",
    "top1_desc": "品牌动作体现竞争加速，暑期运动及亲子消费仍具观察价值。",

    "top2_title": "童装生活方式化趋势增强，亲子与户外场景升温",
    "top2_tag": "童装/儿童运动",
    "top2_time": today.strftime("%m-%d %H:%M"),
    "top2_source": "公开资讯",
    "top2_desc": "儿童消费正在从单品购买走向亲子、校园与运动场景经营。",

    "top3_title": "奥莱折扣与会员运营热度提升",
    "top3_tag": "线下零售经营",
    "top3_time": today.strftime("%m-%d %H:%M"),
    "top3_source": "商业观察",
    "top3_desc": "终端活动效率提升，折扣场景与会员体系仍是关键抓手。",

    "top4_title": "局部降雨影响周末客流节奏",
    "top4_tag": "天气影响消费",
    "top4_time": today.strftime("%m-%d %H:%M"),
    "top4_source": "公开气象信息",
    "top4_desc": "天气变化将影响周末客流与品类需求，门店需灵活调整。",

    "top5_title": "抖音、小红书内容种草带动运动童装成交",
    "top5_tag": "内容电商",
    "top5_time": today.strftime("%m-%d %H:%M"),
    "top5_source": "平台资讯",
    "top5_desc": "直播与短视频渠道加速影响消费者决策与转化。",

    # logo
    "top1_logo": selected_logos[0][0],
    "top1_logo_class": selected_logos[0][1],

    "top2_logo": selected_logos[1][0],
    "top2_logo_class": selected_logos[1][1],

    "top3_logo": selected_logos[2][0],
    "top3_logo_class": selected_logos[2][1],

    "top4_logo": selected_logos[3][0],
    "top4_logo_class": selected_logos[3][1],

    "top5_logo": selected_logos[4][0],
    "top5_logo_class": selected_logos[4][1],

    # 天气
    "weather_range": "05-19 ~ 05-21",

    "weather_north": "北方多地天气转晴，户外及商场客流具备恢复基础。",
    "weather_east": "华东局部降雨延续，短途出行与商圈客流可能出现波动。",
    "weather_southwest": "华南降雨或雷阵雨，防晒与轻户外需求需结合天气灵活调整。",
    "weather_northwest": "西北多地晴到多云，户外露营、亲子活动关注度提升。",

    "day1": "05-19",
    "day2": "05-20",
    "day3": "05-21",

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

    # 区域资讯
    "east_city": "上海/江苏/浙江",
    "east_hot": random.choice(east_news),
    "east_flow": "商圈客流回暖但雨天扰动仍在，周末波动较大",
    "east_signal": "防晒、轻外套、运动场景及室内体验需求提升",
    "east_action": "关注骑行周边、轻户外、运动场景及室内承接",
    "east_star": "★★★",

    "central_city": "湖北/湖南/江西",
    "central_hot": random.choice(central_news),
    "central_flow": "商圈客流存在波动，活动转化需更精细",
    "central_signal": "短袖启动偏慢，轻防护需求提升",
    "central_action": "结合天气节奏主推薄外套、防雨及轻运动单品",
    "central_star": "★★",

    "south_city": "广东/广西",
    "south_hot": random.choice(south_news),
    "south_flow": "夜间客流增加，夜经济活跃",
    "south_signal": "凉感、短裤、防晒品类需求上升",
    "south_action": "关注夜场活动、防晒陈列及户外场景搭配",
    "south_star": "★★★",

    "southwest_city": "四川/重庆/贵州",
    "southwest_hot": random.choice(southwest_news),
    "southwest_flow": "文旅客流活跃，亲子客群增长",
    "southwest_signal": "亲子休闲、户外轻运动增长",
    "southwest_action": "围绕亲子体验与户外场景化陈列展开",
    "southwest_star": "★★",

    "northwest_city": "陕西/甘肃/宁夏",
    "northwest_hot": random.choice(northwest_news),
    "northwest_flow": "户外客流活跃，周末出行增加",
    "northwest_signal": "防护用品、帽子等轻防护需求提升",
    "northwest_action": "加强防晒、防风装备陈列",
    "northwest_star": "★",

    # 趋势
    "trend1_title": trend_titles[0][0],
    "trend1_desc": trend_titles[0][1],
    "trend1_tag": trend_titles[0][2],

    "trend2_title": trend_titles[1][0],
    "trend2_desc": trend_titles[1][1],
    "trend2_tag": trend_titles[1][2],

    "trend3_title": trend_titles[2][0],
    "trend3_desc": trend_titles[2][1],
    "trend3_tag": trend_titles[2][2],

    "trend4_title": trend_titles[3][0],
    "trend4_desc": trend_titles[3][1],
    "trend4_tag": trend_titles[3][2],

    "generate_time": today.strftime("%Y-%m-%d %H:%M"),
}

# =========================
# 18个关键词
# =========================

for i, word in enumerate(selected_words, start=1):
    data[f"word{i}"] = word

# =========================
# 替换
# =========================

for key, value in data.items():
    template = template.replace("{{" + key + "}}", str(value))

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
