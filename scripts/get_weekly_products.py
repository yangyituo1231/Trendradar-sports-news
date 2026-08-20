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
    "冠军跑鞋", "马赫", "竞速160", "飞飚", "咻",
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
        source = clean_text(source_node.text if source_node is not None else "")
        source_homepage = clean_url(source_node.attrib.get("url", "") if source_node is not None else "")
        pub_dt = parse_datetime(node.findtext("pubDate"))

        rows.append({
            "headline": normalize_rss_title(node.findtext("title") or "", source),
            "source": source,
            "source_homepage": source_homepage,
            "google_news_url": clean_url(node.findtext("link")),
            "article_url": clean_url(node.findtext("link")),
            "published_at": pub_dt.isoformat(timespec="minutes") if pub_dt else "",
            "published_date": pub_dt.date().isoformat() if pub_dt else "",
            "query_groups": [query_row["group"]],
            "discovered_by": [query_row["query"]],
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

        rows.append({
            "headline": title,
            "source": clean_text(item.get("source")),
            "source_homepage": clean_url(item.get("source_url")),
            "google_news_url": clean_url(item.get("google_news_url")),
            "article_url": clean_url(item.get("direct_url") or item.get("url")),
            "published_at": clean_text(item.get("published_at")),
            "published_date": clean_text(item.get("published_date")),
            "query_groups": list(dict.fromkeys(safe_list(item.get("query_groups")) + ["weekly_source_pool"])),
            "discovered_by": safe_list(item.get("discovered_by")),
            "meta_description": clean_text(item.get("meta_description")),
            "image_url": clean_url(item.get("image_url")),
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


def source_verification(source: str, source_homepage: str, article_url: str) -> tuple[str, bool]:
    combined = f"{source} {source_homepage} {article_url}"
    hosts = f"{host_of(source_homepage)} {host_of(article_url)}"
    official = has_any(combined, OFFICIAL_SOURCE_WORDS) or any(domain in hosts for domain in OFFICIAL_DOMAINS)

    if official:
        return "official", True
    if has_any(combined, TRUSTED_MEDIA_WORDS):
        return "trusted_media", False
    return "media", False


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
    url = clean_url(item.get("article_url") or item.get("google_news_url"))

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
    if is_external_url(final_url):
        enriched["article_url"] = final_url

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
    if image_url:
        enriched["image_url"] = urljoin(enriched.get("article_url") or final_url, image_url)

    enriched["page_text"] = extract_page_text(soup)
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
    }

    if not text or text in generic or len(text) < 2 or len(text) > 60:
        return ""

    return text


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
            return clean_text(family_match.group(0)), "model_name_in_source"

    # 2. 引号中的具体产品名。
    quoted_patterns = [
        r"[“《「『](.{2,50}?)[”》」』]",
        r"\"([^\"]{2,50})\"",
    ]

    for pattern in quoted_patterns:
        for match in re.findall(pattern, search_text):
            candidate = clean_product_name(match, brand)
            if candidate and has_any(candidate, PRODUCT_NOUNS + PRODUCT_MODEL_FAMILIES):
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
        if candidate:
            return candidate, "product_phrase_in_source"

    # 4. 独立英文/数字型号，例如 AB1234-001、C202 6代。
    model_match = re.search(
        r"\b([A-Z]{1,5}[0-9]{2,6}(?:-[A-Z0-9]{2,6})?|[A-Za-z]{2,18}\s?[0-9]{1,3}(?:\.\d+)?)\b",
        search_text,
    )
    if model_match:
        candidate = clean_product_name(model_match.group(1), brand)
        if candidate:
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
        "display": "未披露",
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
    score += 36 if product.get("is_official") else 22 if product.get("verification") == "trusted_media" else 12
    score += 24 if product.get("product_name") else 0
    score += 8 if product.get("model_code") else 0
    score += 8 if product.get("release_date") else 0
    score += 7 if product.get("price", {}).get("value") is not None else 0
    score += 7 if product.get("technologies") else 0
    score += 5 if product.get("image_url") else 0
    score += 5 if product.get("article_url") else 0
    return max(0, min(100, score))


def build_product_or_signal(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    headline = clean_text(item.get("headline"))
    combined = " ".join([
        headline,
        clean_text(item.get("page_title")),
        clean_text(item.get("meta_description")),
        clean_text(item.get("page_text"))[:12_000],
    ])

    brand = detect_brand(combined)
    product_name, product_name_basis = extract_product_name(
        " ".join([headline, clean_text(item.get("page_title")), clean_text(item.get("meta_description"))]),
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
    verification, is_official = source_verification(
        clean_text(item.get("source")),
        clean_url(item.get("source_homepage")),
        clean_url(item.get("article_url")),
    )

    base = {
        "headline": headline,
        "brand": brand,
        "category": category,
        "audience": audience,
        "scenarios": scenarios,
        "source": clean_text(item.get("source")),
        "source_homepage": clean_url(item.get("source_homepage")),
        "article_url": clean_url(item.get("article_url")),
        "google_news_url": clean_url(item.get("google_news_url")),
        "published_at": clean_text(item.get("published_at")),
        "published_date": clean_text(item.get("published_date")),
        "image_url": clean_url(item.get("image_url")),
        "image_source": "page_open_graph" if item.get("image_url") else "",
        "verification": verification,
        "is_official": is_official,
        "query_groups": safe_list(item.get("query_groups")),
        "discovered_by": safe_list(item.get("discovered_by")),
    }

    if product_name:
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
        key = norm_key(item.get("headline"))
        if not key:
            continue

        if key not in best:
            best[key] = item
            continue

        old = best[key]
        old["query_groups"] = list(dict.fromkeys(safe_list(old.get("query_groups")) + safe_list(item.get("query_groups"))))
        old["discovered_by"] = list(dict.fromkeys(safe_list(old.get("discovered_by")) + safe_list(item.get("discovered_by"))))

        if not old.get("image_url") and item.get("image_url"):
            old["image_url"] = item.get("image_url")
        if not old.get("meta_description") and item.get("meta_description"):
            old["meta_description"] = item.get("meta_description")
        if not is_external_url(old.get("article_url", "")) and is_external_url(item.get("article_url", "")):
            old["article_url"] = item.get("article_url")

    return list(best.values())


def product_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    if a.get("model_code") and b.get("model_code") and a["model_code"] == b["model_code"]:
        return 1.0
    if a.get("brand") and b.get("brand") and a["brand"] != b["brand"]:
        return 0.0
    return SequenceMatcher(None, norm_key(a.get("product_name")), norm_key(b.get("product_name"))).ratio()


def merge_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []

    for product in sorted(products, key=lambda x: x.get("confidence_score", 0), reverse=True):
        target = None
        for existing in merged:
            if product_similarity(product, existing) >= 0.78:
                target = existing
                break

        if target is None:
            product["coverage"] = [{
                "headline": product.get("headline", ""),
                "source": product.get("source", ""),
                "url": product.get("article_url") or product.get("google_news_url", ""),
                "published_at": product.get("published_at", ""),
            }]
            merged.append(product)
            continue

        target["coverage"].append({
            "headline": product.get("headline", ""),
            "source": product.get("source", ""),
            "url": product.get("article_url") or product.get("google_news_url", ""),
            "published_at": product.get("published_at", ""),
        })
        target["technologies"] = list(dict.fromkeys(target.get("technologies", []) + product.get("technologies", [])))[:10]
        target["materials"] = list(dict.fromkeys(target.get("materials", []) + product.get("materials", [])))[:8]
        target["scenarios"] = list(dict.fromkeys(target.get("scenarios", []) + product.get("scenarios", [])))[:4]

        if not target.get("image_url") and product.get("image_url"):
            target["image_url"] = product.get("image_url")
            target["image_source"] = product.get("image_source", "")
        if not target.get("official_url") and product.get("official_url"):
            target["official_url"] = product.get("official_url")
        if target.get("price", {}).get("value") is None and product.get("price", {}).get("value") is not None:
            target["price"] = product.get("price")
        if not target.get("release_date") and product.get("release_date"):
            target["release_date"] = product.get("release_date")
            target["release_date_basis"] = product.get("release_date_basis")

        target["confidence_score"] = max(target.get("confidence_score", 0), product.get("confidence_score", 0))

    return merged


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
    products = []
    media_signals = []

    for item in enriched:
        kind, row = build_product_or_signal(item)

        if kind == "product":
            # 非官方媒体识别出的产品，至少需要具体产品名、品牌和可点击来源。
            quality_ok = bool(
                row.get("product_name")
                and row.get("brand")
                and (row.get("article_url") or row.get("google_news_url"))
                and row.get("confidence_score", 0) >= 46
            )

            if quality_ok:
                products.append(row)
            else:
                row["signal_id"] = stable_id("psg", norm_key(row.get("headline")))
                row["signal_type"] = "insufficient_product_evidence"
                row["note"] = "具体商品证据不足，已降级为媒体信号。"
                media_signals.append(row)
        else:
            media_signals.append(row)

    products = merge_products(products)
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

    media_signals = sorted(
        media_signals,
        key=lambda x: (
            1 if x.get("is_official") else 0,
            x.get("published_at", ""),
        ),
        reverse=True,
    )[:80]

    category_signals = build_category_signals(products, media_signals)
    product_status = Counter(x.get("status", "new") for x in products)
    verification_counts = Counter(x.get("verification", "unknown") for x in products)

    payload = {
        "schema_version": "2.0",
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
            "quality_gate": "进入products必须具备具体产品名、品牌、日期和可点击来源",
            "missing_value_policy": "价格、货号、发售日、技术或图片未披露时保持为空，不进行猜测",
            "image_policy": "仅保留原网页Open Graph图片，不使用通用图库占位",
            "score_note": "confidence_score只代表资料完整度与来源可靠性，不代表销量或市场热度",
        },
        "stats": {
            "query_count": len(queries),
            "fetch_error_count": len(fetch_errors),
            "candidate_count": len(candidates),
            "verified_product_count": len(products),
            "official_product_count": sum(1 for x in products if x.get("is_official")),
            "new_product_count": product_status.get("new", 0),
            "follow_up_product_count": product_status.get("follow_up", 0),
            "media_signal_count": len(media_signals),
            "product_with_price_count": sum(1 for x in products if x.get("price", {}).get("value") is not None),
            "product_with_release_date_count": sum(1 for x in products if x.get("release_date")),
            "product_with_image_count": sum(1 for x in products if x.get("image_url")),
            "verification": dict(verification_counts),
            "rejected": dict(rejected),
        },
        "queries": queries,
        "fetch_errors": fetch_errors[:30],
        "products": products,
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
