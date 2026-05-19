from pathlib import Path
from datetime import datetime, timedelta
import random

template = Path("daily-report.html").read_text(encoding="utf-8")

now = datetime.now()
today = now
day2 = today + timedelta(days=1)
day3 = today + timedelta(days=2)

weekday_map = {
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

# =========================
# 一、TOP5资讯池
# =========================

top_news_pool = [
    {
        "title": "618预售升温，运动品牌加大儿童与夏季品类投放",
        "tag": "大促/电商",
        "source": "平台资讯",
        "desc": "618节奏提前带动防晒、凉感、短裤、童装等夏季品类关注提升。",
        "logo": "618",
        "icon": "🛒",
        "class": "logo-blue",
    },
    {
        "title": "高温天气持续，防晒衣与凉感科技进入主推窗口",
        "tag": "天气影响消费",
        "source": "公开气象信息",
        "desc": "高温与强对流并行，门店需关注防晒、凉感、速干及轻外套陈列。",
        "logo": "高温",
        "icon": "☀️",
        "class": "logo-sky",
    },
    {
        "title": "抖音直播与小红书种草继续影响运动童装成交",
        "tag": "内容电商",
        "source": "平台资讯",
        "desc": "短视频、直播与种草内容正在改变新品传播、到店转化和线上成交节奏。",
        "logo": "内容",
        "icon": "🎵",
        "class": "logo-dark",
    },
    {
        "title": "城市骑行、露营与夜经济延续，轻户外需求释放",
        "tag": "户外消费",
        "source": "消费观察",
        "desc": "文旅、骑行、露营和夜间消费共同带动轻户外与运动生活方式需求。",
        "logo": "户外",
        "icon": "🚴",
        "class": "logo-green",
    },
    {
        "title": "奥莱折扣与会员运营升温，终端转化效率成重点",
        "tag": "线下零售经营",
        "source": "商业观察",
        "desc": "折扣场景、会员权益和组合陈列仍是提升终端销售效率的关键抓手。",
        "logo": "折扣",
        "icon": "%",
        "class": "logo-blue",
    },
    {
        "title": "亲子文旅与周末出行升温，儿童运动场景继续外扩",
        "tag": "儿童消费趋势",
        "source": "消费观察",
        "desc": "亲子出行、校园运动、户外体验共同推动儿童运动消费场景延伸。",
        "logo": "亲子",
        "icon": "🧒",
        "class": "logo-sky",
    },
    {
        "title": "商场活动与本地生活平台联动，周末客流修复提速",
        "tag": "商圈客流",
        "source": "商业观察",
        "desc": "商圈活动、会员权益和本地生活平台联动成为周末转化的重要抓手。",
        "logo": "商圈",
        "icon": "🏬",
        "class": "logo-dark",
    },
]

top_news = random.sample(top_news_pool, 5)

# =========================
# 二、关键词池
# =========================

priority_words_pool = [
    "618",
    "暴雨预警",
    "高温天气",
    "防晒衣",
    "抖音直播",
    "小红书种草",
    "文旅客流",
    "周末客流",
    "城市骑行",
    "商圈活动",
]

hot_words_pool = [
    "618", "高温天气", "暴雨预警", "强对流", "防晒衣", "凉感科技",
    "抖音直播", "小红书种草", "内容电商", "直播带货", "本地生活",
    "周末客流", "商场活动", "会员运营", "奥莱折扣", "夜经济",
    "文旅客流", "城市骑行", "露营经济", "亲子出行", "暑期消费",
    "校园运动", "儿童经济", "运动童装", "安踏", "李宁", "特步",
    "始祖鸟", "萨洛蒙", "蕉下", "迪卡侬", "lululemon", "On昂跑",
    "防晒消费", "轻户外", "短裤", "速干", "马拉松", "城市运动",
    "门店陈列", "商圈恢复", "折扣零售", "消费复苏", "天气扰动",
    "大促预售", "防雨装备", "户外休闲", "亲子运动", "夏季新品",
]

priority_words = random.sample(priority_words_pool, 3)
remaining_words = [w for w in hot_words_pool if w not in priority_words]
selected_words = priority_words + random.sample(remaining_words, 15)

# =========================
# 三、区域热点池
# =========================

east_news = [
    "上海核心商圈周末客流回暖，运动品牌活动密集",
    "杭州城市骑行热度升温，轻运动装备关注提升",
    "南京购物中心亲子运动活动增多",
    "苏州奥莱折扣活动带动家庭客群到店",
    "宁波商圈亲子活动增加，儿童运动品类关注提升",
]

central_news = [
    "武汉商场会员日活动提升到店转化",
    "长沙夜经济恢复明显，运动休闲消费活跃",
    "南昌亲子消费场景增加，儿童品类关注提升",
    "武汉高校周边运动消费热度提升",
    "郑州商圈活动升温，周末家庭客群回流",
]

south_news = [
    "广州高温天气推动防晒与凉感需求",
    "深圳户外运动消费活跃，轻户外品类升温",
    "佛山商圈周末活动带动家庭客流",
    "南宁文旅客流提升，亲子出行需求释放",
    "厦门滨海出行热度上升，轻户外用品关注提升",
]

southwest_news = [
    "成都亲子露营热度持续，轻户外需求增加",
    "重庆文旅带动户外消费，夜间客流活跃",
    "贵阳避暑经济升温，凉感防晒品类受关注",
    "成都购物中心儿童运动体验活动增加",
    "昆明周末出游升温，亲子休闲消费修复",
]

northwest_news = [
    "西安户外消费活跃，周末出行热度提升",
    "兰州周末客流回暖，轻防护用品关注提升",
    "银川露营消费增加，亲子户外活动升温",
    "西安商圈活动带动运动休闲消费",
    "乌鲁木齐户外出行增加，防晒与轻运动需求提升",
]

# =========================
# 四、趋势观察池
# =========================

trend_pool = [
    (
        "大促节点前置，夏季品类进入放量窗口",
        "618节奏提前带动防晒、凉感、速干、童装等品类集中曝光。",
        "大促趋势",
    ),
    (
        "内容平台影响购买决策链路",
        "种草、短视频和直播正在改变新品传播、到店转化与线上成交节奏。",
        "内容趋势",
    ),
    (
        "儿童运动消费场景持续外扩",
        "童装消费正从服饰购买转向亲子、校园、户外与运动场景综合经营。",
        "儿童消费趋势",
    ),
    (
        "天气驱动品类节奏切换",
        "高温、防晒、降雨与强对流共同影响门店客流和商品主推节奏。",
        "季节趋势",
    ),
    (
        "区域商圈活动价值提升",
        "周末客流、会员运营、商圈活动与本地生活平台联动成为转化关键。",
        "渠道趋势",
    ),
    (
        "户外与文旅场景带动运动需求",
        "骑行、露营、亲子出行和文旅活动共同推动轻户外商品机会。",
        "消费趋势",
    ),
]

trends = random.sample(trend_pool, 4)

# =========================
# 五、基础数据
# =========================

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",

    "date": today.strftime("%Y-%m-%d"),
    "weekday": weekday_map[today.weekday()],
    "update_time": today.strftime("%H:%M"),

    "monitor_count": str(random.randint(150, 260)),
    "rss_count": str(random.randint(35, 75)),
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

    "generate_time": today.strftime("%Y-%m-%d %H:%M"),
}

# =========================
# 六、填入TOP5
# =========================

for i, item in enumerate(top_news, start=1):
    data[f"top{i}_title"] = item["title"]
    data[f"top{i}_tag"] = item["tag"]
    data[f"top{i}_time"] = today.strftime("%m-%d %H:%M")
    data[f"top{i}_source"] = item["source"]
    data[f"top{i}_desc"] = item["desc"]
    data[f"top{i}_logo"] = item["logo"]
    data[f"top{i}_icon"] = item["icon"]
    data[f"top{i}_logo_class"] = item["class"]

# =========================
# 七、填入趋势
# =========================

for i, item in enumerate(trends, start=1):
    data[f"trend{i}_title"] = item[0]
    data[f"trend{i}_desc"] = item[1]
    data[f"trend{i}_tag"] = item[2]

# =========================
# 八、填入关键词
# =========================

for i, word in enumerate(selected_words, start=1):
    data[f"word{i}"] = word

# =========================
# 九、模板替换
# =========================

for key, value in data.items():
    template = template.replace("{{" + key + "}}", str(value))

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
