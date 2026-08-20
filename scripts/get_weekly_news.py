from __future__ import annotations

import hashlib
import html as html_lib
import json
import os
import re
import time
import xml.etree.ElementTree as ET

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as dt_time, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================================================
# 0. 输出与运行配置
# =========================================================

TIMEZONE_NAME = "Asia/Shanghai"
LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

OUTPUT_DIR = Path("output/weekly")
ARCHIVE_DIR = OUTPUT_DIR / "archive"
OUTPUT_FILE = OUTPUT_DIR / "weekly_sources.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

RSS_PER_QUERY = 12
MAX_QUERIES = 120
MAX_ITEMS = 240
ENRICH_LIMIT = 90
ENRICH_WORKERS = 8
REQUEST_TIMEOUT = 16
QUERY_INTERVAL = 0.18
HISTORY_DAYS = 60

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 TrendRadarWeekly/2.0"
)


def get_report_window() -> tuple[date, date]:
    """
    默认统计最近7个完整自然日。

    周一早上运行时，对应上周一至周日。
    如需重跑指定周，可设置环境变量：
    WEEKLY_END_DATE=2026-08-16
    """
    override = os.getenv("WEEKLY_END_DATE", "").strip()

    if override:
        end_date = datetime.strptime(override, "%Y-%m-%d").date()
    else:
        end_date = datetime.now(LOCAL_TZ).date() - timedelta(days=1)

    start_date = end_date - timedelta(days=6)
    return start_date, end_date


REPORT_START_DATE, REPORT_END_DATE = get_report_window()
WINDOW_START = datetime.combine(REPORT_START_DATE, dt_time.min, tzinfo=LOCAL_TZ)
WINDOW_END = datetime.combine(REPORT_END_DATE, dt_time.max, tzinfo=LOCAL_TZ)
GENERATED_AT = datetime.now(LOCAL_TZ)


# =========================================================
# 1. 监测范围
# =========================================================

BRANDS = [
    "361儿童", "361°儿童", "361度儿童", "361°", "361度",
    "安踏儿童", "安踏", "FILA KIDS", "FILA Kids", "FILA",
    "李宁YOUNG", "李宁", "特步儿童", "特步", "匹克", "鸿星尔克",
    "Nike Kids", "Nike", "耐克", "Jordan",
    "Adidas Kids", "Adidas", "阿迪达斯",
    "Puma", "彪马", "New Balance", "ASICS", "亚瑟士",
    "Skechers", "斯凯奇", "Under Armour",
    "On昂跑", "昂跑", "On Running", "HOKA", "Salomon", "萨洛蒙",
    "lululemon", "Alo Yoga", "Alo",
    "始祖鸟", "Arc'teryx", "The North Face", "北面",
    "迪桑特", "Descente", "凯乐石", "KAILAS", "可隆", "KOLON SPORT",
    "迪卡侬", "Decathlon", "巴拉巴拉", "moodytiger",
]

BRAND_ALIASES = {
    "361°儿童": "361儿童",
    "361度儿童": "361儿童",
    "361度": "361°",
    "FILA Kids": "FILA KIDS",
    "耐克": "Nike",
    "阿迪达斯": "Adidas",
    "彪马": "Puma",
    "亚瑟士": "ASICS",
    "斯凯奇": "Skechers",
    "昂跑": "On昂跑",
    "On Running": "On昂跑",
    "萨洛蒙": "Salomon",
    "北面": "The North Face",
    "Descente": "迪桑特",
    "KAILAS": "凯乐石",
    "KOLON SPORT": "可隆",
    "Decathlon": "迪卡侬",
}

KIDS_WORDS = [
    "儿童", "青少年", "大童", "中大童", "童鞋", "童装", "亲子",
    "校园运动", "体育中考", "足弓", "成长鞋", "开学",
]

PRODUCT_WORDS = [
    "新品", "新款", "上新", "首发", "发售", "开售", "发布", "推出",
    "系列", "跑鞋", "篮球鞋", "足球鞋", "训练鞋", "童鞋", "运动鞋",
    "越野跑鞋", "户外鞋", "徒步鞋", "凉鞋", "拖鞋", "恢复鞋",
    "防晒衣", "速干", "凉感", "冲锋衣", "羽绒服", "运动服",
    "瑜伽服", "运动内衣", "碳板", "缓震", "中底", "面料", "科技平台",
]

BUSINESS_WORDS = [
    "战略", "财报", "业绩", "营收", "利润", "增长", "下滑", "毛利率",
    "中国市场", "渠道", "经销商", "库存", "供应链", "智能制造",
    "门店", "旗舰店", "开业", "闭店", "商圈", "零售", "电商", "平台",
    "直播", "天猫", "淘宝", "京东", "抖音", "小红书", "得物", "唯品会",
    "签约", "代言", "联名", "合作", "收购", "出售", "任命", "CEO",
    "总裁", "管理层", "出海", "市场份额", "消费", "社零", "政策",
    "报告", "白皮书", "市场规模", "体育产业", "体育消费",
]

SCENE_WORDS = [
    "跑步", "马拉松", "篮球", "足球", "网球", "羽毛球", "健身", "瑜伽",
    "户外", "轻户外", "徒步", "越野", "露营", "骑行", "滑雪", "运动休闲",
]

RELEVANCE_WORDS = list(dict.fromkeys(KIDS_WORDS + PRODUCT_WORDS + BUSINESS_WORDS + SCENE_WORDS + [
    "运动品牌", "运动鞋服", "体育用品", "鞋服", "服装", "鞋业", "购物中心",
]))

HARD_BAD_WORDS = [
    "彩票", "博彩", "赌球", "比分", "赛程", "转会", "伤病名单", "首发阵容",
    "主教练下课", "股票推荐", "个股推荐", "涨停", "跌停", "龙虎榜", "目标价",
    "买入评级", "荐股", "股价", "支撑位", "阻力位", "技术面", "K线",
    "优惠券", "券后", "凑单", "省钱快报", "招商加盟",
    "加盟代理", "招聘", "成人用品", "汽车导购", "购车", "新车上市",
    "手机评测", "电视评测", "楼市", "房价",
]

LOW_VALUE_WORDS = [
    "怎么买", "怎么选", "哪个牌子好", "排行榜", "推荐购买", "值得买",
    "开箱测评", "深度测评", "避坑", "种草清单", "好物推荐", "低至",
    "直降", "满减", "包邮", "抽奖", "送福利", "适合去哪", "去哪玩",
    "旅游攻略", "选购指南", "+FAQ", "FAQ", "门票攻略", "一日游攻略",
]

# 这些内容可以作为场景素材留在原始items中，但不应进入管理层核心事件。
LOCAL_PROMO_WORDS = [
    "打卡", "趣味运动会", "社区活动", "亲子家庭", "嘉年华", "游园会",
    "一日游", "亲子游", "文商旅体", "现场体验", "报名开启",
]

CLICKBAIT_WORDS = [
    "救", "魔法", "爆了", "炸了", "最怕", "背后", "能否", "为何",
    "怎么办", "稳住", "抢钱", "突然", "彻底", "狂飙",
]

GENERIC_DESCRIPTION_WORDS = [
    "Comprehensive up-to-date news coverage",
    "aggregated from sources all over the world by Google News",
    "Google News provides comprehensive",
    "Read full coverage",
    "查看完整报道",
    "由 Google 新闻汇总",
]

GENERIC_IMAGE_WORDS = [
    "google", "gstatic", "logo", "icon", "favicon", "avatar", "default",
    "placeholder", "sprite", "brandmark", "site-logo", "site_logo",
]

EVENT_KEYWORDS = [
    "财报", "业绩", "营收", "利润", "战略", "收购", "出售", "签约", "代言",
    "联名", "新品", "发布", "首发", "门店", "旗舰店", "开业", "闭店",
    "渠道", "经销商", "库存", "供应链", "任命", "CEO", "总裁", "管理层",
    "平台规则", "流量机制", "直播", "体育消费", "社零", "市场规模",
]

CONFLICT_NEGATIVE_WORDS = ["否认", "辟谣", "不实", "未签约", "没有签约", "终止", "取消", "澄清"]
CONFLICT_POSITIVE_WORDS = ["正式签约", "官宣", "拿下", "达成合作", "宣布收购", "完成收购", "正式任命"]
CONFLICT_ACTION_WORDS = ["签约", "代言", "合作", "收购", "出售", "任命", "开业", "发布"]


# =========================================================
# 2. 查询配置：大促只在对应时间窗口启用
# =========================================================

BRAND_QUERY_NAMES = [
    "361度", "安踏", "李宁", "特步", "Nike", "Adidas", "Puma",
    "FILA", "New Balance", "ASICS", "On昂跑", "HOKA", "Salomon",
    "lululemon", "Alo Yoga", "始祖鸟", "The North Face", "迪桑特",
    "凯乐石", "迪卡侬", "巴拉巴拉",
]

BASE_QUERY_GROUPS = {
    "kids": [
        "儿童运动 行业",
        "青少年运动 消费",
        "儿童运动鞋 新品",
        "儿童跑鞋 足弓",
        "青少年篮球鞋",
        "校园运动 鞋服",
        "童装 运动功能",
        "亲子户外 消费",
    ],
    "product": [
        "运动品牌 新品 发布",
        "跑鞋 科技 新品",
        "篮球鞋 新品 科技",
        "户外鞋服 新品",
        "防晒衣 运动品牌",
        "运动恢复 鞋类",
        "轻户外 功能服饰",
    ],
    "brand_business": [
        "运动品牌 财报 业绩",
        "运动品牌 中国市场",
        "运动品牌 战略 调整",
        "运动品牌 管理层 任命",
        "运动品牌 收购 出售",
        "运动品牌 渠道 库存",
        "运动品牌 供应链 智能制造",
        "运动品牌 门店 旗舰店",
    ],
    "channel": [
        "天猫 运动户外 平台",
        "京东 运动服饰",
        "抖音电商 运动品牌",
        "小红书 运动消费",
        "得物 运动鞋",
        "唯品会 运动服饰",
        "购物中心 运动品牌",
        "奥莱 运动品牌",
        "运动零售 渠道变革",
    ],
    "consumer_macro": [
        "体育消费 数据",
        "运动消费 趋势",
        "服装鞋帽 社会消费品零售",
        "户外消费 市场",
        "健康消费 体育产业",
        "居民消费 运动鞋服",
    ],
    "research": [
        "运动鞋服 行业报告",
        "体育消费 白皮书",
        "鞋服行业 数据",
        "零售行业 消费洞察",
        "儿童消费 研究",
    ],
}

SEASONAL_CAMPAIGNS = [
    {
        "name": "三八节",
        "start": (2, 20),
        "end": (3, 15),
        "queries": ["三八节 女性运动 消费", "三八节 运动品牌"],
    },
    {
        "name": "六一",
        "start": (5, 10),
        "end": (6, 5),
        "queries": ["六一 儿童运动", "儿童节 童鞋 童装"],
    },
    {
        "name": "618",
        "start": (5, 15),
        "end": (6, 25),
        "queries": ["618 运动户外 平台数据", "618 儿童运动鞋", "618 运动品牌 战报"],
    },
    {
        "name": "暑期",
        "start": (6, 15),
        "end": (8, 31),
        "queries": ["暑期 体育消费", "暑期 亲子户外", "夏季 防晒 运动服饰"],
    },
    {
        "name": "开学季",
        "start": (7, 20),
        "end": (9, 10),
        "queries": ["开学季 儿童运动鞋", "开学季 青少年运动", "校园运动 鞋服"],
    },
    {
        "name": "99大促",
        "start": (8, 20),
        "end": (9, 15),
        "queries": ["99大促 运动户外", "99大促 童鞋"],
    },
    {
        "name": "国庆出行",
        "start": (9, 15),
        "end": (10, 10),
        "queries": ["国庆 户外消费", "国庆 亲子出行 运动"],
    },
    {
        "name": "双11",
        "start": (10, 10),
        "end": (11, 20),
        "queries": ["双11 运动户外 平台数据", "双11 儿童运动鞋", "双11 运动品牌 战报"],
    },
    {
        "name": "双12",
        "start": (11, 25),
        "end": (12, 18),
        "queries": ["双12 运动户外", "双12 童鞋 童装"],
    },
]


def campaign_dates(year: int, start_md: tuple[int, int], end_md: tuple[int, int]) -> tuple[date, date]:
    start = date(year, start_md[0], start_md[1])
    end = date(year, end_md[0], end_md[1])
    return start, end


def ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return max(a_start, b_start) <= min(a_end, b_end)


def build_queries() -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []

    for group, queries in BASE_QUERY_GROUPS.items():
        for query_text in queries:
            rows.append({"group": group, "query": query_text})

    for brand in BRAND_QUERY_NAMES:
        rows.append({
            "group": "brand",
            "query": f'"{brand}" (战略 OR 财报 OR 新品 OR 门店 OR 渠道 OR 中国市场 OR 签约 OR 联名)',
        })

    active_campaigns: list[str] = []
    years = {REPORT_START_DATE.year, REPORT_END_DATE.year}

    for campaign in SEASONAL_CAMPAIGNS:
        enabled = False
        for year in years:
            start, end = campaign_dates(year, campaign["start"], campaign["end"])
            if ranges_overlap(REPORT_START_DATE, REPORT_END_DATE, start, end):
                enabled = True
                break

        if enabled:
            active_campaigns.append(campaign["name"])
            for query_text in campaign["queries"]:
                rows.append({"group": "seasonal", "query": query_text})

    deduped: list[dict[str, str]] = []
    used = set()

    for row in rows:
        key = row["query"].strip().lower()
        if not key or key in used:
            continue
        used.add(key)
        deduped.append(row)

    return deduped[:MAX_QUERIES], active_campaigns


# =========================================================
# 3. 文本、日期与链接工具
# =========================================================

def clean_text(value: Any) -> str:
    text = html_lib.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u200b", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_url(value: Any) -> str:
    url = clean_text(value)
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return ""


def normalize_title(title: str, source: str = "") -> str:
    title = clean_text(title)
    source = clean_text(source)

    if source:
        for separator in [" - ", " – ", " — ", " | "]:
            suffix = f"{separator}{source}"
            if title.lower().endswith(suffix.lower()):
                title = title[:-len(suffix)].strip()
                break

    return title


def norm_key(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|·]+", "", text)
    return text[:100]


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}_{digest}"


def parse_published_at(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None

    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(LOCAL_TZ)
    except Exception:
        pass

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(LOCAL_TZ)
    except Exception:
        return None


def in_report_window(dt: datetime | None) -> bool:
    return bool(dt and WINDOW_START <= dt <= WINDOW_END)


def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def is_external_article_url(url: str) -> bool:
    host = host_of(url)
    if not host:
        return False
    blocked = [
        "news.google.com", "google.com", "consent.google.com", "accounts.google.com",
        "facebook.com", "x.com", "twitter.com", "weibo.com", "youtube.com",
    ]
    return not any(host == x or host.endswith("." + x) for x in blocked)


def site_hint(host: str) -> str:
    """用于自动链接解析的轻量同站判断，不承担严格公共后缀识别。"""
    host = clean_text(host).lower().removeprefix("www.")
    parts = [x for x in host.split(".") if x]
    if len(parts) <= 2:
        return host
    if tuple(parts[-2:]) in {("com", "cn"), ("net", "cn"), ("org", "cn"), ("gov", "cn")}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_site(url_a: str, url_b: str) -> bool:
    left = site_hint(host_of(url_a))
    right = site_hint(host_of(url_b))
    return bool(left and right and left == right)


def prepare_description(value: Any, title: str = "") -> str:
    text = clean_text(value)
    if len(text) < 28:
        return ""
    if has_any(text, GENERIC_DESCRIPTION_WORDS):
        return ""
    if title and title_similarity(text, title) >= 0.92:
        return ""
    if has_any(text, ["Javascript is disabled", "请启用JavaScript", "访问验证", "安全验证"]):
        return ""

    # 把网页描述控制在适合后续编辑的长度，尽量在句号处截断。
    if len(text) > 360:
        candidate = text[:360]
        stops = [candidate.rfind(mark) for mark in ["。", "！", "？", ". "]]
        stop = max(stops)
        text = candidate[:stop + 1] if stop >= 80 else candidate.rstrip() + "…"

    return text


def is_valid_image_url(url: str, width: int = 0, height: int = 0) -> bool:
    url = clean_url(url)
    if not url:
        return False

    lower = url.lower()
    host = host_of(url)
    if any(token in lower for token in GENERIC_IMAGE_WORDS):
        return False
    if any(domain in host for domain in ["googleusercontent.com", "gstatic.com", "google.com"]):
        return False
    if re.search(r"\.(?:svg|ico|gif)(?:\?|$)", lower):
        return False
    if width and width < 400:
        return False
    if height and height < 180:
        return False
    return True


def has_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(word.lower() in lower for word in words)


def detect_brands(title: str) -> list[str]:
    lower = title.lower()
    hits = []

    for brand in sorted(BRANDS, key=len, reverse=True):
        if brand.lower() in lower:
            normalized = BRAND_ALIASES.get(brand, brand)
            if normalized not in hits:
                hits.append(normalized)

    return hits


def detect_keywords(title: str) -> list[str]:
    words = EVENT_KEYWORDS + PRODUCT_WORDS + KIDS_WORDS + SCENE_WORDS
    return [word for word in dict.fromkeys(words) if word.lower() in title.lower()][:14]


def detect_category(title: str, query_groups: list[str]) -> str:
    if has_any(title, KIDS_WORDS):
        return "儿童与青少年"
    if has_any(title, ["天猫", "淘宝", "京东", "抖音", "小红书", "得物", "唯品会", "直播", "电商"]):
        return "电商与平台"
    if has_any(title, ["财报", "业绩", "营收", "利润", "毛利率", "CEO", "总裁", "收购", "出售", "战略"]):
        return "品牌与公司"
    if has_any(title, PRODUCT_WORDS):
        return "产品与科技"
    if has_any(title, ["户外", "徒步", "露营", "越野", "骑行", "滑雪"]):
        return "户外与场景"
    if has_any(title, ["社零", "体育消费", "消费数据", "消费信心", "政策", "体育产业"]):
        return "宏观与消费"
    if has_any(title, ["报告", "白皮书", "研究", "洞察", "市场规模"]):
        return "研究与数据"
    if "channel" in query_groups:
        return "渠道与零售"
    return "行业动态"


def detect_reporting_period(title: str, published_at: Any = "") -> str:
    dt = parse_published_at(published_at)
    fallback_year = dt.year if dt else REPORT_END_DATE.year
    year_match = re.search(r"(20\d{2})年?", title)
    year = int(year_match.group(1)) if year_match else fallback_year

    if has_any(title, ["上半年", "半年", "半年度", "中期业绩", "中期报告", "半年报"]):
        return f"{year}_h1"
    if has_any(title, ["下半年"]):
        return f"{year}_h2"
    if re.search(r"(?:Q1|第一季度|一季度)", title, flags=re.I):
        return f"{year}_q1"
    if re.search(r"(?:Q2|第二季度|二季度)", title, flags=re.I):
        return f"{year}_q2"
    if re.search(r"(?:Q3|第三季度|三季度)", title, flags=re.I):
        return f"{year}_q3"
    if re.search(r"(?:Q4|第四季度|四季度)", title, flags=re.I):
        return f"{year}_q4"
    if has_any(title, ["全年业绩", "年度业绩", "年报"]):
        return f"{year}_fy"
    return ""


def detect_event_family(title: str) -> str:
    # 财务事件放在渠道判断之前，使“半年关店/渠道调整”仍与同期业绩合并阅读。
    if has_any(title, ["财报", "业绩", "营收", "收入", "净利", "利润", "毛利率", "半年报", "中期"]):
        return "financial_results"
    if detect_reporting_period(title) and has_any(title, ["增长", "下滑", "关店", "闭店", "门店", "渠道"]):
        return "financial_results"
    if has_any(title, ["收购", "出售", "并购", "投资入股", "易主"]):
        return "capital_strategy"
    if has_any(title, ["CEO", "总裁", "董事长", "高管", "管理层", "任命", "换帅"]):
        return "management"
    if has_any(title, ["签约", "代言", "合作伙伴", "赞助"]):
        return "endorsement_partnership"
    if has_any(title, ["联名", "限定", "共创"]):
        return "collaboration"
    if has_any(title, ["新品", "新款", "首发", "发售", "开售", "上新", "推出"]):
        return "product_launch"
    if has_any(title, ["旗舰店", "开业", "开店", "闭店", "关店", "门店", "奥莱"]):
        return "store_channel"
    if has_any(title, ["平台规则", "流量机制", "直播", "天猫", "京东", "抖音", "小红书", "唯品会"]):
        return "platform_channel"
    if has_any(title, ["社零", "社会消费品零售", "国家统计局", "体育消费", "市场规模"]):
        return "macro_data"
    if has_any(title, LOCAL_PROMO_WORDS):
        return "local_activity"
    if has_any(title, ["报告", "白皮书", "研究", "洞察", "调查"]):
        return "research_report"
    return "industry_event"


def event_signature(item: dict[str, Any]) -> str:
    title = item.get("title", "")
    brands = safe_list(item.get("brands")) or detect_brands(title)
    brand = brands[0] if brands else "industry"
    family = item.get("event_family") or detect_event_family(title)
    period = item.get("reporting_period") or detect_reporting_period(title, item.get("published_at"))

    # 同品牌、同财务周期的报道无论分别强调收入、海外或门店，都归为一个事件。
    if family == "financial_results" and period:
        return f"{brand}|{family}|{period}"

    return f"{brand}|{family}|{similarity_text(title)[:32]}"


def core_exclusion_reason(item: dict[str, Any]) -> str:
    title = clean_text(item.get("title"))
    source_tier = item.get("source_tier", "tier_3")
    score = int(item.get("editorial_score", 0))

    if source_tier == "low":
        return "low_quality_source"
    if has_any(title, LOCAL_PROMO_WORDS):
        return "local_promotional_activity"
    if score < 42:
        return "editorial_score_below_core_threshold"
    if not item.get("is_official") and source_tier == "tier_3" and not detect_brands(title):
        return "weak_single_source_without_brand"
    return ""


# =========================================================
# 4. 来源分级与筛选
# =========================================================

OFFICIAL_SOURCE_WORDS = [
    "国家统计局", "商务部", "国家体育总局", "国务院", "公司官网", "官方",
    "Nike Newsroom", "adidas News", "安踏集团", "李宁公司", "特步集团", "361度集团",
]

TIER_1_WORDS = [
    "国家统计局", "商务部", "国家体育总局", "新华社", "新华网", "人民网", "央视网",
    "路透", "Reuters", "彭博", "Bloomberg", "公司官网", "官方",
]

TIER_2_WORDS = [
    "第一财经", "界面新闻", "Jiemian", "财新", "经济观察报", "新京报", "澎湃",
    "36氪", "亿邦动力", "联商网", "赢商网", "电商报", "CBNData", "华丽志",
    "时尚商业", "中国纺织报", "中国商报", "证券时报", "美通社",
]

LOW_SOURCE_WORDS = [
    "百家号", "财富号", "搜狐号", "自媒体", "个人号", "省钱快报",
    "Traders Union", "Dealmoon", "北美省钱快报",
]

LOW_SOURCE_DOMAINS = [
    "dealmoon.com", "dealmoon.ca", "tradersunion.com", "sohu.com",
]

OFFICIAL_DOMAINS = [
    "stats.gov.cn", "mofcom.gov.cn", "sport.gov.cn", "gov.cn",
    "nike.com", "about.nike.com", "adidas-group.com", "adidas.com",
    "anta.com", "anta.com.cn", "lining.com", "xtep.com.cn", "361sport.com",
    "lululemon.com", "on.com", "hoka.com", "puma.com", "asics.com",
    "salomon.com", "newbalance.com", "decathlon.com",
]

SOURCE_NAME_ALIASES = {
    "thepaper.cn": "澎湃新闻",
    "澎湃": "澎湃新闻",
    "stats.gov.cn": "国家统计局",
    "国家统计局": "国家统计局",
    "mofcom.gov.cn": "商务部",
    "sport.gov.cn": "国家体育总局",
    "xinhuanet.com": "新华网",
    "新华网": "新华网",
    "people.com.cn": "人民网",
    "jiemian.com": "界面新闻",
    "Jiemian": "界面新闻",
    "yicai.com": "第一财经",
    "第一财经": "第一财经",
    "ebrun.com": "亿邦动力",
    "亿邦动力": "亿邦动力",
    "cbndata.com": "CBNData",
    "womenofchina.com": "中国妇女网",
    "shyp.gov.cn": "上海杨浦",
    "xinhua": "新华网",
    "Sohu": "搜狐网",
    "搜狐": "搜狐网",
}

DOMAIN_SOURCE_NAMES = [
    ("stats.gov.cn", "国家统计局"),
    ("mofcom.gov.cn", "商务部"),
    ("sport.gov.cn", "国家体育总局"),
    ("xinhuanet.com", "新华网"),
    ("people.com.cn", "人民网"),
    ("thepaper.cn", "澎湃新闻"),
    ("jiemian.com", "界面新闻"),
    ("yicai.com", "第一财经"),
    ("ebrun.com", "亿邦动力"),
    ("cbndata.com", "CBNData"),
    ("womenofchina.com", "中国妇女网"),
    ("shyp.gov.cn", "上海杨浦"),
    ("dealmoon.com", "北美省钱快报"),
    ("dealmoon.ca", "北美省钱快报"),
]


def normalize_source_name(source: str, *urls: str) -> str:
    original = clean_text(source)
    lower_source = original.lower()

    for key, display in SOURCE_NAME_ALIASES.items():
        if key.lower() in lower_source:
            return display

    hosts = " ".join(host_of(url) for url in urls if clean_url(url))
    for domain, display in DOMAIN_SOURCE_NAMES:
        if domain in hosts:
            return display

    return original


def source_profile(source: str, source_url: str, direct_url: str = "") -> tuple[str, bool, int]:
    text = f"{source} {source_url} {direct_url}"
    host_text = f"{host_of(source_url)} {host_of(direct_url)}"

    official = has_any(text, OFFICIAL_SOURCE_WORDS) or any(domain in host_text for domain in OFFICIAL_DOMAINS)

    if official:
        return "official", True, 28
    if has_any(text, TIER_1_WORDS):
        return "tier_1", False, 24
    if has_any(text, TIER_2_WORDS):
        return "tier_2", False, 18
    if has_any(text, LOW_SOURCE_WORDS) or any(domain in host_text for domain in LOW_SOURCE_DOMAINS):
        return "low", False, 3
    return "tier_3", False, 10


def reject_reason(title: str, source: str, published_at: datetime | None, query_groups: list[str]) -> str:
    full = f"{title} {source}"

    if not title or len(title) < 8:
        return "missing_or_short_title"
    if not source:
        return "missing_source"
    if not published_at:
        return "missing_time"
    if not in_report_window(published_at):
        return "outside_window"
    if has_any(full, HARD_BAD_WORDS):
        return "hard_bad_topic"
    if has_any(title, LOW_VALUE_WORDS):
        return "low_value_content"

    brands = detect_brands(title)
    relevant = bool(brands) or has_any(title, RELEVANCE_WORDS)

    if not relevant:
        return "not_industry_relevant"

    # 品牌词本身不够；体育赛果、球员新闻必须同时出现经营或商品信息才保留。
    sport_noise = has_any(title, ["比赛", "联赛", "决赛", "球队", "球员", "进球", "战胜", "不敌", "夺冠"])
    business_or_product = has_any(title, BUSINESS_WORDS + PRODUCT_WORDS)
    if sport_noise and not business_or_product:
        return "sports_result_or_team_news"

    # 宏观查询只保留与消费、零售、体育产业有关的内容。
    if query_groups == ["consumer_macro"] and not has_any(title, ["消费", "零售", "体育", "服装", "鞋帽", "户外", "健康"]):
        return "macro_not_relevant"

    return ""


def editorial_score(item: dict[str, Any]) -> int:
    published_at = parse_published_at(item.get("published_at"))
    age_hours = 9999.0
    if published_at:
        age_hours = max(0.0, (WINDOW_END - published_at).total_seconds() / 3600)

    if age_hours <= 24:
        freshness = 24
    elif age_hours <= 72:
        freshness = 20
    elif age_hours <= 120:
        freshness = 16
    else:
        freshness = 12

    _, _, source_points = source_profile(
        item.get("source", ""),
        item.get("source_url", ""),
        item.get("direct_url", ""),
    )

    title = item.get("title", "")
    impact = 0
    for word in EVENT_KEYWORDS:
        if word.lower() in title.lower():
            impact += 5
    impact = min(impact, 30)

    specificity = 0
    if re.search(r"\d+(?:\.\d+)?%", title):
        specificity += 7
    if re.search(r"\d+(?:\.\d+)?(?:亿|万|元|美元|港元|门|家)", title):
        specificity += 6
    if detect_brands(title):
        specificity += 5
    if has_any(title, ["官方", "公布", "发布", "宣布"]):
        specificity += 3

    kids_bonus = 6 if has_any(title, KIDS_WORDS) else 0
    penalty = 0
    if has_any(title, LOCAL_PROMO_WORDS):
        penalty += 25
    if has_any(title, CLICKBAIT_WORDS) or "?" in title or "？" in title:
        penalty += 6
    if source_profile(
        item.get("source", ""),
        item.get("source_url", ""),
        item.get("direct_url", ""),
    )[0] == "low":
        penalty += 12

    score = freshness + source_points + impact + min(specificity, 15) + kids_bonus - penalty
    return max(1, min(100, score))


# =========================================================
# 5. Google News RSS抓取
# =========================================================

def google_news_rss_url(query_text: str) -> str:
    # Google的after/before只用于缩小范围，最终仍由本地时间做硬过滤。
    search_after = REPORT_START_DATE - timedelta(days=1)
    search_before = REPORT_END_DATE + timedelta(days=1)
    query = f"{query_text} after:{search_after.isoformat()} before:{search_before.isoformat()}"
    return (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )


def fetch_rss(query_row: dict[str, str], session: requests.Session) -> tuple[list[dict[str, Any]], str]:
    url = google_news_rss_url(query_row["query"])

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        return [], repr(exc)

    rows = []

    for node in root.findall(".//item")[:RSS_PER_QUERY]:
        source_node = node.find("source")
        source_original = clean_text(source_node.text if source_node is not None else "")
        source_url = clean_url(source_node.attrib.get("url", "") if source_node is not None else "")
        source = normalize_source_name(source_original, source_url)
        title = normalize_title(node.findtext("title") or "", source_original)
        pub_raw = clean_text(node.findtext("pubDate"))
        pub_dt = parse_published_at(pub_raw)

        row = {
            "title": title,
            "source": source,
            "source_original": source_original,
            "source_url": source_url,
            "google_news_url": clean_url(node.findtext("link")),
            "direct_url": "",
            "url": clean_url(node.findtext("link")),
            "published_at": pub_dt.isoformat(timespec="minutes") if pub_dt else "",
            "published_date": pub_dt.date().isoformat() if pub_dt else "",
            "rss_description": clean_text(node.findtext("description")),
            "query_groups": [query_row["group"]],
            "discovered_by": [query_row["query"]],
        }
        rows.append(row)

    return rows, ""


# =========================================================
# 6. 去重、网页元数据补全与事件聚类
# =========================================================

def merge_exact_duplicates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}

    for item in items:
        key = norm_key(item.get("title"))
        if not key:
            continue

        if key not in best:
            best[key] = item
            continue

        old = best[key]
        old["query_groups"] = list(dict.fromkeys(safe_list(old.get("query_groups")) + safe_list(item.get("query_groups"))))
        old["discovered_by"] = list(dict.fromkeys(safe_list(old.get("discovered_by")) + safe_list(item.get("discovered_by"))))

        if editorial_score(item) > editorial_score(old):
            item["query_groups"] = old["query_groups"]
            item["discovered_by"] = old["discovered_by"]
            best[key] = item

    return list(best.values())


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def meta_content(soup: BeautifulSoup, *, name: str = "", prop: str = "") -> str:
    node = None
    if prop:
        node = soup.find("meta", attrs={"property": prop})
    if not node and name:
        node = soup.find("meta", attrs={"name": name})
    if node:
        return clean_text(node.get("content", ""))
    return ""


def meta_int(soup: BeautifulSoup, prop: str) -> int:
    value = meta_content(soup, prop=prop)
    match = re.search(r"\d+", value)
    return int(match.group()) if match else 0


def discover_original_url(soup: BeautifulSoup, base_url: str, source_url: str) -> str:
    """从Google News落地页中只选择与RSS来源站点一致的外链，避免误取广告链接。"""
    candidates = []

    for node in [
        soup.find("link", attrs={"rel": "canonical"}),
        soup.find("meta", attrs={"property": "og:url"}),
        soup.find("meta", attrs={"name": "twitter:url"}),
    ]:
        if not node:
            continue
        value = node.get("href") or node.get("content") or ""
        candidate = clean_url(urljoin(base_url, value))
        if candidate:
            candidates.append(candidate)

    for node in soup.find_all("a", href=True):
        candidate = clean_url(urljoin(base_url, node.get("href", "")))
        if candidate:
            candidates.append(candidate)

    deduped = []
    used = set()
    for candidate in candidates:
        if candidate in used or not is_external_article_url(candidate):
            continue
        used.add(candidate)
        path = urlparse(candidate).path.strip("/")
        if len(path) < 3:
            continue
        deduped.append(candidate)

    same_source = [x for x in deduped if source_url and same_site(x, source_url)]
    if same_source:
        return max(same_source, key=lambda x: len(urlparse(x).path))
    return ""


def json_ld_description(soup: BeautifulSoup) -> str:
    for node in soup.find_all("script", attrs={"type": "application/ld+json"})[:12]:
        try:
            data = json.loads(node.string or node.get_text() or "")
        except Exception:
            continue

        queue = data if isinstance(data, list) else [data]
        while queue:
            current = queue.pop(0)
            if not isinstance(current, dict):
                continue
            description = clean_text(current.get("description"))
            if description:
                return description
            graph = current.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
    return ""


def first_article_paragraph(soup: BeautifulSoup) -> str:
    selectors = [
        "article p", ".article-content p", ".article_content p", ".content p",
        ".post-content p", ".story-body p", "main p",
    ]
    for selector in selectors:
        for node in soup.select(selector)[:12]:
            text = clean_text(node.get_text(" ", strip=True))
            if 45 <= len(text) <= 600 and not has_any(
                text,
                ["责任编辑", "版权声明", "免责声明", "扫码", "关注公众号", "打开客户端"],
            ):
                return text
    return ""


def enrich_one(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    url = clean_url(item.get("google_news_url") or item.get("url"))

    if not url:
        return enriched

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers=headers,
        )
        response.raise_for_status()
    except Exception:
        enriched["link_status"] = "google_news_fallback"
        enriched.pop("meta_description", None)
        enriched.pop("image_url", None)
        return enriched

    final_url = clean_url(response.url)
    direct_url = final_url if is_external_article_url(final_url) else ""
    response_soup = None

    if "html" in response.headers.get("content-type", "").lower():
        try:
            response_soup = BeautifulSoup(response.text[:1_500_000], "html.parser")
        except Exception:
            response_soup = None

    if not direct_url and response_soup is not None:
        direct_url = discover_original_url(
            response_soup,
            final_url or url,
            clean_url(item.get("source_url")),
        )

    # Google落地页本身没有可核验摘要和新闻图片，宁可留空也不使用Google占位内容。
    if not direct_url:
        enriched["url"] = url
        enriched["link_status"] = "google_news_fallback"
        enriched.pop("meta_description", None)
        enriched.pop("image_url", None)
        return enriched

    article_response = response
    if not same_site(final_url, direct_url):
        try:
            article_response = requests.get(
                direct_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
                headers=headers,
            )
            article_response.raise_for_status()
            if is_external_article_url(article_response.url):
                direct_url = clean_url(article_response.url)
        except Exception:
            article_response = None

    enriched["direct_url"] = direct_url
    enriched["url"] = direct_url
    enriched["link_status"] = "direct"
    enriched["source"] = normalize_source_name(
        enriched.get("source", ""),
        enriched.get("source_url", ""),
        direct_url,
    )

    if article_response is None or "html" not in article_response.headers.get("content-type", "").lower():
        return enriched

    try:
        soup = BeautifulSoup(article_response.text[:1_500_000], "html.parser")
    except Exception:
        return enriched

    canonical_node = soup.find("link", attrs={"rel": "canonical"})
    canonical = ""
    if canonical_node:
        canonical = clean_url(urljoin(direct_url, canonical_node.get("href", "")))

    if canonical and is_external_article_url(canonical) and same_site(canonical, direct_url):
        enriched["direct_url"] = canonical
        enriched["url"] = canonical
        direct_url = canonical

    description = prepare_description(
        meta_content(soup, prop="og:description")
        or meta_content(soup, name="description")
        or meta_content(soup, name="twitter:description")
        or json_ld_description(soup)
        or first_article_paragraph(soup),
        enriched.get("title", ""),
    )

    image_raw = (
        meta_content(soup, prop="og:image")
        or meta_content(soup, name="twitter:image")
    )
    image_url = clean_url(urljoin(direct_url, image_raw)) if image_raw else ""
    image_width = meta_int(soup, "og:image:width")
    image_height = meta_int(soup, "og:image:height")

    if description:
        enriched["meta_description"] = description
    else:
        enriched.pop("meta_description", None)

    if is_valid_image_url(image_url, image_width, image_height):
        enriched["image_url"] = image_url
        enriched["image_source_url"] = direct_url
    else:
        enriched.pop("image_url", None)
        enriched.pop("image_source_url", None)

    return enriched


def enrich_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []

    selected = sorted(items, key=editorial_score, reverse=True)[:ENRICH_LIMIT]
    selected_ids = {id(x) for x in selected}
    untouched = [x for x in items if id(x) not in selected_ids]
    enriched_rows: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as executor:
        future_map = {executor.submit(enrich_one, item): item for item in selected}
        for future in as_completed(future_map):
            original = future_map[future]
            try:
                enriched_rows.append(future.result())
            except Exception:
                enriched_rows.append(original)

    return enriched_rows + untouched


SIMILARITY_FILLER_WORDS = [
    "最新", "重磅", "正式", "宣布", "发布", "报道", "消息", "回应", "市场",
    "中国", "品牌", "公司", "集团", "本周", "为何", "背后", "观察", "分析",
]


def similarity_text(title: str) -> str:
    text = norm_key(title)
    for word in SIMILARITY_FILLER_WORDS:
        text = text.replace(norm_key(word), "")
    return text


def bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def title_similarity(a: str, b: str) -> float:
    a_norm = similarity_text(a)
    b_norm = similarity_text(b)

    if not a_norm or not b_norm:
        return 0.0
    if a_norm in b_norm or b_norm in a_norm:
        return min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm))

    seq = SequenceMatcher(None, a_norm, b_norm).ratio()
    a_bigrams = bigrams(a_norm)
    b_bigrams = bigrams(b_norm)
    union = a_bigrams | b_bigrams
    jac = len(a_bigrams & b_bigrams) / len(union) if union else 0.0
    return max(seq, jac)


def same_event(a: dict[str, Any], b: dict[str, Any]) -> bool:
    similarity = title_similarity(a.get("title", ""), b.get("title", ""))
    brands_a = set(a.get("brands", []))
    brands_b = set(b.get("brands", []))
    keywords_a = set(a.get("keywords", []))
    keywords_b = set(b.get("keywords", []))
    family_a = a.get("event_family") or detect_event_family(a.get("title", ""))
    family_b = b.get("event_family") or detect_event_family(b.get("title", ""))
    period_a = a.get("reporting_period") or detect_reporting_period(
        a.get("title", ""), a.get("published_at", "")
    )
    period_b = b.get("reporting_period") or detect_reporting_period(
        b.get("title", ""), b.get("published_at", "")
    )

    if (
        brands_a & brands_b
        and family_a == family_b == "financial_results"
        and period_a
        and period_a == period_b
    ):
        return True

    if similarity >= 0.72:
        return True
    if brands_a & brands_b and similarity >= 0.54:
        return True
    if (
        brands_a & brands_b
        and family_a == family_b
        and family_a in {"capital_strategy", "management", "endorsement_partnership", "store_channel"}
        and similarity >= 0.42
    ):
        return True
    if len(keywords_a & keywords_b) >= 2 and similarity >= 0.58:
        return True
    return False


def representative_rank(item: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    tier, official, _ = source_profile(item.get("source", ""), item.get("source_url", ""), item.get("direct_url", ""))
    tier_rank = {"official": 5, "tier_1": 4, "tier_2": 3, "tier_3": 2, "low": 1}.get(tier, 0)
    title = item.get("title", "")
    headline_quality = 0 if has_any(title, CLICKBAIT_WORDS) or "?" in title or "？" in title else 1
    return (
        1 if official else 0,
        tier_rank,
        headline_quality,
        1 if item.get("meta_description") else 0,
        1 if item.get("direct_url") else 0,
        int(item.get("editorial_score", 0)),
    )


def build_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []

    for item in sorted(items, key=lambda x: x.get("editorial_score", 0), reverse=True):
        matched_cluster = None

        for cluster in clusters:
            if any(same_event(item, existing) for existing in cluster[:5]):
                matched_cluster = cluster
                break

        if matched_cluster is None:
            clusters.append([item])
        else:
            matched_cluster.append(item)

    events = []

    for cluster in clusters:
        representative = max(cluster, key=representative_rank)
        sources = list(dict.fromkeys([x.get("source", "") for x in cluster if x.get("source")]))
        brands = list(dict.fromkeys([b for x in cluster for b in x.get("brands", [])]))
        keywords = list(dict.fromkeys([k for x in cluster for k in x.get("keywords", [])]))
        published = [parse_published_at(x.get("published_at")) for x in cluster]
        published = [x for x in published if x]

        has_negative = any(has_any(x.get("title", ""), CONFLICT_NEGATIVE_WORDS) for x in cluster)
        has_positive = any(
            has_any(x.get("title", ""), CONFLICT_POSITIVE_WORDS)
            and not has_any(x.get("title", ""), CONFLICT_NEGATIVE_WORDS)
            for x in cluster
        )

        event_seed = event_signature(representative)
        event_id = stable_id("evt", event_seed)
        source_count = len(sources)
        official_count = sum(1 for x in cluster if x.get("is_official"))
        direct_source_count = sum(1 for x in cluster if x.get("direct_url"))
        family = representative.get("event_family") or detect_event_family(representative.get("title", ""))
        period = representative.get("reporting_period") or detect_reporting_period(
            representative.get("title", ""), representative.get("published_at", "")
        )

        summaries = []
        for row in sorted(cluster, key=representative_rank, reverse=True):
            summary = prepare_description(row.get("meta_description"), row.get("title", ""))
            if summary and summary not in summaries:
                summaries.append(summary)

        evidence = []
        used_evidence = set()
        for row in sorted(cluster, key=representative_rank, reverse=True):
            evidence_key = f"{row.get('source')}|{row.get('url')}"
            if evidence_key in used_evidence:
                continue
            used_evidence.add(evidence_key)
            evidence.append({
                "item_id": row.get("id", ""),
                "title": row.get("title", ""),
                "source": row.get("source", ""),
                "source_tier": row.get("source_tier", ""),
                "is_official": bool(row.get("is_official")),
                "url": row.get("url", ""),
                "direct_url": row.get("direct_url", ""),
                "link_status": row.get("link_status", ""),
                "published_at": row.get("published_at", ""),
                "summary": prepare_description(row.get("meta_description"), row.get("title", "")),
            })

        if official_count:
            verification = "official_source"
        elif source_count >= 2:
            verification = "multi_source"
        else:
            verification = "single_source"

        event_score = min(
            100,
            max(int(x.get("editorial_score", 0)) for x in cluster)
            + min(max(source_count - 1, 0) * 4, 12)
            + (5 if official_count else 0),
        )

        events.append({
            "event_id": event_id,
            "fingerprint": event_seed,
            "representative_id": representative.get("id", ""),
            "title": representative.get("title", ""),
            "summary": summaries[0] if summaries else "",
            "category": representative.get("category", ""),
            "event_family": family,
            "reporting_period": period,
            "brands": brands,
            "keywords": keywords[:16],
            "source": representative.get("source", ""),
            "url": representative.get("url", ""),
            "direct_url": representative.get("direct_url", ""),
            "link_status": representative.get("link_status", ""),
            "published_at": representative.get("published_at", ""),
            "first_published_at": min(published).isoformat(timespec="minutes") if published else "",
            "last_published_at": max(published).isoformat(timespec="minutes") if published else "",
            "editorial_score": event_score,
            "mention_count": len(cluster),
            "source_count": source_count,
            "direct_source_count": direct_source_count,
            "sources": sources,
            "evidence": evidence,
            "original_titles": list(dict.fromkeys(x.get("title", "") for x in cluster if x.get("title"))),
            "item_ids": [x.get("id", "") for x in cluster],
            "verification": verification,
            "conflict_flag": bool(has_negative and has_positive),
            "conflict_titles": [x.get("title", "") for x in cluster] if has_negative and has_positive else [],
            "status": "new",
            "first_seen": REPORT_START_DATE.isoformat(),
            "last_seen": REPORT_END_DATE.isoformat(),
        })

    return sorted(events, key=lambda x: (x.get("editorial_score", 0), x.get("source_count", 0)), reverse=True)


# =========================================================
# 7. 历史跟踪与矛盾提醒
# =========================================================

def load_prior_events() -> list[dict[str, Any]]:
    rows = []
    cutoff = REPORT_START_DATE - timedelta(days=HISTORY_DAYS)

    for path in sorted(ARCHIVE_DIR.glob("weekly_sources_*.json"))[-16:]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        window = data.get("report_window", {}) if isinstance(data, dict) else {}
        try:
            prior_end = datetime.strptime(window.get("end_date", ""), "%Y-%m-%d").date()
        except Exception:
            continue

        if prior_end < cutoff or prior_end >= REPORT_START_DATE:
            continue

        for event in safe_list(data.get("events")):
            if isinstance(event, dict):
                rows.append(event)

    return rows


def apply_history_status(events: list[dict[str, Any]], prior_events: list[dict[str, Any]]) -> None:
    for event in events:
        current_brands = set(event.get("brands", []))
        best_match = None
        best_similarity = 0.0

        for prior in prior_events:
            prior_brands = set(prior.get("brands", []))
            if current_brands and prior_brands and not (current_brands & prior_brands):
                continue

            similarity = title_similarity(event.get("title", ""), prior.get("title", ""))
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = prior

        if best_match and best_similarity >= 0.58:
            event["status"] = "follow_up"
            event["previous_event_id"] = best_match.get("event_id", "")
            event["first_seen"] = best_match.get("first_seen") or best_match.get("last_seen") or event["first_seen"]
        else:
            event["status"] = "new"


def detect_cross_event_conflicts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts = []

    for i, left in enumerate(events):
        left_title = left.get("title", "")
        left_negative = has_any(left_title, CONFLICT_NEGATIVE_WORDS)
        left_positive = has_any(left_title, CONFLICT_POSITIVE_WORDS) and not left_negative

        if not (left_negative or left_positive):
            continue

        for right in events[i + 1:]:
            right_title = right.get("title", "")
            right_negative = has_any(right_title, CONFLICT_NEGATIVE_WORDS)
            right_positive = has_any(right_title, CONFLICT_POSITIVE_WORDS) and not right_negative

            if not ((left_negative and right_positive) or (left_positive and right_negative)):
                continue
            if not (set(left.get("brands", [])) & set(right.get("brands", []))):
                continue
            if not (has_any(left_title, CONFLICT_ACTION_WORDS) and has_any(right_title, CONFLICT_ACTION_WORDS)):
                continue

            similarity = title_similarity(left_title, right_title)
            if similarity < 0.30:
                continue

            left["conflict_flag"] = True
            right["conflict_flag"] = True

            conflicts.append({
                "conflict_id": stable_id("conf", left["event_id"] + right["event_id"]),
                "event_ids": [left["event_id"], right["event_id"]],
                "titles": [left_title, right_title],
                "reason": "同一品牌相关事件同时出现确认与否认表述，进入人工/官方核验队列。",
            })

    return conflicts


# =========================================================
# 8. 主程序
# =========================================================

def main() -> None:
    queries, active_campaigns = build_queries()
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    })

    raw_rows: list[dict[str, Any]] = []
    rejected = Counter()
    fetch_errors = []

    print(
        f"Weekly source collector | {REPORT_START_DATE} ~ {REPORT_END_DATE} "
        f"| timezone={TIMEZONE_NAME} | queries={len(queries)}"
    )
    print("Active campaigns:", "、".join(active_campaigns) if active_campaigns else "无")

    for index, query_row in enumerate(queries, start=1):
        rows, error = fetch_rss(query_row, session)

        if error:
            fetch_errors.append({"query": query_row["query"], "error": error})
            print(f"[{index}/{len(queries)}] ERROR {query_row['query']}: {error}")
        else:
            print(f"[{index}/{len(queries)}] {query_row['group']} | {query_row['query']} -> {len(rows)}")

        for row in rows:
            published_at = parse_published_at(row.get("published_at"))
            reason = reject_reason(
                row.get("title", ""),
                row.get("source", ""),
                published_at,
                row.get("query_groups", []),
            )

            if reason:
                rejected[reason] += 1
                continue

            raw_rows.append(row)

        time.sleep(QUERY_INTERVAL)

    print(f"RSS accepted before dedupe: {len(raw_rows)}")

    items = merge_exact_duplicates(raw_rows)
    print(f"After exact-title dedupe: {len(items)}")

    if not items:
        raise SystemExit("No valid weekly sources found; existing output was not overwritten.")

    items = enrich_items(items)

    prepared = []
    for item in items:
        item = dict(item)
        item["source"] = normalize_source_name(
            item.get("source", ""),
            item.get("source_url", ""),
            item.get("direct_url", ""),
        )
        item["brands"] = detect_brands(item.get("title", ""))
        item["keywords"] = detect_keywords(item.get("title", ""))
        item["category"] = detect_category(item.get("title", ""), item.get("query_groups", []))
        item["event_family"] = detect_event_family(item.get("title", ""))
        item["reporting_period"] = detect_reporting_period(
            item.get("title", ""), item.get("published_at", "")
        )

        tier, official, _ = source_profile(
            item.get("source", ""),
            item.get("source_url", ""),
            item.get("direct_url", ""),
        )
        item["source_tier"] = tier
        item["is_official"] = official
        item["editorial_score"] = editorial_score(item)
        exclusion = core_exclusion_reason(item)
        item["core_eligible"] = not exclusion
        item["core_exclusion_reason"] = exclusion
        item["id"] = stable_id(
            "src",
            f"{norm_key(item.get('title'))}|{item.get('published_date')}|{item.get('source')}",
        )

        description = prepare_description(item.get("meta_description"), item.get("title", ""))
        if description:
            item["meta_description"] = description
        else:
            item.pop("meta_description", None)

        if not is_valid_image_url(item.get("image_url", "")):
            item.pop("image_url", None)
            item.pop("image_source_url", None)

        # RSS description通常只是Google News列表HTML；没有抓到正文摘要时不冒充摘要。
        item.pop("rss_description", None)
        prepared.append(item)

    items = sorted(prepared, key=lambda x: x.get("editorial_score", 0), reverse=True)[:MAX_ITEMS]
    core_items = [x for x in items if x.get("core_eligible")]
    events = build_events(core_items)

    prior_events = load_prior_events()
    apply_history_status(events, prior_events)
    conflict_groups = detect_cross_event_conflicts(events)

    category_counts = Counter(x.get("category", "行业动态") for x in items)
    source_tier_counts = Counter(x.get("source_tier", "unknown") for x in items)
    status_counts = Counter(x.get("status", "new") for x in events)

    payload = {
        "schema_version": "2.1",
        "generated_at": GENERATED_AT.isoformat(timespec="minutes"),
        "report_window": {
            "start_date": REPORT_START_DATE.isoformat(),
            "end_date": REPORT_END_DATE.isoformat(),
            "timezone": TIMEZONE_NAME,
            "complete_calendar_days": 7,
        },
        "methodology": {
            "discovery": "Google News RSS多主题检索",
            "hard_date_filter": True,
            "date_basis": "报道发布时间，统一换算为Asia/Shanghai后过滤",
            "seasonal_queries": active_campaigns,
            "deduplication": "标准化标题去重 + 品牌/事件类型/财务周期聚类 + 标题相似度复核",
            "summary_policy": "仅保留原文页有效描述；Google News固定英文说明不作为摘要",
            "link_policy": "优先解析原文链接，无法安全解析时保留Google News链接并标记fallback",
            "core_event_policy": "低质量来源、本地宣传活动和编辑分不足的内容保留在线索池但不进入核心事件",
            "editorial_score_note": "仅代表周报编辑优先级，不代表销量、搜索量或市场热度",
            "product_note": "本文件只发现产品相关新闻，不把新闻篇数当作商品销量",
        },
        "stats": {
            "query_count": len(queries),
            "fetch_error_count": len(fetch_errors),
            "accepted_item_count": len(items),
            "core_eligible_item_count": len(core_items),
            "event_count": len(events),
            "new_event_count": status_counts.get("new", 0),
            "follow_up_event_count": status_counts.get("follow_up", 0),
            "conflict_count": len(conflict_groups),
            "direct_url_count": sum(1 for x in items if x.get("direct_url")),
            "official_source_count": sum(1 for x in items if x.get("is_official")),
            "multi_source_event_count": sum(1 for x in events if x.get("source_count", 0) >= 2),
            "rejected": dict(rejected),
            "categories": dict(category_counts),
            "source_tiers": dict(source_tier_counts),
            "core_exclusions": dict(Counter(
                x.get("core_exclusion_reason", "")
                for x in items
                if x.get("core_exclusion_reason")
            )),
        },
        "queries": queries,
        "fetch_errors": fetch_errors[:30],
        "conflict_groups": conflict_groups,
        "events": events,
        "items": items,
    }

    archive_file = ARCHIVE_DIR / (
        f"weekly_sources_{REPORT_START_DATE.isoformat()}_{REPORT_END_DATE.isoformat()}.json"
    )

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(OUTPUT_FILE)
    archive_file.write_text(content, encoding="utf-8")

    print(f"weekly sources saved: {OUTPUT_FILE}")
    print(f"weekly sources archived: {archive_file}")
    print(f"items: {len(items)} | events: {len(events)} | conflicts: {len(conflict_groups)}")
    print(f"new: {status_counts.get('new', 0)} | follow_up: {status_counts.get('follow_up', 0)}")
    print(f"direct urls: {sum(1 for x in items if x.get('direct_url'))}")

    print("\nTop 15 candidate events:")
    for index, event in enumerate(events[:15], start=1):
        print(
            f"{index}. [{event['editorial_score']}] [{event['status']}] "
            f"[{event['verification']}] {event['title']} | {event['source']}"
        )


if __name__ == "__main__":
    main()
