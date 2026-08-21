from __future__ import annotations

import hashlib
import html as html_lib
import json
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
# 0. 文件与运行配置
# =========================================================

TIMEZONE_NAME = "Asia/Shanghai"
LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

WEEKLY_DIR = Path("output/weekly")
ARCHIVE_DIR = WEEKLY_DIR / "archive"
SOURCE_FILE = WEEKLY_DIR / "weekly_sources.json"
OUTPUT_FILE = WEEKLY_DIR / "weekly_products.json"

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

RSS_PER_QUERY = 10
MAX_QUERIES = 90
MAX_SOURCE_ITEMS = 160
ENRICH_LIMIT = 100
ENRICH_WORKERS = 8
REQUEST_TIMEOUT = 18
QUERY_INTERVAL = 0.16
HISTORY_DAYS = 60

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 TrendRadarProductRadar/2.0"
)


# =========================================================
# 1. 基础工具
# =========================================================

def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"load json error: {path} {repr(exc)}")
        return default


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


def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def is_external_url(url: str) -> bool:
    host = host_of(url)
    if not host:
        return False

    blocked = [
        "news.google.com",
        "google.com",
        "consent.google.com",
        "accounts.google.com",
    ]
    return not any(host == x or host.endswith("." + x) for x in blocked)


def norm_key(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|·™®]+", "", text)
    return text[:120]


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}_{digest}"


def has_any(text: str, words: list[str]) -> bool:
    lower = clean_text(text).lower()
    return any(word.lower() in lower for word in words)


def parse_datetime(value: Any) -> datetime | None:
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


def short_text(value: Any, length: int = 220) -> str:
    text = clean_text(value)
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "..."


# =========================================================
# 2. 读取第一阶段周度资讯池并统一统计周期
# =========================================================

weekly_sources = load_json(SOURCE_FILE, {})
source_window = weekly_sources.get("report_window", {}) if isinstance(weekly_sources, dict) else {}


def resolve_report_window() -> tuple[date, date]:
    try:
        start_date = datetime.strptime(source_window.get("start_date", ""), "%Y-%m-%d").date()
        end_date = datetime.strptime(source_window.get("end_date", ""), "%Y-%m-%d").date()
        return start_date, end_date
    except Exception:
        end_date = datetime.now(LOCAL_TZ).date() - timedelta(days=1)
        return end_date - timedelta(days=6), end_date


REPORT_START_DATE, REPORT_END_DATE = resolve_report_window()
WINDOW_START = datetime.combine(REPORT_START_DATE, dt_time.min, tzinfo=LOCAL_TZ)
WINDOW_END = datetime.combine(REPORT_END_DATE, dt_time.max, tzinfo=LOCAL_TZ)
GENERATED_AT = datetime.now(LOCAL_TZ)


def in_report_window(value: Any) -> bool:
    dt = parse_datetime(value)
    return bool(dt and WINDOW_START <= dt <= WINDOW_END)


active_campaigns = safe_list(
    weekly_sources.get("methodology", {}).get("seasonal_queries", [])
    if isinstance(weekly_sources, dict)
    else []
)


# =========================================================
# 3. 品牌、品类与产品事实词库
# 词库只用于识别真实文本，不会自动生成产品
# =========================================================

BRAND_VARIANTS = {
    "361儿童": ["361儿童", "361°儿童", "361度儿童", "361 Kids", "361°KIDS"],
    "361°": ["361°", "361度"],
    "安踏儿童": ["安踏儿童", "ANTA KIDS"],
    "安踏": ["安踏", "ANTA"],
    "FILA KIDS": ["FILA KIDS", "FILA Kids"],
    "FILA": ["FILA"],
    "李宁YOUNG": ["李宁YOUNG", "LI-NING YOUNG"],
    "李宁": ["李宁", "LI-NING", "Li-Ning"],
    "特步儿童": ["特步儿童", "XTEP KIDS"],
    "特步": ["特步", "XTEP"],
    "Nike": ["Nike", "耐克"],
    "Jordan": ["Jordan", "乔丹品牌"],
    "Adidas": ["Adidas", "adidas", "阿迪达斯"],
    "Puma": ["Puma", "PUMA", "彪马"],
    "New Balance": ["New Balance", "新百伦"],
    "ASICS": ["ASICS", "Asics", "亚瑟士"],
    "Skechers": ["Skechers", "斯凯奇"],
    "Under Armour": ["Under Armour", "安德玛"],
    "On昂跑": ["On昂跑", "On Running", "昂跑"],
    "HOKA": ["HOKA", "Hoka"],
    "Salomon": ["Salomon", "萨洛蒙"],
    "lululemon": ["lululemon", "Lululemon", "露露乐蒙"],
    "Alo Yoga": ["Alo Yoga", "ALO", "Alo"],
    "始祖鸟": ["始祖鸟", "Arc'teryx", "ARCTERYX"],
    "The North Face": ["The North Face", "北面"],
    "迪桑特": ["迪桑特", "DESCENTE", "Descente"],
    "凯乐石": ["凯乐石", "KAILAS"],
    "可隆": ["可隆", "KOLON SPORT"],
    "迪卡侬": ["迪卡侬", "Decathlon"],
    "巴拉巴拉": ["巴拉巴拉", "Balabala"],
    "moodytiger": ["moodytiger", "modytiger"],
}

# 长名称先判断，避免“安踏儿童”被先识别成“安踏”。
BRAND_SEARCH_ROWS = sorted(
    [(brand, variant) for brand, variants in BRAND_VARIANTS.items() for variant in variants],
    key=lambda row: len(row[1]),
    reverse=True,
)

PRODUCT_NOUNS = [
    "儿童跑鞋", "青少年跑鞋", "儿童篮球鞋", "篮球鞋", "足球鞋", "训练鞋",
    "竞速跑鞋", "缓震跑鞋", "越野跑鞋", "跑鞋", "童鞋", "运动鞋",
    "户外鞋", "徒步鞋", "溯溪鞋", "恢复鞋", "恢复拖鞋", "运动凉鞋",
    "凉鞋", "拖鞋", "防晒衣", "防晒服", "凉感T恤", "速干T恤",
    "运动T恤", "冲锋衣", "软壳外套", "羽绒服", "运动外套", "运动服",
    "运动套装", "瑜伽服", "瑜伽裤", "运动内衣", "背包", "运动装备",
]

PRODUCT_ACTION_WORDS = [
    "新品", "新款", "发布", "推出", "上新", "首发", "发售", "开售", "上市",
    "亮相", "登场", "系列", "联名", "配色", "升级", "迭代",
]

PRODUCT_MODEL_FAMILIES = [
    "Pegasus", "Vomero", "Air Max", "Metcon", "Alphafly", "Vaporfly",
    "Adizero", "Ultraboost", "Supernova", "Samba", "Gazelle",
    "Cloudsurfer", "Cloudmonster", "Cloudboom", "Cloud 6", "Cloudflow",
    "Clifton", "Bondi", "Speedgoat", "Mach X", "Cielo X1",
    "XT-6", "ACS Pro", "Gel-Kayano", "GEL-NIMBUS", "Novablast",
    "Fresh Foam", "FuelCell", "Deviate Nitro", "ForeverRun",
    "飞燃", "超轻", "赤兔", "绝影", "烈骏", "C202", "氮科技",
    "冠军跑鞋", "马赫", "竞速160", "飞飚", "咻", "骇浪", "Kobe",
]

TECHNOLOGY_WORDS = [
    "ZoomX", "Air Zoom", "ReactX", "Flyknit", "Dri-FIT", "Storm-FIT",
    "Lightstrike Pro", "BOOST", "Primeknit", "ENERGYRODS",
    "CloudTec", "CloudTec Phase", "Helion", "Speedboard",
    "PEBA", "EVA", "TPU", "碳板", "全掌碳板", "超临界发泡", "氮科技",
    "缓震", "回弹", "足弓支撑", "防滑大底", "耐磨大底", "GORE-TEX",
    "Vibram", "BOA", "防晒", "UPF50+", "凉感", "速干", "防水", "防风",
]

MATERIAL_WORDS = [
    "网布", "工程网布", "针织", "Flyknit", "Primeknit", "EVA", "PEBA", "TPU",
    "橡胶大底", "碳纤维", "再生聚酯", "锦纶", "氨纶", "GORE-TEX", "Vibram",
]

SCENARIO_RULES = {
    "跑步": ["跑步", "跑鞋", "慢跑", "竞速", "马拉松"],
    "篮球": ["篮球", "篮球鞋", "球场"],
    "足球": ["足球", "足球鞋"],
    "校园运动": ["儿童", "青少年", "校园", "体育课", "开学", "跳绳"],
    "户外徒步": ["户外", "徒步", "登山", "露营", "山系"],
    "越野跑": ["越野", "越野跑"],
    "训练健身": ["训练", "健身", "训练鞋"],
    "瑜伽": ["瑜伽", "瑜伽服", "瑜伽裤"],
    "城市通勤": ["通勤", "城市", "日常", "休闲"],
    "亲子出行": ["亲子", "家庭", "出行"],
}

CATEGORY_RULES = {
    "儿童运动鞋": ["儿童跑鞋", "儿童篮球鞋", "童鞋", "青少年跑鞋", "成长鞋"],
    "跑鞋": ["竞速跑鞋", "缓震跑鞋", "越野跑鞋", "跑鞋", "Pegasus", "Vomero", "Adizero", "Cloud", "Clifton", "Bondi"],
    "篮球鞋": ["篮球鞋"],
    "足球鞋": ["足球鞋"],
    "训练鞋": ["训练鞋"],
    "户外鞋": ["户外鞋", "徒步鞋", "溯溪鞋", "越野跑鞋", "XT-6"],
    "夏季鞋类": ["恢复鞋", "恢复拖鞋", "运动凉鞋", "凉鞋", "拖鞋"],
    "夏季功能服饰": ["防晒衣", "防晒服", "凉感", "速干"],
    "户外服饰": ["冲锋衣", "软壳", "羽绒服", "户外外套"],
    "运动服饰": ["运动T恤", "运动外套", "运动服", "运动套装"],
    "瑜伽与训练服": ["瑜伽服", "瑜伽裤", "运动内衣"],
    "运动配件": ["背包", "帽", "运动装备"],
}

AUDIENCE_RULES = {
    "儿童/青少年": ["儿童", "青少年", "大童", "中大童", "童鞋", "童装", "Kids", "KIDS", "YOUNG"],
    "女性": ["女性", "女子", "女款", "瑜伽", "运动内衣"],
    "男性": ["男性", "男子", "男款"],
}

HARD_BAD_WORDS = [
    "财报", "营收", "净利润", "毛利率", "市值", "股价", "涨停", "跌停", "目标价",
    "比分", "赛程", "转会", "球队", "主教练", "伤病", "汽车", "手机", "电视",
    "优惠券", "券后", "凑单", "直降", "满减", "省钱快报", "怎么买", "怎么选",
    "排行榜", "推荐购买", "测评", "招商加盟", "招聘",
]

OFFICIAL_DOMAINS = [
    "nike.com", "about.nike.com", "adidas.com", "adidas-group.com",
    "anta.com", "anta.com.cn", "lining.com", "xtep.com.cn", "361sport.com",
    "puma.com", "newbalance.com", "asics.com", "skechers.com", "underarmour.com",
    "on.com", "hoka.com", "salomon.com", "lululemon.com", "aloyoga.com",
    "arcteryx.com", "thenorthface.com", "descente.com", "kailas.com.cn",
    "decathlon.com", "balabala.com",
]

OFFICIAL_SOURCE_WORDS = [
    "官方", "官网", "Newsroom", "品牌官网", "安踏集团", "李宁公司", "特步集团", "361度集团",
]

TRUSTED_MEDIA_WORDS = [
    "第一财经", "界面新闻", "Jiemian", "新京报", "澎湃", "36氪", "亿邦动力",
    "联商网", "赢商网", "CBNData", "华丽志", "时尚商业", "美通社", "中国纺织报",
]

TIER_1_WORDS = [
    "国家统计局", "商务部", "国家体育总局", "新华网", "人民网", "央视",
    "新华社", "中国政府网",
]

TIER_2_WORDS = TRUSTED_MEDIA_WORDS + [
    "中国妇女网", "中国日报", "经济观察报", "南方都市报", "北京商报",
    "证券时报", "财联社", "虎嗅", "钛媒体", "品牌星球", "Morketing",
]

LOW_SOURCE_WORDS = [
    "搜狐号", "百家号", "网易号", "企鹅号", "财富号", "自媒体", "省钱快报",
    "Dealmoon", "北美省钱快报", "Traders Union", "投資慧眼", "推荐榜",
]

LOW_SOURCE_DOMAINS = [
    "dealmoon.com", "dealmoon.ca", "tradersunion.com", "sohu.com/a/",
]

SOURCE_NAME_ALIASES = {
    "thepaper.cn": "澎湃新闻",
    "澎湃": "澎湃新闻",
    "jiemian.com": "界面新闻",
    "Jiemian": "界面新闻",
    "yicai.com": "第一财经",
    "ebrun.com": "亿邦动力",
    "womenofchina.com": "中国妇女网",
    "stats.gov.cn": "国家统计局",
    "mofcom.gov.cn": "商务部",
    "sport.gov.cn": "国家体育总局",
    "xinhuanet.com": "新华网",
    "people.com.cn": "人民网",
    "shyp.gov.cn": "上海杨浦",
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
    ("womenofchina.com", "中国妇女网"),
    ("shyp.gov.cn", "上海杨浦"),
    ("dealmoon.com", "北美省钱快报"),
    ("dealmoon.ca", "北美省钱快报"),
]

GENERIC_PRODUCT_PHRASES = [
    "核心产品", "代表产品", "主推产品", "明星产品", "运动品牌新品", "品牌新品",
    "全线产品", "新品系列", "新款系列", "核心产品瑜伽服", "瑜伽服核心产品",
]

INVALID_IMAGE_HOSTS = [
    "google.com", "googleusercontent.com", "gstatic.com", "ggpht.com",
    "googleapis.com", "news.google.com",
]

INVALID_IMAGE_TOKENS = [
    "logo", "icon", "favicon", "avatar", "default", "placeholder", "sprite",
    "loading", "blank", "transparent", "brandmark", "site-logo", "news-logo",
]


# =========================================================
# 4. 查询构建：只启用当前周期对应的季节节点
# =========================================================

QUERY_BRANDS = [
    "361儿童", "安踏儿童", "安踏", "李宁YOUNG", "李宁", "特步儿童", "特步",
    "Nike", "Adidas", "Puma", "New Balance", "ASICS", "On昂跑", "HOKA",
    "Salomon", "lululemon", "Alo Yoga", "始祖鸟", "The North Face", "迪桑特",
    "凯乐石", "迪卡侬", "巴拉巴拉",
]

BASE_PRODUCT_QUERIES = [
    "儿童运动鞋 新品 发布",
    "青少年跑鞋 新品",
    "儿童篮球鞋 新品",
    "校园运动鞋 上新",
    "跑鞋 新品 科技 发布",
    "篮球鞋 新品 发布",
    "运动品牌 防晒衣 新品",
    "户外鞋服 新品 发布",
    "恢复拖鞋 运动品牌 新品",
    "运动凉鞋 新品",
    "运动服饰 功能面料 新品",
]

CAMPAIGN_PRODUCT_QUERIES = {
    "三八节": ["三八节 女性运动 新品"],
    "六一": ["六一 儿童运动鞋 新品", "儿童节 童装 新品"],
    "618": ["618 运动鞋服 新品", "618 儿童运动鞋 新品"],
    "暑期": ["暑期 儿童运动 新品", "夏季 防晒衣 运动品牌", "夏季 运动凉鞋 新品"],
    "开学季": ["开学季 儿童运动鞋 新品", "开学季 青少年训练鞋"],
    "99大促": ["99大促 运动鞋服 新品"],
    "国庆出行": ["国庆 户外鞋服 新品", "亲子出行 运动鞋"],
    "双11": ["双11 运动鞋服 新品", "双11 儿童运动鞋"],
    "双12": ["双12 运动鞋服 新品"],
}

OFFICIAL_SITE_QUERIES = [
    "site:about.nike.com 鞋 发布",
    "site:news.adidas.com 鞋 发布",
    "site:anta.com 新品 跑鞋",
    "site:lining.com 新品 跑鞋",
    "site:361sport.com 新品",
    "site:on.com 新品 跑鞋",
    "site:hoka.com 新品 跑鞋",
    "site:salomon.com 新品",
    "site:newbalance.com 新品 鞋",
    "site:asics.com 新品 跑鞋",
    "site:thenorthface.com 新品 鞋服",
    "site:lululemon.com 新品",
    "site:anta.com 儿童 新品",
    "site:361sport.com 儿童 新品",
]


def build_queries() -> list[dict[str, str]]:
    rows = [{"group": "product", "query": query} for query in BASE_PRODUCT_QUERIES]

    for brand in QUERY_BRANDS:
        rows.append({
            "group": "brand_product",
            "query": f'"{brand}" (新品 OR 新款 OR 发布 OR 首发 OR 上新 OR 跑鞋 OR 篮球鞋 OR 童鞋 OR 户外鞋)',
        })

    for query in OFFICIAL_SITE_QUERIES:
        rows.append({"group": "official_site", "query": query})

    for campaign in active_campaigns:
        for query in CAMPAIGN_PRODUCT_QUERIES.get(clean_text(campaign), []):
            rows.append({"group": "seasonal", "query": query})

    output = []
    used = set()

    for row in rows:
        key = row["query"].lower().strip()
        if not key or key in used:
            continue
        used.add(key)
        output.append(row)

    return output[:MAX_QUERIES]


# =========================================================
# 5. RSS发现
# =========================================================

def google_news_url(query: str) -> str:
    search_after = REPORT_START_DATE - timedelta(days=1)
    search_before = REPORT_END_DATE + timedelta(days=1)
    full_query = f"{query} after:{search_after.isoformat()} before:{search_before.isoformat()}"
    return (
        "https://news.google.com/rss/search?q="
        + quote(full_query)
        + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )


def normalize_rss_title(title: str, source: str) -> str:
    title = clean_text(title)
    source = clean_text(source)

    if source:
        for separator in [" - ", " – ", " — ", " | "]:
            suffix = separator + source
            if title.lower().endswith(suffix.lower()):
                title = title[:-len(suffix)].strip()
                break

    return title


def fetch_rss(query_row: dict[str, str], session: requests.Session) -> tuple[list[dict[str, Any]], str]:
    try:
        response = session.get(google_news_url(query_row["query"]), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        return [], repr(exc)

    rows = []

    for node in root.findall(".//item")[:RSS_PER_QUERY]:
        source_node = node.find("source")
        raw_source = clean_text(source_node.text if source_node is not None else "")
        source_homepage = clean_url(source_node.attrib.get("url", "") if source_node is not None else "")
        source = normalize_source_name(raw_source, source_homepage)
        pub_dt = parse_datetime(node.findtext("pubDate"))
        google_url = clean_url(node.findtext("link"))

        rows.append({
            "headline": normalize_rss_title(node.findtext("title") or "", raw_source),
            "source": source,
            "source_homepage": source_homepage,
            "google_news_url": google_url,
            "article_url": "",
            "direct_url": "",
            "link_status": "google_news_fallback" if google_url else "missing",
            "published_at": pub_dt.isoformat(timespec="minutes") if pub_dt else "",
            "published_date": pub_dt.date().isoformat() if pub_dt else "",
            "query_groups": [query_row["group"]],
            "discovered_by": [query_row["query"]],
            "source_tier": "",
            "is_official": False,
            "core_eligible": True,
        })

    return rows, ""


def rows_from_weekly_sources() -> list[dict[str, Any]]:
    rows = []

    for item in safe_list(weekly_sources.get("items", [])):
        if not isinstance(item, dict):
            continue

        title = clean_text(item.get("title"))
        if not title:
            continue
        if not has_any(title, PRODUCT_NOUNS + PRODUCT_ACTION_WORDS + PRODUCT_MODEL_FAMILIES):
            continue

        source_homepage = clean_url(item.get("source_url"))
        direct_url = direct_article_url(item)
        source = normalize_source_name(item.get("source"), source_homepage, direct_url)
        image_url = clean_url(item.get("image_url"))

        rows.append({
            "headline": title,
            "source": source,
            "source_homepage": source_homepage,
            "google_news_url": clean_url(item.get("google_news_url")),
            "article_url": direct_url,
            "direct_url": direct_url,
            "link_status": clean_text(item.get("link_status")) or ("direct" if direct_url else "google_news_fallback"),
            "published_at": clean_text(item.get("published_at")),
            "published_date": clean_text(item.get("published_date")),
            "query_groups": list(dict.fromkeys(safe_list(item.get("query_groups")) + ["weekly_source_pool"])),
            "discovered_by": safe_list(item.get("discovered_by")),
            "meta_description": clean_text(item.get("meta_description")),
            "image_url": image_url if is_valid_image_url(image_url) else "",
            "image_source_url": (
                clean_url(item.get("image_source_url")) or direct_url
            ) if is_valid_image_url(image_url) else "",
            "source_tier": clean_text(item.get("source_tier")),
            "is_official": bool(item.get("is_official")),
            "core_eligible": bool(item.get("core_eligible", True)),
            "core_exclusion_reason": clean_text(item.get("core_exclusion_reason")),
            "event_family": clean_text(item.get("event_family")),
        })

    return rows


# =========================================================
# 6. 品牌、来源、品类和场景识别
# =========================================================

def detect_brand(text: str) -> str:
    lower = clean_text(text).lower()

    for brand, variant in BRAND_SEARCH_ROWS:
        if variant.lower() in lower:
            return brand

    return ""


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


def source_profile(
    source: str,
    source_homepage: str,
    article_url: str,
    inherited_tier: str = "",
    inherited_official: bool = False,
) -> tuple[str, bool, int]:
    combined = f"{source} {source_homepage} {article_url}"
    hosts = f"{host_of(source_homepage)} {host_of(article_url)}"
    official = bool(inherited_official) or has_any(combined, OFFICIAL_SOURCE_WORDS)
    official = official or any(domain in hosts for domain in OFFICIAL_DOMAINS)

    if official:
        return "official", True, 32

    inherited_tier = clean_text(inherited_tier)
    if inherited_tier in {"tier_1", "tier_2", "tier_3", "low"}:
        points = {"tier_1": 26, "tier_2": 20, "tier_3": 10, "low": 2}
        return inherited_tier, False, points[inherited_tier]

    if has_any(combined, TIER_1_WORDS):
        return "tier_1", False, 26
    if has_any(combined, TIER_2_WORDS):
        return "tier_2", False, 20
    if has_any(combined, LOW_SOURCE_WORDS) or any(domain in combined.lower() for domain in LOW_SOURCE_DOMAINS):
        return "low", False, 2
    return "tier_3", False, 10


def source_verification(
    source: str,
    source_homepage: str,
    article_url: str,
    inherited_tier: str = "",
    inherited_official: bool = False,
) -> tuple[str, bool]:
    tier, official, _ = source_profile(
        source,
        source_homepage,
        article_url,
        inherited_tier,
        inherited_official,
    )
    if official:
        return "official", True
    if tier in {"tier_1", "tier_2"}:
        return "trusted_media", False
    return "media", False


def is_valid_image_url(value: Any) -> bool:
    url = clean_url(value)
    if not url:
        return False

    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    full = f"{host}{path}"

    if any(host == blocked or host.endswith("." + blocked) for blocked in INVALID_IMAGE_HOSTS):
        return False
    if path.endswith((".svg", ".ico", ".gif")):
        return False
    if any(token in full for token in INVALID_IMAGE_TOKENS):
        return False
    return True


def direct_article_url(item: dict[str, Any]) -> str:
    for key in ["direct_url", "article_url", "url"]:
        url = clean_url(item.get(key))
        if url and is_external_url(url):
            return url
    return ""


def detect_category(text: str) -> str:
    for category, words in CATEGORY_RULES.items():
        if has_any(text, words):
            return category
    return "商品趋势"


def detect_audience(text: str, brand: str) -> str:
    for audience, words in AUDIENCE_RULES.items():
        if has_any(text, words):
            return audience

    if brand in ["361儿童", "安踏儿童", "FILA KIDS", "李宁YOUNG", "特步儿童", "巴拉巴拉", "moodytiger"]:
        return "儿童/青少年"

    return "成人/通用"


def detect_scenarios(text: str) -> list[str]:
    output = []
    for scenario, words in SCENARIO_RULES.items():
        if has_any(text, words):
            output.append(scenario)
    return output[:4]


def detect_terms(text: str, vocabulary: list[str], limit: int) -> list[str]:
    lower = clean_text(text).lower()
    output = []

    for term in vocabulary:
        if term.lower() in lower and term not in output:
            output.append(term)

    return output[:limit]


# =========================================================
# 7. 页面抓取与证据提取
# =========================================================

def meta_content(soup: BeautifulSoup, *, name: str = "", prop: str = "") -> str:
    node = None
    if prop:
        node = soup.find("meta", attrs={"property": prop})
    if not node and name:
        node = soup.find("meta", attrs={"name": name})
    if node:
        return clean_text(node.get("content", ""))
    return ""


def extract_page_text(soup: BeautifulSoup) -> str:
    for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        node.decompose()

    chunks = []
    for node in soup.find_all(["p", "h1", "h2", "h3", "li"]):
        text = clean_text(node.get_text(" ", strip=True))
        if len(text) >= 12:
            chunks.append(text)
        if sum(len(x) for x in chunks) >= 18_000:
            break

    return " ".join(chunks)[:18_000]


def enrich_candidate(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    url = direct_article_url(item)

    if not url:
        return enriched

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"},
        )
        response.raise_for_status()
    except Exception:
        return enriched

    final_url = clean_url(response.url)
    if not is_external_url(final_url):
        return enriched

    enriched["article_url"] = final_url
    enriched["direct_url"] = final_url
    enriched["link_status"] = "direct"

    if "html" not in response.headers.get("content-type", "").lower():
        return enriched

    try:
        soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    except Exception:
        return enriched

    canonical_node = soup.find("link", attrs={"rel": "canonical"})
    if canonical_node:
        canonical = clean_url(urljoin(final_url, canonical_node.get("href", "")))
        if canonical and is_external_url(canonical):
            enriched["article_url"] = canonical
            enriched["direct_url"] = canonical

    page_title = (
        meta_content(soup, prop="og:title")
        or meta_content(soup, name="twitter:title")
        or clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    )
    description = (
        meta_content(soup, prop="og:description")
        or meta_content(soup, name="description")
        or meta_content(soup, name="twitter:description")
    )
    image_url = (
        meta_content(soup, prop="og:image")
        or meta_content(soup, name="twitter:image")
    )

    if page_title:
        enriched["page_title"] = page_title
    if description:
        enriched["meta_description"] = description[:700]
    resolved_image = clean_url(urljoin(enriched.get("article_url") or final_url, image_url)) if image_url else ""
    if is_valid_image_url(resolved_image):
        enriched["image_url"] = resolved_image
        enriched["image_source_url"] = enriched.get("article_url") or final_url
    elif not is_valid_image_url(enriched.get("image_url")):
        enriched.pop("image_url", None)
        enriched.pop("image_source_url", None)

    enriched["page_text"] = extract_page_text(soup)
    enriched["source"] = normalize_source_name(
        enriched.get("source", ""),
        enriched.get("source_homepage", ""),
        enriched.get("article_url", ""),
    )
    tier, official, _ = source_profile(
        enriched.get("source", ""),
        enriched.get("source_homepage", ""),
        enriched.get("article_url", ""),
        enriched.get("source_tier", ""),
        bool(enriched.get("is_official")),
    )
    enriched["source_tier"] = tier
    enriched["is_official"] = official
    return enriched


def enrich_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = items[:ENRICH_LIMIT]
    output = []

    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as executor:
        future_map = {executor.submit(enrich_candidate, item): item for item in selected}

        for future in as_completed(future_map):
            original = future_map[future]
            try:
                output.append(future.result())
            except Exception:
                output.append(original)

    output.extend(items[ENRICH_LIMIT:])
    return output


# =========================================================
# 8. 具体产品事实提取
# =========================================================

def clean_product_name(value: str, brand: str) -> str:
    text = clean_text(value).strip("：:，,。；;（）()【】[]《》<>“”\"'")

    for variants in BRAND_VARIANTS.values():
        for variant in variants:
            text = re.sub(re.escape(variant), "", text, flags=re.IGNORECASE)

    text = re.sub(r"^(正式|全新|最新|推出|发布|首发|上新|新款|新品|联名)+", "", text)
    text = re.sub(r"(正式)?(发布|推出|首发|上新|发售|开售|上市)$", "", text)
    text = clean_text(text).strip("-—·：:")

    generic = {
        "新品", "新款", "运动品牌新品", "跑鞋新品", "儿童运动鞋", "运动鞋",
        "跑鞋", "篮球鞋", "户外鞋", "防晒衣", "运动服饰", "新品系列",
        "核心产品", "代表产品", "主推产品", "明星产品", "核心产品瑜伽服",
        "瑜伽服核心产品", "瑜伽服", "瑜伽裤", "运动内衣", "商品趋势",
    }

    if not text or text in generic or len(text) < 2 or len(text) > 60:
        return ""

    return text


def is_specific_product_name(value: str, brand: str = "") -> bool:
    name = clean_product_name(value, brand)
    if not name:
        return False

    residue = name
    for variants in BRAND_VARIANTS.values():
        for variant in variants:
            residue = re.sub(re.escape(variant), "", residue, flags=re.IGNORECASE)

    # 标题正则可能从多词英文品牌中间开始匹配；继续剔除品牌组成词，
    # 避免把“Yoga核心产品瑜伽服”误认成Alo Yoga的具体型号。
    for brand_part in re.findall(r"[A-Za-z0-9°]+|[一-龥]{2,}", clean_text(brand)):
        if len(brand_part) >= 2:
            residue = re.sub(re.escape(brand_part), "", residue, flags=re.IGNORECASE)

    removable = sorted(
        GENERIC_PRODUCT_PHRASES + PRODUCT_ACTION_WORDS + PRODUCT_NOUNS + [
            "产品", "商品", "核心", "代表", "主推", "明星", "全新", "系列",
            "运动", "儿童", "青少年", "成人", "男款", "女款", "同款",
        ],
        key=len,
        reverse=True,
    )
    for token in removable:
        residue = re.sub(re.escape(token), "", residue, flags=re.IGNORECASE)

    residue = re.sub(r"[^A-Za-z0-9一-龥]+", "", residue)
    if len(residue) < 2:
        return False

    # 只有通用品类和营销词，不视为“具名产品”。
    if re.fullmatch(r"(?:新品|新款|核心|产品|商品|系列|运动|鞋服|服装)+", residue):
        return False

    return True


def extract_product_name(text: str, brand: str) -> tuple[str, str]:
    search_text = clean_text(text)

    # 1. 已知系列名称只用于从原文中识别，不会凭空补入。
    for family in sorted(PRODUCT_MODEL_FAMILIES, key=len, reverse=True):
        family_pattern = (
            re.escape(family)
            + r"(?:\s*(?:第?\d{1,3}(?:\.\d+)?代?|[A-Za-z]{1,3}\d{1,3}))?"
        )
        family_match = re.search(family_pattern, search_text, flags=re.IGNORECASE)
        if family_match:
            candidate = clean_product_name(family_match.group(0), brand)
            if is_specific_product_name(candidate, brand):
                return candidate, "model_name_in_source"

    # 2. 引号中的具体产品名。
    quoted_patterns = [
        r"[“《「『](.{2,50}?)[”》」』]",
        r"\"([^\"]{2,50})\"",
    ]

    for pattern in quoted_patterns:
        for match in re.findall(pattern, search_text):
            candidate = clean_product_name(match, brand)
            if (
                candidate
                and has_any(candidate, PRODUCT_NOUNS + PRODUCT_MODEL_FAMILIES)
                and is_specific_product_name(candidate, brand)
            ):
                return candidate, "quoted_product_name"

    # 3. 中文/英文型号 + 商品名。
    product_pattern = (
        r"([A-Za-z0-9°＋+\-·一-龥]{2,34}"
        r"(?:系列|儿童|青少年|专业|竞速|缓震|越野|轻量|训练|运动)?"
        r"(?:儿童跑鞋|青少年跑鞋|儿童篮球鞋|篮球鞋|足球鞋|训练鞋|竞速跑鞋|"
        r"缓震跑鞋|越野跑鞋|跑鞋|童鞋|运动鞋|户外鞋|徒步鞋|溯溪鞋|"
        r"恢复拖鞋|运动凉鞋|凉鞋|拖鞋|防晒衣|防晒服|凉感T恤|速干T恤|"
        r"冲锋衣|软壳外套|羽绒服|运动外套|运动服|运动套装|瑜伽服|瑜伽裤))"
    )

    for match in re.findall(product_pattern, search_text, flags=re.IGNORECASE):
        candidate = clean_product_name(match, brand)
        if candidate and is_specific_product_name(candidate, brand):
            return candidate, "product_phrase_in_source"

    # 4. 独立英文/数字型号，例如 AB1234-001、C202 6代。
    model_match = re.search(
        r"\b([A-Z]{1,5}[0-9]{2,6}(?:-[A-Z0-9]{2,6})?|[A-Za-z]{2,18}\s?[0-9]{1,3}(?:\.\d+)?)\b",
        search_text,
    )
    if model_match:
        candidate = clean_product_name(model_match.group(1), brand)
        if candidate and is_specific_product_name(candidate, brand):
            return candidate, "model_code_in_source"

    return "", "not_identified"


def extract_model_code(text: str) -> str:
    patterns = [
        r"\b([A-Z]{2,5}\d{3,6}-\d{2,4})\b",
        r"(?:货号|款号|SKU|Style\s*Code)\s*[：:]?\s*([A-Za-z0-9\-]{5,20})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1)).upper()

    return ""


def extract_price(text: str) -> dict[str, Any]:
    patterns = [
        (r"(?:建议零售价|官方售价|发售价|售价|定价|价格)\s*(?:为|从|：|:)?\s*[¥￥]?\s*(\d{2,5})(?:\.\d{1,2})?\s*元", "CNY"),
        (r"(?:建议零售价|官方售价|发售价|售价|定价|价格)\s*(?:为|从|：|:)?\s*(\d{2,5})(?:\.\d{1,2})?\s*人民币", "CNY"),
        (r"(?:售价|定价|价格)\s*(?:为|从|：|:)?\s*\$\s*(\d{2,5})(?:\.\d{1,2})?", "USD"),
        (r"(?:售价|定价|价格)\s*(?:为|从|：|:)?\s*(\d{2,5})(?:\.\d{1,2})?\s*美元", "USD"),
    ]

    for pattern, currency in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        value = int(match.group(1))
        if currency == "CNY" and 30 <= value <= 20_000:
            return {
                "value": value,
                "currency": currency,
                "display": f"¥{value}",
                "basis": "source_explicit_price",
            }
        if currency == "USD" and 20 <= value <= 5_000:
            return {
                "value": value,
                "currency": currency,
                "display": f"${value}",
                "basis": "source_explicit_price",
            }

    return {
        "value": None,
        "currency": "",
        "display": "",
        "basis": "not_disclosed",
    }


def extract_release_date(text: str, article_date: str) -> dict[str, str]:
    patterns = [
        r"(?:将于|于)?\s*(20\d{2})年(\d{1,2})月(\d{1,2})日\s*(?:正式)?(?:发售|开售|上市|发布|上架)",
        r"(?:将于|于)?\s*(\d{1,2})月(\d{1,2})日\s*(?:正式)?(?:发售|开售|上市|发布|上架)",
    ]

    match = re.search(patterns[0], text)
    if match:
        try:
            value = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return {"date": value.isoformat(), "basis": "source_explicit_release_date"}
        except Exception:
            pass

    match = re.search(patterns[1], text)
    if match:
        try:
            article_year = datetime.strptime(article_date, "%Y-%m-%d").year
            value = date(article_year, int(match.group(1)), int(match.group(2)))
            return {"date": value.isoformat(), "basis": "source_explicit_release_date"}
        except Exception:
            pass

    return {"date": "", "basis": "not_disclosed"}


def evidence_snippet(text: str, terms: list[str], length: int = 180) -> str:
    clean = clean_text(text)
    lower = clean.lower()

    positions = [lower.find(term.lower()) for term in terms if term and term.lower() in lower]
    positions = [x for x in positions if x >= 0]
    start = max(0, min(positions) - 45) if positions else 0
    return short_text(clean[start:start + length], length)


def confidence_score(product: dict[str, Any]) -> int:
    score = 0
    tier = clean_text(product.get("source_tier"))
    score += 34 if product.get("is_official") else 23 if tier == "tier_1" else 19 if tier == "tier_2" else 9
    score += 24 if is_specific_product_name(product.get("product_name", ""), product.get("brand", "")) else 0
    score += 8 if product.get("model_code") else 0
    score += 8 if product.get("release_date") else 0
    score += 7 if product.get("price", {}).get("value") is not None else 0
    score += 7 if product.get("technologies") else 0
    score += 4 if is_valid_image_url(product.get("image_url")) else 0
    score += 8 if direct_article_url(product) else 0
    score += 12 if int(product.get("credible_source_count") or 0) >= 2 else 0
    return max(0, min(100, score))


def build_product_or_signal(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    headline = clean_text(item.get("headline"))
    identification_text = " ".join([
        headline,
        clean_text(item.get("page_title")),
        clean_text(item.get("meta_description")),
    ])
    combined = " ".join([
        identification_text,
        clean_text(item.get("page_text"))[:12_000],
    ])

    brand = detect_brand(identification_text) or detect_brand(combined)
    product_name, product_name_basis = extract_product_name(
        identification_text,
        brand,
    )
    model_code = extract_model_code(combined)
    category = detect_category(combined)
    audience = detect_audience(combined, brand)
    scenarios = detect_scenarios(combined)
    technologies = detect_terms(combined, TECHNOLOGY_WORDS, 10)
    materials = detect_terms(combined, MATERIAL_WORDS, 8)
    price = extract_price(combined)
    release = extract_release_date(combined, clean_text(item.get("published_date")))
    article_url = direct_article_url(item)
    source_homepage = clean_url(item.get("source_homepage"))
    source = normalize_source_name(item.get("source"), source_homepage, article_url)
    source_tier, is_official, _ = source_profile(
        source,
        source_homepage,
        article_url,
        clean_text(item.get("source_tier")),
        bool(item.get("is_official")),
    )
    verification = "official" if is_official else "trusted_media" if source_tier in {"tier_1", "tier_2"} else "media"
    image_url = clean_url(item.get("image_url"))
    if not is_valid_image_url(image_url):
        image_url = ""

    base = {
        "headline": headline,
        "brand": brand,
        "category": category,
        "audience": audience,
        "scenarios": scenarios,
        "source": source,
        "source_homepage": source_homepage,
        "article_url": article_url,
        "direct_url": article_url,
        "google_news_url": clean_url(item.get("google_news_url")),
        "link_status": clean_text(item.get("link_status")) or ("direct" if article_url else "google_news_fallback"),
        "published_at": clean_text(item.get("published_at")),
        "published_date": clean_text(item.get("published_date")),
        "image_url": image_url,
        "image_source": "page_open_graph" if image_url else "",
        "image_source_url": clean_url(item.get("image_source_url")) if image_url else "",
        "verification": verification,
        "source_tier": source_tier,
        "is_official": is_official,
        "core_eligible": bool(item.get("core_eligible", True)),
        "core_exclusion_reason": clean_text(item.get("core_exclusion_reason")),
        "event_family": clean_text(item.get("event_family")),
        "query_groups": safe_list(item.get("query_groups")),
        "discovered_by": safe_list(item.get("discovered_by")),
    }

    if product_name and is_specific_product_name(product_name, brand):
        official_url = base["article_url"] if is_official else ""
        product = {
            **base,
            "product_name": product_name,
            "product_name_basis": product_name_basis,
            "model_code": model_code,
            "release_date": release["date"],
            "release_date_basis": release["basis"],
            "price": price,
            "technologies": technologies,
            "materials": materials,
            "official_url": official_url,
            "evidence": {
                "product": evidence_snippet(combined, [product_name, model_code]),
                "technology": evidence_snippet(combined, technologies[:2]) if technologies else "",
                "price_or_release": evidence_snippet(
                    combined,
                    ["售价", "定价", "价格", "发售", "开售", "上市"],
                ),
            },
            "status": "new",
            "first_seen": REPORT_START_DATE.isoformat(),
            "last_seen": REPORT_END_DATE.isoformat(),
        }
        product["confidence_score"] = confidence_score(product)
        product["product_id"] = stable_id(
            "prd",
            f"{brand}|{norm_key(product_name)}|{model_code}",
        )
        return "product", product

    signal = {
        **base,
        "signal_id": stable_id("psg", f"{norm_key(headline)}|{base['source']}"),
        "signal_type": "product_media_signal",
        "keywords": detect_terms(combined, PRODUCT_NOUNS + PRODUCT_ACTION_WORDS + TECHNOLOGY_WORDS, 12),
        "evidence": evidence_snippet(combined, PRODUCT_NOUNS + PRODUCT_ACTION_WORDS),
        "note": "未识别到可核验的具体产品名，只作为媒体信号，不进入真实产品清单。",
    }
    return "signal", signal


# =========================================================
# 9. 去重、历史状态与品类信号
# =========================================================

def merge_discovery_duplicates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}

    for item in items:
        item = dict(item)
        direct_url = direct_article_url(item)
        source = normalize_source_name(
            item.get("source", ""),
            item.get("source_homepage", ""),
            direct_url,
        )
        item["source"] = source
        if direct_url:
            item["article_url"] = direct_url
            item["direct_url"] = direct_url
            item["link_status"] = "direct"

        source_identity = source.lower() or host_of(direct_url) or host_of(item.get("source_homepage", ""))
        key = f"{norm_key(item.get('headline'))}|{source_identity}"
        if not key:
            continue

        if key not in best:
            best[key] = item
            continue

        old = best[key]
        old["query_groups"] = list(dict.fromkeys(safe_list(old.get("query_groups")) + safe_list(item.get("query_groups"))))
        old["discovered_by"] = list(dict.fromkeys(safe_list(old.get("discovered_by")) + safe_list(item.get("discovered_by"))))

        if not is_valid_image_url(old.get("image_url")) and is_valid_image_url(item.get("image_url")):
            old["image_url"] = item.get("image_url")
            old["image_source_url"] = item.get("image_source_url", "")
        if not old.get("meta_description") and item.get("meta_description"):
            old["meta_description"] = item.get("meta_description")
        if not is_external_url(old.get("article_url", "")) and is_external_url(item.get("article_url", "")):
            old["article_url"] = item.get("article_url")
            old["direct_url"] = item.get("article_url")
            old["link_status"] = "direct"
        if not old.get("source_tier") and item.get("source_tier"):
            old["source_tier"] = item.get("source_tier")
        old["is_official"] = bool(old.get("is_official") or item.get("is_official"))

    return list(best.values())


def product_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    if a.get("model_code") and b.get("model_code") and a["model_code"] == b["model_code"]:
        return 1.0
    if a.get("brand") and b.get("brand") and a["brand"] != b["brand"]:
        return 0.0
    return SequenceMatcher(None, norm_key(a.get("product_name")), norm_key(b.get("product_name"))).ratio()


def coverage_row(product: dict[str, Any]) -> dict[str, Any]:
    url = direct_article_url(product)
    return {
        "headline": clean_text(product.get("headline")),
        "source": normalize_source_name(
            product.get("source", ""),
            product.get("source_homepage", ""),
            url,
        ),
        "url": url,
        "direct_url": url,
        "link_status": "direct" if url else clean_text(product.get("link_status")) or "google_news_fallback",
        "published_at": clean_text(product.get("published_at")),
        "published_date": clean_text(product.get("published_date")),
        "source_tier": clean_text(product.get("source_tier")) or "tier_3",
        "is_official": bool(product.get("is_official")),
    }


def coverage_identity(row: dict[str, Any]) -> str:
    source = normalize_source_name(row.get("source", ""), row.get("url", ""))
    return source.lower() or host_of(clean_url(row.get("url")))


def merge_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []

    for product in sorted(products, key=lambda x: x.get("confidence_score", 0), reverse=True):
        target = None
        for existing in merged:
            if product_similarity(product, existing) >= 0.78:
                target = existing
                break

        if target is None:
            product["coverage"] = [coverage_row(product)]
            merged.append(product)
            continue

        new_coverage = coverage_row(product)
        existing_keys = {
            (coverage_identity(row), norm_key(row.get("headline")))
            for row in safe_list(target.get("coverage"))
            if isinstance(row, dict)
        }
        coverage_key = (coverage_identity(new_coverage), norm_key(new_coverage.get("headline")))
        if coverage_key not in existing_keys:
            target["coverage"].append(new_coverage)
        target["technologies"] = list(dict.fromkeys(target.get("technologies", []) + product.get("technologies", [])))[:10]
        target["materials"] = list(dict.fromkeys(target.get("materials", []) + product.get("materials", [])))[:8]
        target["scenarios"] = list(dict.fromkeys(target.get("scenarios", []) + product.get("scenarios", [])))[:4]

        if not is_valid_image_url(target.get("image_url")) and is_valid_image_url(product.get("image_url")):
            target["image_url"] = product.get("image_url")
            target["image_source"] = product.get("image_source", "")
            target["image_source_url"] = product.get("image_source_url", "")
        if not target.get("official_url") and product.get("official_url"):
            target["official_url"] = product.get("official_url")
        if target.get("price", {}).get("value") is None and product.get("price", {}).get("value") is not None:
            target["price"] = product.get("price")
        if not target.get("release_date") and product.get("release_date"):
            target["release_date"] = product.get("release_date")
            target["release_date_basis"] = product.get("release_date_basis")

        target["confidence_score"] = max(target.get("confidence_score", 0), product.get("confidence_score", 0))
        if product.get("is_official"):
            target["is_official"] = True
            target["verification"] = "official"
            target["source_tier"] = "official"

    return merged


def evaluate_product_verification(product: dict[str, Any]) -> tuple[bool, str]:
    coverage = [x for x in safe_list(product.get("coverage")) if isinstance(x, dict)]
    unique_coverage = []
    used_sources = set()

    for row in coverage:
        identity = coverage_identity(row)
        if not identity or identity in used_sources:
            continue
        used_sources.add(identity)
        unique_coverage.append(row)

    direct_rows = [x for x in unique_coverage if is_external_url(clean_url(x.get("direct_url") or x.get("url")))]
    credible_rows = [
        x for x in direct_rows
        if x.get("is_official") or clean_text(x.get("source_tier")) in {"tier_1", "tier_2"}
    ]
    official_rows = [x for x in direct_rows if x.get("is_official")]

    product["coverage"] = unique_coverage
    product["source_count"] = len(unique_coverage)
    product["direct_source_count"] = len(direct_rows)
    product["credible_source_count"] = len(credible_rows)
    product["official_evidence_count"] = len(official_rows)
    product["evidence_status"] = "verified" if official_rows or len(credible_rows) >= 2 else "lead"

    if not clean_text(product.get("brand")):
        return False, "missing_brand"
    if not is_specific_product_name(product.get("product_name", ""), product.get("brand", "")):
        return False, "generic_or_missing_product_name"
    if not in_report_window(product.get("published_at") or product.get("published_date")):
        return False, "outside_or_missing_date"
    if not direct_rows:
        return False, "missing_direct_source"
    if official_rows:
        product["verification"] = "official"
        product["verification_reason"] = "官方来源直接核验"
        return True, "official_source"
    if len(credible_rows) >= 2:
        product["verification"] = "multi_source"
        product["verification_reason"] = "至少两家独立可信来源交叉核验"
        return True, "two_credible_sources"

    product["verification"] = "product_lead"
    product["verification_reason"] = "仅有单一非官方来源，保留为商品线索"
    return False, "insufficient_independent_evidence"


def product_to_lead(product: dict[str, Any], reason: str) -> dict[str, Any]:
    lead = dict(product)
    lead["signal_id"] = stable_id(
        "pld",
        f"{lead.get('brand', '')}|{norm_key(lead.get('product_name'))}|{norm_key(lead.get('headline'))}",
    )
    lead["signal_type"] = "product_lead"
    lead["lead_reason"] = reason
    lead["evidence_status"] = "lead"
    lead["note"] = "具名商品证据尚未达到官方单源或两家独立可信来源的核验门槛。"
    return lead


def suppress_duplicate_images(rows: list[dict[str, Any]]) -> int:
    counts = Counter(
        clean_url(row.get("image_url"))
        for row in rows
        if isinstance(row, dict) and is_valid_image_url(row.get("image_url"))
    )
    duplicated = {url for url, count in counts.items() if url and count > 1}
    suppressed = 0

    for row in rows:
        image_url = clean_url(row.get("image_url"))
        if not is_valid_image_url(image_url) or image_url in duplicated:
            if image_url:
                suppressed += 1
            row["image_url"] = ""
            row["image_source"] = ""
            row["image_source_url"] = ""
            if image_url in duplicated:
                row["image_rejection_reason"] = "duplicate_image_across_products"
            elif image_url:
                row["image_rejection_reason"] = "invalid_or_generic_image"

    return suppressed


def load_prior_products() -> list[dict[str, Any]]:
    cutoff = REPORT_START_DATE - timedelta(days=HISTORY_DAYS)
    output = []

    for path in sorted(ARCHIVE_DIR.glob("weekly_products_*.json"))[-16:]:
        data = load_json(path, {})
        window = data.get("report_window", {}) if isinstance(data, dict) else {}

        try:
            prior_end = datetime.strptime(window.get("end_date", ""), "%Y-%m-%d").date()
        except Exception:
            continue

        if prior_end < cutoff or prior_end >= REPORT_START_DATE:
            continue

        output.extend([x for x in safe_list(data.get("products")) if isinstance(x, dict)])

    return output


def apply_product_history(products: list[dict[str, Any]], prior_products: list[dict[str, Any]]) -> None:
    for product in products:
        best = None
        best_score = 0.0

        for prior in prior_products:
            score = product_similarity(product, prior)
            if score > best_score:
                best_score = score
                best = prior

        if best and best_score >= 0.78:
            product["status"] = "follow_up"
            product["previous_product_id"] = best.get("product_id", "")
            product["first_seen"] = best.get("first_seen") or best.get("last_seen") or product["first_seen"]


def build_category_signals(products: list[dict[str, Any]], media_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    category_counter = Counter()
    brand_counter: dict[str, Counter] = {}
    evidence_rows: dict[str, list[dict[str, str]]] = {}

    for product in products:
        category = product.get("category") or "商品趋势"
        category_counter[category] += 2
        brand_counter.setdefault(category, Counter())[product.get("brand") or "未识别品牌"] += 1
        evidence_rows.setdefault(category, []).append({
            "title": product.get("headline", ""),
            "source": product.get("source", ""),
            "url": product.get("article_url") or product.get("google_news_url", ""),
        })

    for signal in media_signals:
        category = signal.get("category") or "商品趋势"
        category_counter[category] += 1
        brand_counter.setdefault(category, Counter())[signal.get("brand") or "未识别品牌"] += 1
        evidence_rows.setdefault(category, []).append({
            "title": signal.get("headline", ""),
            "source": signal.get("source", ""),
            "url": signal.get("article_url") or signal.get("google_news_url", ""),
        })

    output = []
    for category, evidence_count in category_counter.most_common(12):
        output.append({
            "category": category,
            "evidence_count": evidence_count,
            "brands": [x[0] for x in brand_counter.get(category, Counter()).most_common(6)],
            "evidence": evidence_rows.get(category, [])[:6],
            "note": "证据数量只代表本周可见媒体/官方信息数量，不代表销量或搜索热度。",
        })

    return output


# =========================================================
# 10. 主程序
# =========================================================

def main() -> None:
    queries = build_queries()
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    })

    candidates = rows_from_weekly_sources()
    fetch_errors = []
    rejected = Counter()

    print(
        f"Weekly product evidence collector | {REPORT_START_DATE} ~ {REPORT_END_DATE} "
        f"| queries={len(queries)}"
    )
    print("Active campaigns:", "、".join(active_campaigns) if active_campaigns else "无")
    print(f"Candidates inherited from weekly sources: {len(candidates)}")

    for index, query_row in enumerate(queries, start=1):
        rows, error = fetch_rss(query_row, session)

        if error:
            fetch_errors.append({"query": query_row["query"], "error": error})
            print(f"[{index}/{len(queries)}] ERROR {query_row['query']}: {error}")
        else:
            print(f"[{index}/{len(queries)}] {query_row['group']} | {query_row['query']} -> {len(rows)}")

        for row in rows:
            headline = clean_text(row.get("headline"))

            if not headline or len(headline) < 8:
                rejected["missing_or_short_title"] += 1
                continue
            if not row.get("source"):
                rejected["missing_source"] += 1
                continue
            if not in_report_window(row.get("published_at")):
                rejected["outside_window"] += 1
                continue
            if has_any(headline, HARD_BAD_WORDS):
                rejected["bad_or_non_product_topic"] += 1
                continue
            if not has_any(headline, PRODUCT_NOUNS + PRODUCT_ACTION_WORDS + PRODUCT_MODEL_FAMILIES):
                rejected["no_product_signal"] += 1
                continue

            candidates.append(row)

        time.sleep(QUERY_INTERVAL)

    candidates = merge_discovery_duplicates(candidates)[:MAX_SOURCE_ITEMS]
    print(f"Accepted candidates after dedupe: {len(candidates)}")

    enriched = enrich_candidates(candidates) if candidates else []
    provisional_products = []
    product_leads = []
    media_signals = []

    for item in enriched:
        kind, row = build_product_or_signal(item)

        if kind == "product":
            basic_identity_ok = bool(
                row.get("product_name")
                and row.get("brand")
                and is_specific_product_name(row.get("product_name", ""), row.get("brand", ""))
            )

            if basic_identity_ok:
                provisional_products.append(row)
            else:
                row["signal_id"] = stable_id("psg", norm_key(row.get("headline")))
                row["signal_type"] = "generic_product_signal"
                row["note"] = "品牌或具体商品名不足，已降级为普通商品媒体信号。"
                media_signals.append(row)
        else:
            media_signals.append(row)

    merged_candidates = merge_products(provisional_products)
    products = []

    for product in merged_candidates:
        verified, reason = evaluate_product_verification(product)
        product["verification_gate_reason"] = reason
        product["confidence_score"] = confidence_score(product)

        if verified:
            products.append(product)
        else:
            product_leads.append(product_to_lead(product, reason))

    prior_products = load_prior_products()
    apply_product_history(products, prior_products)

    products = sorted(
        products,
        key=lambda x: (
            1 if x.get("is_official") else 0,
            x.get("confidence_score", 0),
            x.get("published_at", ""),
        ),
        reverse=True,
    )

    product_leads = sorted(
        product_leads,
        key=lambda x: (
            x.get("credible_source_count", 0),
            x.get("confidence_score", 0),
            x.get("published_at", ""),
        ),
        reverse=True,
    )[:50]

    media_signals = sorted(
        product_leads + media_signals,
        key=lambda x: (
            1 if x.get("signal_type") == "product_lead" else 0,
            1 if x.get("is_official") else 0,
            x.get("published_at", ""),
        ),
        reverse=True,
    )[:80]

    duplicate_image_suppressed_count = suppress_duplicate_images(products + media_signals)

    category_signals = build_category_signals(products, media_signals)
    product_status = Counter(x.get("status", "new") for x in products)
    verification_counts = Counter(x.get("verification", "unknown") for x in products)

    payload = {
        "schema_version": "2.1",
        "generated_at": GENERATED_AT.isoformat(timespec="minutes"),
        "report_window": {
            "start_date": REPORT_START_DATE.isoformat(),
            "end_date": REPORT_END_DATE.isoformat(),
            "timezone": TIMEZONE_NAME,
        },
        "methodology": {
            "purpose": "发现并核验周内出现的具体运动鞋服产品，不生成销量排名",
            "sources": "周度资讯池 + Google News RSS + 可访问网页元数据/正文",
            "active_campaigns": active_campaigns,
            "quality_gate": "进入products必须具备品牌、具体型号/系列名、周期内日期和原文直链，并满足官方单源或至少两家独立可信来源",
            "missing_value_policy": "价格、货号、发售日、技术或图片未披露时保持为空，不进行猜测",
            "image_policy": "仅保留官方页或原文页有效Open Graph图片；Google图标、Logo、占位图及跨产品重复图全部清空",
            "lead_policy": "未达到核验门槛的具名商品进入product_leads/media_signals，不进入已核验产品清单",
            "score_note": "confidence_score只代表资料完整度与来源可靠性，不代表销量或市场热度",
        },
        "stats": {
            "query_count": len(queries),
            "fetch_error_count": len(fetch_errors),
            "candidate_count": len(candidates),
            "verified_product_count": len(products),
            "official_product_count": sum(1 for x in products if x.get("is_official")),
            "multi_source_product_count": sum(1 for x in products if x.get("verification") == "multi_source"),
            "new_product_count": product_status.get("new", 0),
            "follow_up_product_count": product_status.get("follow_up", 0),
            "product_lead_count": len(product_leads),
            "media_signal_count": len(media_signals),
            "product_with_price_count": sum(1 for x in products if x.get("price", {}).get("value") is not None),
            "product_with_release_date_count": sum(1 for x in products if x.get("release_date")),
            "product_with_image_count": sum(1 for x in products if x.get("image_url")),
            "duplicate_image_suppressed_count": duplicate_image_suppressed_count,
            "direct_source_product_count": sum(1 for x in products if x.get("direct_source_count", 0) > 0),
            "verification": dict(verification_counts),
            "lead_reasons": dict(Counter(x.get("lead_reason", "unknown") for x in product_leads)),
            "rejected": dict(rejected),
        },
        "queries": queries,
        "fetch_errors": fetch_errors[:30],
        "products": products,
        "product_leads": product_leads,
        "category_signals": category_signals,
        "media_signals": media_signals,
    }

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    archive_file = ARCHIVE_DIR / (
        f"weekly_products_{REPORT_START_DATE.isoformat()}_{REPORT_END_DATE.isoformat()}.json"
    )

    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(OUTPUT_FILE)
    archive_file.write_text(content, encoding="utf-8")

    print(f"weekly products saved: {OUTPUT_FILE}")
    print(f"weekly products archived: {archive_file}")
    print(
        f"verified products: {len(products)} | official: "
        f"{sum(1 for x in products if x.get('is_official'))} | media signals: {len(media_signals)}"
    )

    if not products:
        print("NOTICE: no product passed the evidence gate; the report should show an empty verified-product state.")

    print("\nVerified product evidence:")
    for index, product in enumerate(products[:20], start=1):
        print(
            f"{index}. [{product['confidence_score']}] [{product['verification']}] "
            f"{product['brand']} | {product['product_name']} | {product['source']}"
        )


if __name__ == "__main__":
    main()
