import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

MAX_ITEMS = 100
OUT_DIR = Path("output/news")
OUT_FILE = OUT_DIR / "latest.json"

NOW = datetime.now()
MONTH = NOW.month


def current_campaign():
    if MONTH == 1:
        return "元旦年货"
    if MONTH == 2:
        return "春节开春"
    if MONTH == 3:
        return "38大促春季上新"
    if MONTH == 4:
        return "清明春游"
    if MONTH == 5:
        return "五一六一618预热"
    if MONTH == 6:
        return "六一618端午"
    if MONTH in [7, 8]:
        return "暑期消费"
    if MONTH == 9:
        return "开学季99大促"
    if MONTH == 10:
        return "国庆双11预热"
    if MONTH == 11:
        return "双11"
    if MONTH == 12:
        return "双12年货预热"
    return "日常经营"


CAMPAIGN = current_campaign()

CAMPAIGN_GROUPS = {
    "元旦年货": ["元旦", "年货", "春节", "冬季", "保暖", "防滑", "羽绒", "棉服"],
    "春节开春": ["春节", "开春", "春季上新", "轻外套", "亲子", "童装"],
    "38大促春季上新": ["38大促", "三八", "女神节", "春季上新", "春装", "轻外套"],
    "清明春游": ["清明", "春游", "踏青", "轻户外", "亲子出行", "露营"],
    "五一六一618预热": ["五一", "劳动节", "六一", "儿童节", "618", "预售", "防晒", "凉感"],
    "六一618端午": ["六一", "儿童节", "618", "端午", "防晒", "凉感", "速干"],
    "暑期消费": ["暑期", "夏季", "防晒", "凉感", "速干", "亲子户外"],
    "开学季99大促": ["开学季", "99大促", "秋季上新", "校园", "儿童运动"],
    "国庆双11预热": ["国庆", "中秋", "双11预热", "秋冬", "轻外套", "出行"],
    "双11": ["双11", "双十一", "秋冬", "保暖", "防滑", "棉服"],
    "双12年货预热": ["双12", "年货", "冬季", "保暖", "防滑", "羽绒"],
    "日常经营": ["运动童装", "运动品牌", "商场客流", "轻户外", "小红书"],
}

CAMPAIGN_KEYWORDS = {
    "五一六一618预热": [
        "五一 运动品牌 消费",
        "五一 亲子户外 运动",
        "六一 儿童运动 童装",
        "儿童节 运动童装",
        "618 运动品牌 防晒 凉感",
        "618 童装 运动品牌",
    ],
    "六一618端午": [
        "六一 儿童运动 童装",
        "儿童节 运动童装",
        "端午 亲子户外 运动",
        "618 运动品牌 防晒 凉感",
        "618 童装 运动品牌",
        "618 抖音电商 运动品牌",
        "天猫 运动童装 618",
        "京东 运动品牌 618",
        "唯品会 运动童装 618",
    ],
    "暑期消费": [
        "暑期消费 儿童运动",
        "暑期 童装 防晒 凉感",
        "夏季 运动品牌 防晒 速干",
        "亲子户外 暑期 运动",
    ],
    "开学季99大促": [
        "开学季 运动童装",
        "校园体育 儿童运动",
        "儿童运动鞋 开学季",
        "秋季 童装 运动品牌",
        "99大促 运动品牌",
        "99大促 童装",
    ],
    "国庆双11预热": [
        "国庆 运动品牌 消费",
        "国庆 亲子户外 运动",
        "中秋 运动品牌 消费",
        "双11预热 运动品牌",
        "秋冬 童装 运动品牌",
    ],
    "双11": [
        "双11 运动品牌 童装",
        "双十一 运动品牌 防滑 保暖",
        "双11 抖音电商 运动品牌",
        "双11 小红书 童装",
        "天猫 运动品牌 双11",
        "京东 运动品牌 双11",
    ],
}

DEFAULT_CAMPAIGN_KEYWORDS = [
    "运动童装 儿童运动 消费",
    "运动品牌 消费 零售",
    "商场 客流 运动品牌",
    "小红书 种草 运动品牌",
]

REGION_CITY_MAP = {
    "华东": ["上海", "南京", "苏州", "杭州", "宁波", "无锡", "合肥"],
    "华中": ["武汉", "长沙", "南昌", "郑州"],
    "华南": ["广州", "深圳", "佛山", "东莞", "南宁", "厦门", "福州"],
    "西南": ["成都", "重庆", "贵阳", "昆明"],
    "西北": ["西安", "兰州", "银川", "乌鲁木齐"],
}

CITY_TO_REGION = {}
for region, cities in REGION_CITY_MAP.items():
    for city in cities:
        CITY_TO_REGION[city] = region


BASE_KEYWORDS = [
    "运动童装 儿童运动 消费",
    "童装 亲子 户外 运动",
    "儿童运动 校园 体育 消费",
    "亲子运动 童装 户外",
    "校园体育 运动童装",

    "防晒衣 凉感 速干 运动",
    "高温 防晒衣 凉感 消费",
    "暴雨 天气 商场 客流",
    "夏季 运动品牌 防晒 凉感",
    "防晒 消费 运动品牌",
    "速干 短裤 运动童装",
    "低温 保暖 防滑 童装",
    "降雪 防滑 运动鞋",

    "抖音电商 运动品牌",
    "抖音直播 童装 运动",
    "小红书 种草 运动品牌",
    "小红书 童装 防晒",
    "天猫 运动品牌 童装",
    "京东 运动品牌 童装",
    "唯品会 运动童装",

    "商场 客流 消费 运动品牌",
    "购物中心 儿童运动 亲子",
    "奥莱 折扣 运动品牌",
    "门店 客流 会员 运动品牌",
    "商圈 活动 亲子 运动",
    "本地生活 商场 客流 消费",

    "户外 露营 骑行 亲子消费",
    "城市骑行 运动消费",
    "露营 亲子 户外 消费",
    "夜经济 运动消费",
    "城市徒步 轻户外 消费",

    "Nike 儿童 运动",
    "耐克 儿童 运动",
    "Nike Kids 童装",
    "Adidas 儿童 运动",
    "阿迪达斯 儿童 运动",
    "Adidas Kids 童装",
    "ASICS 亚瑟士 跑步 消费",
    "亚瑟士 跑步 消费",
    "On昂跑 中国消费",
    "On 昂跑 跑步 消费",
    "HOKA 跑步 消费",
    "lululemon 中国消费",
    "Puma 彪马 运动消费",
    "New Balance 新百伦 运动消费",

    "安踏 儿童 运动",
    "安踏儿童 童装",
    "FILA KIDS 儿童",
    "李宁YOUNG 儿童",
    "李宁 童装 儿童",
    "特步儿童 运动",
    "特步 运动 消费",
    "361度 儿童 运动",
    "361儿童 运动",

    "巴拉巴拉 运动童装",
    "Balabala 运动童装",
    "安奈儿 童装 消费",

    "始祖鸟 户外 消费",
    "萨洛蒙 户外 运动",
    "北面 户外 消费",
    "哥伦比亚 户外 消费",
    "凯乐石 户外 消费",
    "探路者 户外 消费",
    "骆驼 户外 消费",

    "蕉下 防晒 消费",
    "蕉内 运动 消费",
    "伯希和 户外 消费",
]

LOCAL_NEWS_QUERIES = [
    "上海 商圈 客流 购物中心 亲子",
    "上海 商场 会员 消费 运动",
    "南京 购物中心 亲子 活动",
    "苏州 奥莱 商场 客流",
    "杭州 商场 客流 亲子 消费",
    "宁波 商圈 消费 亲子",
    "无锡 商场 客流 儿童",
    "合肥 商圈 消费 亲子",

    "武汉 商圈 客流 亲子",
    "武汉 购物中心 儿童 活动",
    "长沙 商场 亲子 消费",
    "南昌 购物中心 儿童 活动",
    "郑州 商圈 客流 消费",

    "广州 商圈 文旅 亲子",
    "广州 购物中心 客流 消费",
    "深圳 商场 客流 户外",
    "佛山 商圈 亲子 消费",
    "东莞 商场 客流 儿童",
    "厦门 文旅 亲子 户外",
    "福州 商圈 消费 亲子",
    "南宁 商场 客流 童装",

    "成都 商圈 客流 亲子",
    "成都 文旅 户外 消费",
    "重庆 文旅 商场 消费",
    "贵阳 商圈 消费 亲子",
    "昆明 文旅 户外 亲子",

    "西安 商圈 文旅 亲子",
    "西安 购物中心 客流",
    "兰州 商场 客流 消费",
    "银川 商场 客流 亲子",
    "乌鲁木齐 商圈 消费 户外",
]

CITY_WEATHER_ABNORMAL_QUERIES = [
    "上海 高温 防晒 消费 商场",
    "杭州 高温 防晒 凉感 童装",
    "南京 高温 防晒 商场 客流",
    "广州 高温 防晒 凉感 消费",
    "深圳 高温 防晒 户外 消费",
    "厦门 高温 防晒 亲子 户外",
    "福州 高温 防晒 消费",
    "南宁 高温 防晒 凉感",

    "武汉 暴雨 商场 客流 亲子",
    "长沙 暴雨 商场 客流",
    "南昌 暴雨 购物中心 客流",
    "郑州 强对流 商场 客流",
    "成都 暴雨 商圈 客流",
    "重庆 暴雨 文旅 商场",
    "贵阳 降雨 商场 客流",
    "昆明 降雨 户外 文旅",

    "西安 高温 防晒 商场 客流",
    "兰州 高温 防晒 防风 消费",
    "银川 大风 防晒 户外 消费",
    "乌鲁木齐 大风 防晒 户外 消费",

    "城市 高温 商场 客流 防晒",
    "暴雨 强对流 商场 客流 消费",
    "大风 防晒 户外 消费",
    "降雨 购物中心 客流 亲子",
]

AI_AND_TREND_KEYWORDS = [
    "AI 消费 零售",
    "AI 运动品牌",
    "人工智能 消费",
    "人工智能 零售",
    "AI 商场 零售",
    "AI 内容种草",
    "AI 电商",
    "AI 智能硬件 消费",
    "智能机器人 消费",
    "科技消费 年轻人",
    "运动科技 功能面料",
    "智能穿戴 儿童",
    "智能运动 消费",

    "年轻人 消费趋势",
    "00后 消费",
    "情绪消费",
    "悦己消费",
    "松弛感 消费",
    "治愈消费",
    "社交消费",
    "运动社交",
    "运动最解压",
    "女性消费",
    "她经济",
    "国潮消费",

    "城市骑行 消费",
    "城市徒步 消费",
    "夜经济 消费",
    "文旅 客流 商圈",
    "演唱会 商圈 客流",
    "赛事 商圈 客流",
    "暑期消费 文旅",
    "亲子出行 消费",
    "城市运动 消费",

    "GDP 社零 消费",
    "社零 消费趋势",
    "就业 收入 消费",
    "消费信心 零售",
    "促消费 政策 零售",
    "下沉市场 消费",
    "银发经济 消费",
    "消费分层 零售",
    "理性消费",
    "性价比消费",

    "店播增长",
    "内容种草",
    "会员复购",
    "直播带货",
    "达人矩阵",
    "本地生活 零售",
    "即时零售 运动品牌",
]

KEYWORDS = (
    CAMPAIGN_KEYWORDS.get(CAMPAIGN, DEFAULT_CAMPAIGN_KEYWORDS)
    + BASE_KEYWORDS
    + LOCAL_NEWS_QUERIES
    + CITY_WEATHER_ABNORMAL_QUERIES
    + AI_AND_TREND_KEYWORDS
)

KEYWORDS = list(dict.fromkeys(KEYWORDS))


NEGATIVE_KEYWORDS = [
    "中超", "英超", "欧冠", "NBA", "CBA", "世界杯", "世锦赛",
    "冠军", "夺冠", "决赛", "半决赛", "比分", "赛程", "联赛",
    "主教练", "球员", "转会", "足球", "篮球", "乒乓球", "羽毛球",
    "网球", "拳击", "格斗", "赛车", "马拉松成绩", "破纪录",
    "体育总局", "奥运会", "全运会", "国家队", "运动员",
    "央行", "利率", "财政", "货币政策", "地产", "楼市",
    "基金", "证券", "港股", "A股", "美股", "融资",
    "并购", "IPO", "财报电话会",
    "彩票", "电竞比赛", "游戏赛事", "博彩",
]

SOFT_NEGATIVE_KEYWORDS = [
    "股价", "财报", "营收", "净利润", "股东", "市值", "评级", "研报",
    "管理层", "董事会", "资本市场",
]

WEATHER_ABNORMAL_WORDS = [
    "高温", "暴雨", "强对流", "雷暴", "大风", "降雨", "降温", "升温",
    "冰雹", "台风", "寒潮", "低温", "降雪", "结冰", "沙尘", "防晒",
    "防风", "防雨", "防滑", "凉感", "速干",
]

LOCAL_BUSINESS_WORDS = [
    "商场", "商圈", "购物中心", "客流", "门店", "奥莱", "会员",
    "亲子", "儿童", "童装", "文旅", "旅游", "暑期", "夜经济",
    "户外", "骑行", "露营", "消费", "活动",
]


BRAND_WORDS = {
    "Nike": 7, "耐克": 7, "Nike Kids": 8,
    "Adidas": 7, "阿迪达斯": 7, "Adidas Kids": 8,
    "Puma": 6, "彪马": 6,
    "New Balance": 6, "新百伦": 6,
    "ASICS": 7, "亚瑟士": 7,
    "On": 5, "On昂跑": 8, "昂跑": 8,
    "HOKA": 8,
    "Salomon": 6, "萨洛蒙": 6,
    "lululemon": 6,

    "安踏": 7, "安踏儿童": 9,
    "FILA": 6, "FILA KIDS": 8,
    "李宁": 7, "李宁YOUNG": 8,
    "特步": 7, "特步儿童": 8,
    "361": 7, "361度": 7, "361儿童": 9,

    "巴拉巴拉": 7, "Balabala": 7,
    "始祖鸟": 7, "北面": 6, "哥伦比亚": 5,
    "凯乐石": 5, "探路者": 5, "骆驼": 5,
    "蕉下": 6, "蕉内": 5, "伯希和": 5,
}

HOT_WORDS = {
    "运动童装": 10, "童装": 8, "儿童运动": 10, "儿童": 6,
    "亲子": 7, "校园": 6, "校园体育": 8, "暑期": 5, "开学": 5,
    "防晒衣": 9, "防晒": 7, "凉感": 7, "速干": 6, "短裤": 5,
    "运动凉鞋": 5, "轻外套": 5, "功能面料": 6,
    "保暖": 6, "防滑": 6, "羽绒": 5, "棉服": 5,
    "高温": 7, "暴雨": 7, "强对流": 7, "降雨": 6, "天气": 4,
    "低温": 5, "降雪": 5, "结冰": 5, "大风": 5, "沙尘": 5,

    "618": 12 if CAMPAIGN in ["五一六一618预热", "六一618端午"] else 2,
    "双11": 12 if CAMPAIGN in ["国庆双11预热", "双11"] else -10,
    "双十一": 12 if CAMPAIGN in ["国庆双11预热", "双11"] else -10,
    "双12": 10 if CAMPAIGN == "双12年货预热" else -5,
    "99大促": 10 if CAMPAIGN == "开学季99大促" else -3,
    "五一": 8 if CAMPAIGN == "五一六一618预热" else -2,
    "六一": 10 if CAMPAIGN in ["五一六一618预热", "六一618端午"] else -2,
    "儿童节": 10 if CAMPAIGN in ["五一六一618预热", "六一618端午"] else -2,
    "端午": 8 if CAMPAIGN == "六一618端午" else -2,
    "大促": 6, "预售": 5,

    "抖音": 7, "抖音电商": 8, "直播": 6,
    "小红书": 7, "种草": 6, "天猫": 5, "京东": 5, "唯品会": 5,
    "商场": 7, "商圈": 7, "购物中心": 7, "客流": 8, "门店": 7,
    "奥莱": 7, "折扣": 5, "会员": 5, "零售": 6, "消费": 5, "本地生活": 6,
    "户外": 7, "轻户外": 8, "露营": 6, "骑行": 6,
    "城市骑行": 8, "城市徒步": 7, "夜经济": 6, "文旅": 7, "出行": 5,

    "AI": 8, "人工智能": 8, "智能机器人": 7, "智能硬件": 6,
    "运动科技": 6, "智能穿戴": 6,
    "年轻人": 7, "00后": 7, "情绪消费": 8, "悦己": 7, "松弛感": 7,
    "社交消费": 6, "运动社交": 7, "女性消费": 6, "她经济": 6,
    "GDP": 5, "社零": 6, "就业": 5, "消费信心": 6, "促消费": 6,
    "消费分层": 6, "下沉市场": 6, "银发经济": 5, "理性消费": 5, "性价比": 6,
    "店播": 7, "会员复购": 7, "内容种草": 8, "达人矩阵": 6, "即时零售": 6,
}

HOT_WORDS.update(BRAND_WORDS)

SOURCE_PREFERENCE = [
    "界面新闻", "36氪", "赢商网", "联商网", "亿邦动力", "电商报",
    "中国商报", "北京商报", "第一财经", "证券时报", "新华网",
    "澎湃新闻", "每日经济新闻", "南方都市报", "腾讯新闻",
    "新京报", "中国经济网", "财联社", "虎嗅", "品牌星球",
    "本地宝", "文旅", "气象", "天气网", "中国天气",
    "晚点LatePost", "极客公园", "Tech星球", "FBIF",
]


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_title(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r" - .*?$", "", title)
    title = re.sub(r"_.*?$", "", title)
    title = title.replace("（图）", "").replace("(图)", "")
    return title.strip()


def has_any(text: str, words: list) -> bool:
    return any(w in text for w in words)


def detect_city(title: str) -> str:
    for city in CITY_TO_REGION.keys():
        if city in title:
            return city
    return ""


def detect_region(title: str) -> str:
    city = detect_city(title)
    if city:
        return CITY_TO_REGION.get(city, "全国")

    for region, cities in REGION_CITY_MAP.items():
        if region in title:
            return region
        if any(city in title for city in cities):
            return region

    return "全国"


def is_weather_abnormal(title: str) -> bool:
    return has_any(title, WEATHER_ABNORMAL_WORDS)


def is_local_business(title: str) -> bool:
    return detect_city(title) != "" and has_any(title, LOCAL_BUSINESS_WORDS)


def wrong_campaign_terms():
    all_terms = set()
    for terms in CAMPAIGN_GROUPS.values():
        all_terms.update(terms)
    current_terms = set(CAMPAIGN_GROUPS.get(CAMPAIGN, []))
    return list(all_terms - current_terms)


def campaign_bonus(title: str) -> int:
    score = 0
    current_terms = CAMPAIGN_GROUPS.get(CAMPAIGN, [])
    wrong_terms = wrong_campaign_terms()

    if any(k in title for k in current_terms):
        score += 18

    if any(k in title for k in wrong_terms):
        score -= 18

    if CAMPAIGN in ["五一六一618预热", "六一618端午", "暑期消费"]:
        if any(k in title for k in ["双11", "双十一", "双12", "年货节", "春节"]):
            score -= 35
        if any(k in title for k in ["618", "六一", "儿童节", "端午", "防晒", "凉感", "速干", "暑期"]):
            score += 15

    if CAMPAIGN in ["国庆双11预热", "双11", "双12年货预热"]:
        if any(k in title for k in ["618", "暑期", "夏季大促", "六一"]):
            score -= 30
        if any(k in title for k in ["双11", "双十一", "国庆", "中秋", "秋冬", "保暖", "防滑"]):
            score += 14

    return score


def fetch_google_news_rss(keyword: str):
    query = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    items = []

    for item in root.findall(".//item"):
        title = normalize_title(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        pub_date = clean_text(item.findtext("pubDate"))

        source = "Google News"
        source_node = item.find("source")
        if source_node is not None and source_node.text:
            source = clean_text(source_node.text)

        if title:
            city = detect_city(title)
            region = detect_region(title)
            weather_abnormal = is_weather_abnormal(title)

            items.append({
                "title": title,
                "source": source,
                "url": link,
                "published_at": pub_date,
                "keyword": keyword,
                "campaign": CAMPAIGN,
                "city": city,
                "region": region,
                "weather_abnormal": weather_abnormal,
                "local_business": is_local_business(title),
            })

    return items


def is_hard_negative(title: str) -> bool:
    return has_any(title, NEGATIVE_KEYWORDS)


def relevance_score(item: dict) -> int:
    title = item.get("title", "")
    source = item.get("source", "")

    score = 0

    for word, weight in HOT_WORDS.items():
        if word in title:
            score += weight

    score += campaign_bonus(title)

    for s in SOURCE_PREFERENCE:
        if s in source:
            score += 2

    combos = [
        (["童装", "儿童", "亲子"], 8),
        (["防晒", "凉感", "速干", "高温"], 7),
        (["商场", "商圈", "客流", "门店"], 7),
        (["抖音", "小红书", "直播", "种草"], 6),
        (["户外", "骑行", "露营", "文旅"], 6),
        (["Nike", "Adidas", "安踏", "李宁", "特步", "361"], 5),
        (["On", "HOKA", "亚瑟士", "跑步"], 5),
        (["AI", "消费", "零售"], 8),
        (["年轻人", "情绪消费"], 8),
        (["松弛感", "消费"], 6),
        (["城市骑行", "户外"], 7),
        (["文旅", "客流"], 7),
        (["GDP", "社零", "消费"], 7),
        (["就业", "收入", "消费"], 6),
        (["会员", "复购"], 7),
        (["店播", "直播"], 6),
        (["内容种草", "小红书"], 7),
    ]

    if CAMPAIGN in ["五一六一618预热", "六一618端午"]:
        combos.append((["618", "防晒", "凉感", "速干"], 8))
    elif CAMPAIGN in ["国庆双11预热", "双11"]:
        combos.append((["双11", "双十一", "保暖", "防滑"], 8))
    elif CAMPAIGN == "开学季99大促":
        combos.append((["开学", "校园", "儿童运动", "99大促"], 8))
    else:
        combos.append((["大促", "预售", "消费"], 5))

    for words, bonus in combos:
        if sum(1 for w in words if w in title) >= 2:
            score += bonus

    if item.get("local_business"):
        score += 12

    if item.get("weather_abnormal"):
        score += 10

    if item.get("city") and item.get("weather_abnormal"):
        score += 10

    if item.get("region") and item.get("region") != "全国":
        score += 5

    if is_hard_negative(title):
        score -= 35

    for w in SOFT_NEGATIVE_KEYWORDS:
        if w in title:
            score -= 5

    if "财报" in title and not has_any(title, ["童装", "儿童", "品牌", "零售", "消费", "渠道", "361", "安踏", "李宁", "特步"]):
        score -= 12

    return score


def dedupe(items):
    seen = set()
    result = []

    for item in items:
        title = normalize_title(item.get("title", ""))
        key = re.sub(r"\W+", "", title.lower())

        if not key or key in seen:
            continue

        seen.add(key)
        item["title"] = title
        result.append(item)

    return result


def bucket_name(title: str, item: dict = None):
    item = item or {}

    if item.get("weather_abnormal"):
        return "local_weather"
    if item.get("local_business"):
        return "local_business"

    current_terms = CAMPAIGN_GROUPS.get(CAMPAIGN, [])
    if has_any(title, current_terms):
        return "campaign"
    if has_any(title, ["童装", "儿童", "亲子", "校园"]):
        return "kids"
    if has_any(title, ["高温", "防晒", "凉感", "速干", "暴雨", "天气", "低温", "降雪", "结冰", "保暖", "防滑"]):
        return "weather"
    if has_any(title, ["AI", "人工智能", "智能", "科技", "机器人"]):
        return "ai_tech"
    if has_any(title, ["GDP", "社零", "就业", "收入", "消费信心", "促消费", "消费分层"]):
        return "macro"
    if has_any(title, ["年轻人", "情绪消费", "悦己", "松弛感", "女性消费", "她经济"]):
        return "trend"
    if has_any(title, ["抖音", "小红书", "直播", "种草", "天猫", "京东", "唯品会"]):
        return "platform"
    if has_any(title, ["商场", "商圈", "客流", "门店", "奥莱", "会员"]):
        return "store"
    if has_any(title, ["户外", "骑行", "露营", "文旅", "夜经济", "出行"]):
        return "outdoor"
    if has_any(title, list(BRAND_WORDS.keys())):
        return "brand"
    return "other"


def diversify(items):
    buckets = {
        "local_weather": [],
        "local_business": [],
        "campaign": [],
        "kids": [],
        "weather": [],
        "ai_tech": [],
        "macro": [],
        "trend": [],
        "platform": [],
        "store": [],
        "outdoor": [],
        "brand": [],
        "other": [],
    }

    for item in items:
        buckets[bucket_name(item.get("title", ""), item)].append(item)

    limits = {
        "local_weather": 20,
        "local_business": 24,
        "campaign": 16,
        "kids": 14,
        "weather": 14,
        "ai_tech": 10,
        "macro": 10,
        "trend": 10,
        "platform": 12,
        "store": 12,
        "outdoor": 10,
        "brand": 10,
        "other": 5,
    }

    order = [
        "local_weather",
        "local_business",
        "campaign",
        "kids",
        "weather",
        "ai_tech",
        "macro",
        "trend",
        "store",
        "platform",
        "outdoor",
        "brand",
        "other",
    ]

    final = []
    for key in order:
        final.extend(buckets[key][:limits[key]])

    final.sort(key=lambda x: x.get("score", 0), reverse=True)
    return final[:MAX_ITEMS]


def main():
    all_items = []

    print(f"Current campaign: {CAMPAIGN}")
    print(f"Total keywords: {len(KEYWORDS)}")

    for keyword in KEYWORDS:
        try:
            rows = fetch_google_news_rss(keyword)
            all_items.extend(rows)
            print(f"Fetched {len(rows)} items for: {keyword}")
            time.sleep(0.35)
        except Exception as e:
            print(f"Fetch failed: {keyword} | {e}")

    all_items = dedupe(all_items)

    filtered = []
    for item in all_items:
        score = relevance_score(item)
        if score > 0:
            item["score"] = score
            filtered.append(item)

    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    filtered = diversify(filtered)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    region_counts = {}
    for item in filtered:
        region = item.get("region", "全国")
        region_counts[region] = region_counts.get(region, 0) + 1

    payload = {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "campaign": CAMPAIGN,
        "count": len(filtered),
        "region_counts": region_counts,
        "items": filtered,
    }

    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(filtered)} filtered news items to {OUT_FILE}")
    print("Region counts:", region_counts)

    for i, item in enumerate(filtered[:25], start=1):
        print(
            f"{i}. [{item.get('score')}] "
            f"[{item.get('region')}/{item.get('city') or '-'}] "
            f"{item.get('title')} | {item.get('source')}"
        )


if __name__ == "__main__":
    main()
