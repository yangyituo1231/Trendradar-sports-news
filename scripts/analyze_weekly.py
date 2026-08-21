from __future__ import annotations

import json
import os
import re

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


# =========================================================
# 0. 文件与运行配置
# =========================================================

TIMEZONE_NAME = "Asia/Shanghai"
LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

WEEKLY_DIR = Path("output/weekly")
ARCHIVE_DIR = WEEKLY_DIR / "archive"

SOURCE_FILE = WEEKLY_DIR / "weekly_sources.json"
PRODUCT_FILE = WEEKLY_DIR / "weekly_products.json"
OUTPUT_FILE = WEEKLY_DIR / "weekly_analysis.json"

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

MIN_EVENT_SCORE = 42
MAX_EVENT_CANDIDATES_FOR_AI = 55
MAX_PRODUCT_CANDIDATES_FOR_AI = 24
MAX_KEY_DEVELOPMENTS = 8
MIN_KEY_DEVELOPMENTS = 4
MAX_DEEP_DIVES = 4
MAX_PRODUCTS = 6
MAX_COMPETITOR_CHANNEL = 6
MAX_KIDS_CONSUMER = 5
MAX_WATCHLIST = 5


# =========================================================
# 1. 基础工具
# =========================================================

def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"load json error: {path} {repr(exc)}")
        return default


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\n", " ").replace("\u200b", " ").strip()
    return re.sub(r"\s+", " ", text)


def short_text(value: Any, length: int) -> str:
    text = clean_text(value)
    if len(text) <= length:
        return text
    return text[:length].rstrip("，。；：,.;:") + "..."


def clean_url(value: Any) -> str:
    url = clean_text(value)
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return ""


def host_of(value: Any) -> str:
    try:
        return urlparse(clean_url(value)).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def is_direct_url(value: Any) -> bool:
    url = clean_url(value)
    host = host_of(url)
    if not url or not host:
        return False
    blocked = ["news.google.com", "google.com", "consent.google.com", "accounts.google.com"]
    return not any(host == x or host.endswith("." + x) for x in blocked)


def is_google_news_url(value: Any) -> bool:
    """Google News RSS链接可作为受控回退证据，但不冒充媒体原文直链。"""
    url = clean_url(value)
    host = host_of(url)
    return bool(url and (host == "news.google.com" or host.endswith(".news.google.com")))


def is_evidence_url(value: Any) -> bool:
    """优先接受媒体原文；原文解析失败时允许Google News可点击中转链接。"""
    return is_direct_url(value) or is_google_news_url(value)


def valid_image_url(value: Any) -> str:
    url = clean_url(value)
    host = host_of(url)
    path = urlparse(url).path.lower() if url else ""
    full = f"{host}{path}"

    if not url or not host:
        return ""
    if any(
        host == x or host.endswith("." + x)
        for x in ["google.com", "googleusercontent.com", "gstatic.com", "ggpht.com", "news.google.com"]
    ):
        return ""
    if path.endswith((".svg", ".ico", ".gif")):
        return ""
    if any(token in full for token in ["logo", "icon", "favicon", "avatar", "default", "placeholder", "sprite"]):
        return ""
    return url


GOOGLE_BOILERPLATE_MARKERS = [
    "Comprehensive up-to-date news coverage",
    "aggregated from sources all over the world by Google News",
    "Google News provides comprehensive",
]


def clean_summary(value: Any, length: int = 260) -> str:
    text = clean_text(value)
    if not text or any(marker.lower() in text.lower() for marker in GOOGLE_BOILERPLATE_MARKERS):
        return ""
    return short_text(text, length)


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def norm_key(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|·™®]+", "", text)
    return text[:120]


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        pass

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def title_similarity(a: str, b: str) -> float:
    a_key = norm_key(a)
    b_key = norm_key(b)
    if not a_key or not b_key:
        return 0.0
    if a_key in b_key or b_key in a_key:
        return min(len(a_key), len(b_key)) / max(len(a_key), len(b_key))
    return SequenceMatcher(None, a_key, b_key).ratio()


def unique_strings(values: list[Any], limit: int | None = None) -> list[str]:
    output = []
    used = set()

    for value in values:
        text = clean_text(value)
        if not text or text in used:
            continue
        used.add(text)
        output.append(text)
        if limit and len(output) >= limit:
            break

    return output


def extract_json_object(text: Any) -> dict[str, Any]:
    if isinstance(text, dict):
        return text

    raw = clean_text(text)
    if not raw:
        return {}

    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(raw[start:end + 1])
            return value if isinstance(value, dict) else {}
        except Exception:
            pass

    return {}


def numeric_tokens(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?%?", clean_text(text))


def sanitize_grounded_text(text: Any, evidence_text: str, max_length: int) -> str:
    """
    AI可以做归纳，但若新增了证据中不存在的数字，则删除该句。
    新闻标题、日期、来源不会经过AI生成。
    """
    raw = clean_text(text)
    if not raw:
        return ""

    evidence_numbers = set(numeric_tokens(evidence_text))
    sentences = re.split(r"(?<=[。！？；])", raw)
    kept = []

    for sentence in sentences:
        sentence = clean_text(sentence)
        if not sentence:
            continue

        unsupported = [number for number in numeric_tokens(sentence) if number not in evidence_numbers]
        if unsupported:
            continue
        kept.append(sentence)

    return short_text("".join(kept), max_length)


# =========================================================
# 2. 读取并校验输入
# =========================================================

weekly_sources = load_json(SOURCE_FILE, {})
weekly_products = load_json(PRODUCT_FILE, {})

if not isinstance(weekly_sources, dict) or not weekly_sources:
    raise SystemExit(f"Missing or invalid source file: {SOURCE_FILE}")

source_window = safe_dict(weekly_sources.get("report_window"))
product_window = safe_dict(weekly_products.get("report_window"))

REPORT_START_DATE = parse_date(source_window.get("start_date"))
REPORT_END_DATE = parse_date(source_window.get("end_date"))

if not REPORT_START_DATE or not REPORT_END_DATE:
    raise SystemExit("weekly_sources.json has no valid report window")

if product_window:
    product_start = parse_date(product_window.get("start_date"))
    product_end = parse_date(product_window.get("end_date"))
    if product_start != REPORT_START_DATE or product_end != REPORT_END_DATE:
        print("WARNING: weekly_products.json window differs from weekly_sources.json; source window wins")

GENERATED_AT = datetime.now(LOCAL_TZ)

source_items = [x for x in safe_list(weekly_sources.get("items")) if isinstance(x, dict)]
source_events_raw = [x for x in safe_list(weekly_sources.get("events")) if isinstance(x, dict)]
source_conflicts = [x for x in safe_list(weekly_sources.get("conflict_groups")) if isinstance(x, dict)]
product_leads = [x for x in safe_list(weekly_products.get("product_leads")) if isinstance(x, dict)]


def normalize_product_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """把可信单一来源的具名商品转为可审阅候选，不补写原文未披露字段。"""
    copied = dict(row)
    source_tier = clean_text(copied.get("source_tier"))
    trusted_single = bool(copied.get("is_official")) or source_tier in {"official", "tier_1", "tier_2"}

    if trusted_single and clean_text(copied.get("evidence_status")) != "verified":
        copied["evidence_status"] = "media_confirmed"
        copied["verification"] = "official" if copied.get("is_official") else "trusted_media"
        copied["verification_reason"] = (
            "官方来源单篇报道确认；链接解析失败时保留Google News中转链接。"
            if copied.get("is_official")
            else "单一可信媒体报道确认；价格、发售日和技术字段仅在原文披露时展示。"
        )
    return copied


product_rows = [
    normalize_product_candidate(x)
    for x in safe_list(weekly_products.get("products")) + product_leads
    if isinstance(x, dict)
]
product_media_signals = [x for x in safe_list(weekly_products.get("media_signals")) if isinstance(x, dict)]
product_category_signals = [x for x in safe_list(weekly_products.get("category_signals")) if isinstance(x, dict)]

item_map = {clean_text(x.get("id")): x for x in source_items if clean_text(x.get("id"))}
product_map = {clean_text(x.get("product_id")): x for x in product_rows if clean_text(x.get("product_id"))}


def coalesce_financial_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """分析层兜底：同一品牌、同一财务周期只保留一个事件。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for event in events:
        event_id = clean_text(event.get("event_id"))
        family = clean_text(event.get("event_family"))
        period = clean_text(event.get("reporting_period"))
        brands = unique_strings(safe_list(event.get("brands")), 5)
        primary_brand = brands[0].lower() if brands else ""

        if family == "financial_results" and period and primary_brand:
            key = f"financial|{primary_brand}|{period}"
        else:
            key = f"event|{event_id or norm_key(event.get('title'))}"
        grouped[key].append(event)

    output = []
    for rows in grouped.values():
        if len(rows) == 1:
            row = dict(rows[0])
            row["merged_event_ids"] = unique_strings(
                [row.get("event_id")] + safe_list(row.get("merged_event_ids")),
                12,
            )
            output.append(row)
            continue

        def representative_rank(row: dict[str, Any]) -> tuple[int, int, int, int]:
            verification = clean_text(row.get("verification"))
            return (
                2 if verification == "official_source" else 1 if verification == "multi_source" else 0,
                1 if is_direct_url(row.get("direct_url") or row.get("url")) else 0,
                to_int(row.get("editorial_score"), 0),
                to_int(row.get("source_count"), 0),
            )

        representative = dict(max(rows, key=representative_rank))
        evidence = []
        evidence_used = set()
        sources = []
        source_used = set()

        for row in rows:
            for item in safe_list(row.get("evidence")):
                if not isinstance(item, dict):
                    continue
                key = clean_text(item.get("item_id")) or clean_url(item.get("direct_url") or item.get("url"))
                if not key or key in evidence_used:
                    continue
                evidence_used.add(key)
                evidence.append(dict(item))
            for source in safe_list(row.get("sources")):
                source = clean_text(source)
                if source and source not in source_used:
                    source_used.add(source)
                    sources.append(source)

        direct_hosts = {
            host_of(x.get("direct_url") or x.get("url"))
            for x in evidence
            if is_direct_url(x.get("direct_url") or x.get("url"))
        }
        official_count = sum(1 for x in evidence if x.get("is_official"))
        verification = (
            "official_source" if official_count
            else "multi_source" if len(direct_hosts) >= 2
            else clean_text(representative.get("verification")) or "single_source"
        )

        merged_ids = unique_strings(
            [x.get("event_id") for x in rows]
            + [y for x in rows for y in safe_list(x.get("merged_event_ids"))],
            30,
        )
        representative.update({
            "evidence": evidence,
            "sources": sources,
            "item_ids": unique_strings([y for x in rows for y in safe_list(x.get("item_ids"))], 80),
            "original_titles": unique_strings(
                [x.get("title") for x in rows]
                + [y for x in rows for y in safe_list(x.get("original_titles"))],
                30,
            ),
            "brands": unique_strings([y for x in rows for y in safe_list(x.get("brands"))], 8),
            "keywords": unique_strings([y for x in rows for y in safe_list(x.get("keywords"))], 20),
            "merged_event_ids": merged_ids,
            "mention_count": sum(max(1, to_int(x.get("mention_count"), 1)) for x in rows),
            "source_count": len(direct_hosts) or max(to_int(x.get("source_count"), 0) for x in rows),
            "direct_source_count": len(direct_hosts),
            "verification": verification,
            "conflict_flag": any(bool(x.get("conflict_flag")) for x in rows),
            "editorial_score": min(
                100,
                max(to_int(x.get("editorial_score"), 0) for x in rows) + min(8, (len(rows) - 1) * 3),
            ),
        })
        output.append(representative)

    return sorted(
        output,
        key=lambda x: (to_int(x.get("editorial_score"), 0), to_int(x.get("source_count"), 0)),
        reverse=True,
    )


source_events = coalesce_financial_events(source_events_raw)
event_map = {}
for event in source_events:
    aliases = unique_strings(
        [event.get("event_id")] + safe_list(event.get("merged_event_ids")),
        40,
    )
    for event_id in aliases:
        event_map[event_id] = event


# =========================================================
# 3. 事件和产品质量门槛
# =========================================================

INVALID_SOURCE_NAMES = {"", "公开资讯", "Google", "Google News", "网络资讯", "综合网络"}

LOW_VALUE_EVENT_WORDS = [
    "股价", "K线", "支撑位", "压力位", "目标价", "涨停", "跌停", "龙虎榜", "股票",
    "优惠券", "省钱", "值得买", "怎么买", "怎么选", "适合去哪", "旅游攻略", "选购攻略", "FAQ",
    "餐饮团购", "餐饮套餐", "七夕餐饮", "股票支撑", "股票走势", "股价能否", "TOPBRAND |",
]

LOW_RELEVANCE_EVENT_PATTERNS = [
    r"TOPBRAND.*(?:；|;).*(?:；|;)",
    r"(?:餐饮|外卖).*(?:团购|套餐|优惠)",
    r"(?:股价|股票).*(?:支撑|压力|走势|目标价)",
]

GENERIC_PRODUCT_WORDS = [
    "核心产品", "代表产品", "主推产品", "明星产品", "新品系列", "新款系列", "品牌新品",
    "产品", "商品", "核心", "代表", "主推", "明星", "全新", "新品", "新款", "系列",
    "运动", "儿童", "青少年", "成人", "男款", "女款", "同款", "跑鞋", "运动鞋", "篮球鞋",
    "户外鞋", "防晒衣", "瑜伽服", "瑜伽裤", "运动内衣", "服装", "鞋服", "商品趋势",
]


def event_representative_item(event: dict[str, Any]) -> dict[str, Any]:
    representative_id = clean_text(event.get("representative_id"))
    if representative_id and representative_id in item_map:
        return item_map[representative_id]

    for item_id in safe_list(event.get("item_ids")):
        if clean_text(item_id) in item_map:
            return item_map[clean_text(item_id)]

    return {}


def event_evidence_rows(event: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    used = set()

    for row in safe_list(event.get("evidence")):
        if not isinstance(row, dict):
            continue
        url = clean_url(row.get("direct_url") or row.get("url") or row.get("google_news_url"))
        if not is_evidence_url(url) or url in used:
            continue
        used.add(url)
        output.append({
            "item_id": clean_text(row.get("item_id")),
            "title": clean_text(row.get("title")),
            "source": clean_text(row.get("source")),
            "source_tier": clean_text(row.get("source_tier")),
            "is_official": bool(row.get("is_official")),
            "url": url,
            "published_at": clean_text(row.get("published_at")),
            "summary": clean_summary(row.get("summary")),
        })

    return sorted(
        output,
        key=lambda x: (
            1 if x.get("is_official") else 0,
            2 if x.get("source_tier") == "tier_1" else 1 if x.get("source_tier") == "tier_2" else 0,
            x.get("published_at", ""),
        ),
        reverse=True,
    )


def event_primary_evidence(event: dict[str, Any]) -> dict[str, Any]:
    representative = event_representative_item(event)
    candidates = [
        {
            "title": event.get("title"),
            "source": event.get("source"),
            "source_tier": event.get("source_tier"),
            "is_official": event.get("verification") == "official_source",
            "url": event.get("direct_url") or event.get("url") or event.get("google_news_url"),
            "published_at": event.get("published_at"),
            "summary": event.get("summary"),
        },
        {
            "item_id": representative.get("id"),
            "title": representative.get("title"),
            "source": representative.get("source"),
            "source_tier": representative.get("source_tier"),
            "is_official": representative.get("is_official"),
            "url": representative.get("direct_url") or representative.get("url") or representative.get("google_news_url"),
            "published_at": representative.get("published_at") or representative.get("published_date"),
            "summary": representative.get("meta_description"),
        },
    ] + event_evidence_rows(event)

    for row in candidates:
        url = clean_url(row.get("url"))
        source = clean_text(row.get("source"))
        if is_evidence_url(url) and source not in INVALID_SOURCE_NAMES:
            copied = dict(row)
            copied["url"] = url
            copied["summary"] = clean_summary(copied.get("summary"))
            return copied

    return {}


def event_url(event: dict[str, Any]) -> str:
    return clean_url(event_primary_evidence(event).get("url"))


def event_source(event: dict[str, Any]) -> str:
    return clean_text(event_primary_evidence(event).get("source"))


def event_source_tier(event: dict[str, Any]) -> str:
    return clean_text(event_primary_evidence(event).get("source_tier"))


def event_summary(event: dict[str, Any]) -> str:
    primary = event_primary_evidence(event)
    return (
        clean_summary(event.get("summary"))
        or clean_summary(primary.get("summary"))
    )


def event_date(event: dict[str, Any]) -> date | None:
    primary = event_primary_evidence(event)
    return parse_date(primary.get("published_at") or event.get("published_at"))


def event_is_official(event: dict[str, Any]) -> bool:
    return bool(
        event.get("verification") == "official_source"
        or event_primary_evidence(event).get("is_official")
        or any(x.get("is_official") for x in event_evidence_rows(event))
    )


def event_quality_reason(event: dict[str, Any]) -> str:
    title = clean_text(event.get("title"))
    source = event_source(event)
    url = event_url(event)
    published_date = event_date(event)

    if not clean_text(event.get("event_id")):
        return "missing_event_id"
    if not title:
        return "missing_title"
    if any(word.lower() in title.lower() for word in LOW_VALUE_EVENT_WORDS):
        return "low_value_topic"
    if any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in LOW_RELEVANCE_EVENT_PATTERNS):
        return "low_relevance_topic"
    if clean_text(event.get("event_family")) == "local_activity":
        return "local_promotion"
    if source in INVALID_SOURCE_NAMES:
        return "invalid_source"
    if not url:
        return "missing_direct_url"
    if event_source_tier(event) == "tier_4":
        return "low_quality_source"
    if (
        clean_text(event.get("verification")) == "single_source"
        and to_int(event.get("source_count"), 1) < 2
        and event_source_tier(event) == "tier_3"
    ):
        return "weak_single_source"
    if not published_date:
        return "missing_date"
    if not (REPORT_START_DATE <= published_date <= REPORT_END_DATE):
        return "outside_window"
    if to_int(event.get("editorial_score"), 0) < MIN_EVENT_SCORE:
        return "low_editorial_score"
    if event.get("conflict_flag"):
        return "unresolved_conflict"
    return ""


def is_specific_product_name(value: Any, brand: Any = "") -> bool:
    residue = clean_text(value)
    if not residue:
        return False

    for token in [clean_text(brand)] + GENERIC_PRODUCT_WORDS:
        if token:
            residue = re.sub(re.escape(token), "", residue, flags=re.IGNORECASE)

    for brand_part in re.findall(r"[A-Za-z0-9°]+|[一-龥]{2,}", clean_text(brand)):
        if len(brand_part) >= 2:
            residue = re.sub(re.escape(brand_part), "", residue, flags=re.IGNORECASE)

    residue = re.sub(r"[^A-Za-z0-9一-龥]+", "", residue)
    return len(residue) >= 2


def product_direct_url(product: dict[str, Any]) -> str:
    for value in [
        product.get("official_url"),
        product.get("direct_url"),
        product.get("article_url"),
        product.get("url"),
        product.get("google_news_url"),
    ]:
        if is_evidence_url(value):
            return clean_url(value)

    for row in safe_list(product.get("coverage")):
        if isinstance(row, dict) and is_evidence_url(
            row.get("direct_url") or row.get("url") or row.get("google_news_url")
        ):
            return clean_url(row.get("direct_url") or row.get("url") or row.get("google_news_url"))
    return ""


def product_quality_reason(product: dict[str, Any]) -> str:
    product_name = clean_text(product.get("product_name"))
    brand = clean_text(product.get("brand"))
    source = clean_text(product.get("source"))
    url = product_direct_url(product)
    published_date = parse_date(product.get("published_date") or product.get("published_at"))
    verification = clean_text(product.get("verification"))
    evidence_status = clean_text(product.get("evidence_status"))

    if not clean_text(product.get("product_id")):
        return "missing_product_id"
    if not brand:
        return "missing_brand"
    if not product_name:
        return "missing_product_name"
    if not is_specific_product_name(product_name, brand):
        return "generic_product_name"
    if source in INVALID_SOURCE_NAMES:
        return "invalid_source"
    if not url:
        return "missing_direct_url"
    if not published_date:
        return "missing_date"
    if not (REPORT_START_DATE <= published_date <= REPORT_END_DATE):
        return "outside_window"
    trusted_single = bool(product.get("is_official")) or clean_text(product.get("source_tier")) in {
        "official", "tier_1", "tier_2"
    }
    if evidence_status and evidence_status not in {"verified", "media_confirmed"}:
        return "unverified_product"
    if verification and verification not in {"official", "multi_source", "trusted_media"}:
        return "insufficient_independent_evidence"
    if to_int(product.get("official_evidence_count"), 0) < 1 and to_int(product.get("credible_source_count"), 0) < 2:
        if clean_text(weekly_products.get("schema_version")) == "2.1" and not trusted_single:
            return "insufficient_independent_evidence"
    if clean_text(product.get("source_tier")) == "tier_4":
        return "low_quality_source"
    if to_int(product.get("confidence_score"), 0) < (52 if evidence_status == "media_confirmed" else 46):
        return "low_confidence"
    return ""


event_rejections = Counter()
eligible_events = []

for event in source_events:
    reason = event_quality_reason(event)
    if reason:
        event_rejections[reason] += 1
    else:
        eligible_events.append(event)

product_rejections = Counter()
eligible_products = []

for product in product_rows:
    reason = product_quality_reason(product)
    if reason:
        product_rejections[reason] += 1
    else:
        eligible_products.append(product)


# =========================================================
# 4. 候选排序与公开结构
# =========================================================

CATEGORY_BONUS = {
    "儿童与青少年": 10,
    "产品与科技": 9,
    "品牌与公司": 9,
    "电商与平台": 8,
    "渠道与零售": 8,
    "宏观与消费": 7,
    "研究与数据": 6,
    "户外与场景": 6,
    "行业动态": 4,
}


def event_selection_score(event: dict[str, Any]) -> int:
    score = to_int(event.get("editorial_score"), 0)
    score += CATEGORY_BONUS.get(clean_text(event.get("category")), 4)
    score += 9 if event_is_official(event) else 0
    score += 6 if to_int(event.get("source_count"), 0) >= 2 else 0
    score += 3 if event.get("status") == "new" else 1

    title = clean_text(event.get("title"))
    if any(word in title for word in [
        "儿童", "青少年", "童装", "童鞋", "校园运动", "开学季", "跑鞋", "篮球鞋", "运动品牌"
    ]):
        score += 10
    if any(word in title for word in ["餐饮", "外卖", "旅游攻略", "股价", "股票"]):
        score -= 18
    if re.search(r"\d+(?:\.\d+)?%", title):
        score += 5
    if re.search(r"\d+(?:\.\d+)?(?:亿|万|元|美元|港元|门|家)", title):
        score += 4

    return score


def event_evidence_text(event: dict[str, Any]) -> str:
    parts = [
        clean_text(event.get("title")),
        event_summary(event),
    ]

    for item in event_evidence_rows(event):
        parts.extend([
            clean_text(item.get("title")),
            clean_summary(item.get("summary")),
        ])

    return " ".join([x for x in parts if x])


def event_public(event: dict[str, Any]) -> dict[str, Any]:
    primary = event_primary_evidence(event)
    evidence = event_evidence_rows(event)
    return {
        "event_id": clean_text(event.get("event_id")),
        "title": clean_text(event.get("title")),
        "category": clean_text(event.get("category")) or "行业动态",
        "event_family": clean_text(event.get("event_family")),
        "reporting_period": clean_text(event.get("reporting_period")),
        "brands": unique_strings(safe_list(event.get("brands")), 5),
        "source": event_source(event),
        "url": event_url(event),
        "direct_url": event_url(event),
        "published_at": clean_text(primary.get("published_at") or event.get("published_at")),
        "published_date": event_date(event).isoformat() if event_date(event) else "",
        "status": clean_text(event.get("status")) or "new",
        "verification": clean_text(event.get("verification")) or "single_source",
        "is_official": event_is_official(event),
        "source_count": to_int(event.get("source_count"), 1),
        "direct_source_count": to_int(event.get("direct_source_count"), len(evidence)),
        "mention_count": to_int(event.get("mention_count"), 1),
        "editorial_score": to_int(event.get("editorial_score"), 0),
        "selection_score": event_selection_score(event),
        "summary_snippet": event_summary(event),
        "merged_event_ids": unique_strings(safe_list(event.get("merged_event_ids")), 30),
        "evidence": evidence[:12],
    }


def product_coverage_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    used = set()

    for row in safe_list(product.get("coverage")):
        if not isinstance(row, dict):
            continue
        url = clean_url(row.get("direct_url") or row.get("url") or row.get("google_news_url"))
        if not is_evidence_url(url) or url in used:
            continue
        used.add(url)
        output.append({
            "headline": clean_text(row.get("headline") or row.get("title")),
            "source": clean_text(row.get("source")),
            "source_tier": clean_text(row.get("source_tier")),
            "is_official": bool(row.get("is_official")),
            "url": url,
            "direct_url": url,
            "published_at": clean_text(row.get("published_at")),
            "published_date": clean_text(row.get("published_date")) or (
                parse_date(row.get("published_at")).isoformat() if parse_date(row.get("published_at")) else ""
            ),
        })

    if not output and product_direct_url(product):
        output.append({
            "headline": clean_text(product.get("headline")),
            "source": clean_text(product.get("source")),
            "source_tier": clean_text(product.get("source_tier")),
            "is_official": bool(product.get("is_official")),
            "url": product_direct_url(product),
            "direct_url": product_direct_url(product),
            "published_at": clean_text(product.get("published_at")),
            "published_date": clean_text(product.get("published_date")),
        })

    return output


def product_public(product: dict[str, Any]) -> dict[str, Any]:
    price = safe_dict(product.get("price"))
    coverage = product_coverage_rows(product)
    return {
        "product_id": clean_text(product.get("product_id")),
        "brand": clean_text(product.get("brand")),
        "product_name": clean_text(product.get("product_name")),
        "model_code": clean_text(product.get("model_code")),
        "category": clean_text(product.get("category")) or "商品趋势",
        "audience": clean_text(product.get("audience")),
        "scenarios": unique_strings(safe_list(product.get("scenarios")), 4),
        "release_date": clean_text(product.get("release_date")),
        "release_date_basis": clean_text(product.get("release_date_basis")),
        "price": {
            "value": price.get("value"),
            "currency": clean_text(price.get("currency")),
            "display": clean_text(price.get("display")),
            "basis": clean_text(price.get("basis")) or "not_disclosed",
        },
        "technologies": unique_strings(safe_list(product.get("technologies")), 10),
        "materials": unique_strings(safe_list(product.get("materials")), 8),
        "source": clean_text(product.get("source")),
        "url": product_direct_url(product),
        "direct_url": product_direct_url(product),
        "official_url": clean_url(product.get("official_url")) if is_direct_url(product.get("official_url")) else "",
        "image_url": valid_image_url(product.get("image_url")),
        "headline": clean_text(product.get("headline")),
        "published_at": clean_text(product.get("published_at")),
        "published_date": clean_text(product.get("published_date")),
        "verification": clean_text(product.get("verification")),
        "verification_reason": clean_text(product.get("verification_reason")),
        "evidence_status": clean_text(product.get("evidence_status")),
        "is_official": bool(product.get("is_official")),
        "confidence_score": to_int(product.get("confidence_score"), 0),
        "source_count": to_int(product.get("source_count"), len(coverage)),
        "direct_source_count": to_int(product.get("direct_source_count"), len(coverage)),
        "credible_source_count": to_int(product.get("credible_source_count"), 0),
        "official_evidence_count": to_int(product.get("official_evidence_count"), 0),
        "status": clean_text(product.get("status")) or "new",
        "first_seen": clean_text(product.get("first_seen")),
        "last_seen": clean_text(product.get("last_seen")),
        "evidence": safe_dict(product.get("evidence")),
        "coverage": coverage[:8],
    }


eligible_events = sorted(eligible_events, key=event_selection_score, reverse=True)
eligible_products = sorted(
    eligible_products,
    key=lambda x: (
        1 if x.get("is_official") else 0,
        to_int(x.get("confidence_score"), 0),
        clean_text(x.get("published_at")),
    ),
    reverse=True,
)

eligible_event_map = {clean_text(x.get("event_id")): x for x in eligible_events}
eligible_product_map = {clean_text(x.get("product_id")): x for x in eligible_products}


# =========================================================
# 5. 无AI时也可工作的规则编辑器
# =========================================================

def select_diverse_events(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    output = []
    brand_counter = Counter()
    category_counter = Counter()
    brand_family_used = set()

    for event in events:
        category = clean_text(event.get("category")) or "行业动态"
        brands = unique_strings(safe_list(event.get("brands")), 5)
        primary_brand = brands[0] if brands else ""
        event_family = clean_text(event.get("event_family")) or "other"
        brand_family_key = (primary_brand.lower(), event_family)

        if primary_brand and brand_counter[primary_brand] >= 2:
            continue
        if primary_brand and brand_family_key in brand_family_used:
            continue
        if category_counter[category] >= 2:
            continue

        output.append(event)
        if primary_brand:
            brand_counter[primary_brand] += 1
            brand_family_used.add(brand_family_key)
        category_counter[category] += 1

        if len(output) >= limit:
            break

    return output[:limit]


def fallback_weekly_thesis(events: list[dict[str, Any]], products: list[dict[str, Any]]) -> str:
    if events:
        first = clean_text(events[0].get("title"))
        second = clean_text(events[1].get("title")) if len(events) > 1 else ""
        product_note = "；具名产品仅收录已达到核验门槛的项目" if products else ""
        if second:
            return short_text(f"本周核心变化是{first}；同时关注{second}{product_note}。", 78)
        return short_text(f"本周核心变化是{first}{product_note}。", 78)

    return "本周有效资讯有限，周报以已核验事件和后续观察为主。"


def fallback_key_reason(event: dict[str, Any]) -> str:
    category = clean_text(event.get("category")) or "行业动态"
    verification = clean_text(event.get("verification"))
    status = "本周新事件" if event.get("status") == "new" else "上周事件后续"
    source_note = "且有官方来源" if verification == "official_source" else "且有多来源交叉报道" if verification == "multi_source" else ""
    return f"属于{category}的重要{status}{source_note}。"


def fallback_deep_dives(key_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in key_events:
        grouped[clean_text(event.get("category")) or "行业动态"].append(event)

    output = []
    for category, rows in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
        evidence_titles = [clean_text(x.get("title")) for x in rows[:3]]
        analysis = f"本周该方向的主要证据包括：{'；'.join(evidence_titles)}。"
        output.append({
            "headline": f"{category}：本周变化",
            "event_ids": [clean_text(x.get("event_id")) for x in rows[:3]],
            "analysis": short_text(analysis, 180),
        })
        if len(output) >= MAX_DEEP_DIVES:
            break

    return output


def fallback_watchlist(
    events: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []

    follow_ups = [x for x in events if x.get("status") == "follow_up"]
    for event in follow_ups[:3]:
        output.append({
            "title": short_text(event.get("title"), 38),
            "event_ids": [clean_text(event.get("event_id"))],
            "product_ids": [],
            "reason": "该事件已连续出现，下一周关注是否有官方数据或进一步动作。",
        })

    for product in products[:2]:
        output.append({
            "title": f"跟踪{product.get('brand', '')}{product.get('product_name', '')}",
            "event_ids": [],
            "product_ids": [clean_text(product.get("product_id"))],
            "reason": "继续核对中国市场发售信息、官方价格和产品技术资料。",
        })

    if not output and events:
        output.append({
            "title": "跟踪本周重点事件后续",
            "event_ids": [clean_text(x.get("event_id")) for x in events[:3]],
            "product_ids": [],
            "reason": "关注后续官方回应、渠道落地和数据披露。",
        })

    return output[:MAX_WATCHLIST]


rule_key_events = select_diverse_events(eligible_events, MAX_KEY_DEVELOPMENTS)
rule_product_selection = eligible_products[:MAX_PRODUCTS]


# =========================================================
# 6. DeepSeek：只允许返回候选ID
# =========================================================

def ai_event_candidates() -> list[dict[str, Any]]:
    output = []

    for event in eligible_events[:MAX_EVENT_CANDIDATES_FOR_AI]:
        public = event_public(event)
        output.append({
            "event_id": public["event_id"],
            "title": public["title"],
            "category": public["category"],
            "event_family": public["event_family"],
            "reporting_period": public["reporting_period"],
            "brands": public["brands"],
            "source": public["source"],
            "published_date": public["published_date"],
            "status": public["status"],
            "verification": public["verification"],
            "source_count": public["source_count"],
            "direct_source_count": public["direct_source_count"],
            "editorial_score": public["editorial_score"],
            "description": public["summary_snippet"],
            "evidence_titles": [x.get("title", "") for x in public.get("evidence", [])[:5]],
        })

    return output


def ai_product_candidates() -> list[dict[str, Any]]:
    output = []

    for product in eligible_products[:MAX_PRODUCT_CANDIDATES_FOR_AI]:
        public = product_public(product)
        output.append({
            "product_id": public["product_id"],
            "brand": public["brand"],
            "product_name": public["product_name"],
            "model_code": public["model_code"],
            "category": public["category"],
            "audience": public["audience"],
            "scenarios": public["scenarios"],
            "release_date": public["release_date"],
            "price": public["price"]["display"],
            "technologies": public["technologies"],
            "source": public["source"],
            "published_date": public["published_date"],
            "verification": public["verification"],
            "verification_reason": public["verification_reason"],
            "credible_source_count": public["credible_source_count"],
            "official_evidence_count": public["official_evidence_count"],
            "confidence_score": public["confidence_score"],
            "headline": public["headline"],
        })

    return output


AI_EVENT_CANDIDATES = ai_event_candidates()
AI_PRODUCT_CANDIDATES = ai_product_candidates()


def deepseek_prompt() -> str:
    return f"""
你是361°儿童事业部管理层周度行业情报编辑。

统计周期：{REPORT_START_DATE.isoformat()}至{REPORT_END_DATE.isoformat()}。

你的任务不是创造新闻，而是从候选事实中选择最值得阅读的内容并做简洁归纳。

必须遵守：
1. 只能使用下面提供的event_id和product_id，禁止创造任何新ID。
2. 不要输出或改写新闻标题；程序会用ID回填原始标题、日期、来源和链接。
3. 不得增加候选证据中没有出现的数字、品牌动作、产品功能、价格或结论。
4. 不要把报道篇数、编辑分数或资料完整度写成销量、搜索量或市场热度。
5. key_developments选择4至8项，并保持品牌、平台、商品、消费等方向适度分散；候选不足时可以少于4项，禁止凑数。
6. 同一品牌同一财务周期只能保留一个事件，不得把同一份财报的营收、利润、海外增长拆成多项。
7. deep_dives选择2至4个主题，每个主题必须绑定1至3个event_id。
8. product_selection最多6项；如果产品证据少，可以少选或不选，禁止凑数。
9. competitor_channel_ids和kids_consumer_ids只能来自事件候选，且不要重复key_developments已选事件。
10. 所有分析文字应说明“发生了什么、为什么值得关注、行业层面的变化”，不要写空泛经营口号。
11. 只输出严格JSON，不要Markdown，不要代码围栏，不要额外解释。

输出结构：
{{
  "weekly_thesis": "70字以内本周核心判断",
  "week_in_one_paragraph": "150字以内，概括本周最重要的变化",
  "key_developments": [
    {{
      "event_id": "evt_xxx",
      "reason": "60字以内，解释为什么进入本周重点"
    }}
  ],
  "deep_dives": [
    {{
      "headline": "主题标题，不是虚构事件标题",
      "event_ids": ["evt_xxx"],
      "analysis": "180字以内，只基于这些事件进行归纳"
    }}
  ],
  "product_selection": [
    {{
      "product_id": "prd_xxx",
      "reason": "70字以内，说明该具体商品的信息价值"
    }}
  ],
  "competitor_channel_ids": ["evt_xxx"],
  "kids_consumer_ids": ["evt_xxx"],
  "watchlist": [
    {{
      "title": "观察主题",
      "event_ids": ["evt_xxx"],
      "product_ids": ["prd_xxx"],
      "reason": "下一周具体观察什么"
    }}
  ],
  "next_week_focus": ["最多5条，每条50字以内"]
}}

事件候选：
{json.dumps(AI_EVENT_CANDIDATES, ensure_ascii=False)}

真实产品候选：
{json.dumps(AI_PRODUCT_CANDIDATES, ensure_ascii=False)}

本周品类证据计数（仅代表信息证据数量，不代表市场热度）：
{json.dumps(product_category_signals[:12], ensure_ascii=False)}
"""


def call_deepseek() -> tuple[dict[str, Any], str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

    if not api_key:
        return {}, "DEEPSEEK_API_KEY not found; deterministic fallback used"
    if not AI_EVENT_CANDIDATES:
        return {}, "No eligible event candidates; deterministic fallback used"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是严格基于证据工作的行业情报编辑。只能选择输入ID，不能编造新闻、产品、数字或链接。"
                    "只输出一个合法JSON对象。"
                ),
            },
            {"role": "user", "content": deepseek_prompt()},
        ],
        "temperature": 0.15,
        "max_tokens": 4200,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = ""

    for attempt in range(1, 3):
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers=headers,
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = extract_json_object(content)
            if parsed:
                return parsed, ""
            last_error = f"attempt {attempt}: invalid JSON response"
        except Exception as exc:
            last_error = f"attempt {attempt}: {repr(exc)}"

    return {}, last_error or "DeepSeek call failed"


# =========================================================
# 7. AI结果校验与规则结果合并
# =========================================================

def valid_event_ids(values: Any, limit: int | None = None) -> list[str]:
    output = []
    for value in safe_list(values):
        event_id = clean_text(value)
        if event_id in eligible_event_map and event_id not in output:
            output.append(event_id)
        if limit and len(output) >= limit:
            break
    return output


def valid_product_ids(values: Any, limit: int | None = None) -> list[str]:
    output = []
    for value in safe_list(values):
        product_id = clean_text(value)
        if product_id in eligible_product_map and product_id not in output:
            output.append(product_id)
        if limit and len(output) >= limit:
            break
    return output


def validate_key_developments(ai_data: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    used = set()
    brand_counter = Counter()
    category_counter = Counter()
    brand_family_used = set()

    def can_add(event: dict[str, Any]) -> bool:
        category = clean_text(event.get("category")) or "行业动态"
        brands = unique_strings(safe_list(event.get("brands")), 5)
        primary_brand = brands[0] if brands else ""
        family = clean_text(event.get("event_family")) or "other"
        if category_counter[category] >= 2:
            return False
        if primary_brand and brand_counter[primary_brand] >= 2:
            return False
        if primary_brand and (primary_brand.lower(), family) in brand_family_used:
            return False
        return True

    def register(event: dict[str, Any]) -> None:
        category = clean_text(event.get("category")) or "行业动态"
        brands = unique_strings(safe_list(event.get("brands")), 5)
        primary_brand = brands[0] if brands else ""
        family = clean_text(event.get("event_family")) or "other"
        category_counter[category] += 1
        if primary_brand:
            brand_counter[primary_brand] += 1
            brand_family_used.add((primary_brand.lower(), family))

    for row in safe_list(ai_data.get("key_developments")):
        if not isinstance(row, dict):
            continue
        event_id = clean_text(row.get("event_id"))
        if event_id not in eligible_event_map or event_id in used:
            continue

        event = eligible_event_map[event_id]
        if not can_add(event):
            continue
        reason = sanitize_grounded_text(row.get("reason"), event_evidence_text(event), 80)
        output.append({"event_id": event_id, "reason": reason or fallback_key_reason(event)})
        used.add(event_id)
        register(event)

        if len(output) >= MAX_KEY_DEVELOPMENTS:
            break

    fill_target = max(MIN_KEY_DEVELOPMENTS, len(output)) if ai_data else MAX_KEY_DEVELOPMENTS
    if len(output) >= fill_target:
        return output[:MAX_KEY_DEVELOPMENTS]

    for event in rule_key_events:
        event_id = clean_text(event.get("event_id"))
        if event_id in used:
            continue
        if not can_add(event):
            continue
        output.append({"event_id": event_id, "reason": fallback_key_reason(event)})
        used.add(event_id)
        register(event)
        if len(output) >= fill_target:
            break

    return output


def validate_deep_dives(ai_data: dict[str, Any], key_event_ids: list[str]) -> list[dict[str, Any]]:
    output = []

    for row in safe_list(ai_data.get("deep_dives")):
        if not isinstance(row, dict):
            continue

        event_ids = valid_event_ids(row.get("event_ids"), 3)
        if not event_ids:
            continue

        evidence = " ".join(event_evidence_text(eligible_event_map[x]) for x in event_ids)
        analysis = sanitize_grounded_text(row.get("analysis"), evidence, 220)
        headline = short_text(row.get("headline"), 38)

        if not headline or not analysis:
            continue

        output.append({
            "headline": headline,
            "event_ids": event_ids,
            "analysis": analysis,
        })

        if len(output) >= MAX_DEEP_DIVES:
            break

    if len(output) < 2:
        fallback_events = [eligible_event_map[x] for x in key_event_ids if x in eligible_event_map]
        for row in fallback_deep_dives(fallback_events):
            key = norm_key(row.get("headline"))
            if any(norm_key(x.get("headline")) == key for x in output):
                continue
            output.append(row)
            if len(output) >= min(2, MAX_DEEP_DIVES):
                break

    return output[:MAX_DEEP_DIVES]


def product_evidence_text(product: dict[str, Any]) -> str:
    public = product_public(product)
    return " ".join([
        public.get("headline", ""),
        public.get("product_name", ""),
        public.get("model_code", ""),
        " ".join(public.get("technologies", [])),
        " ".join(public.get("materials", [])),
        clean_text(public.get("price", {}).get("display")),
        public.get("release_date", ""),
        json.dumps(public.get("evidence", {}), ensure_ascii=False),
    ])


def validate_product_selection(ai_data: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    used = set()

    for row in safe_list(ai_data.get("product_selection")):
        if not isinstance(row, dict):
            continue
        product_id = clean_text(row.get("product_id"))
        if product_id not in eligible_product_map or product_id in used:
            continue

        product = eligible_product_map[product_id]
        reason = sanitize_grounded_text(row.get("reason"), product_evidence_text(product), 90)
        output.append({
            "product_id": product_id,
            "reason": reason or clean_text(product.get("verification_reason")) or "具名商品已达到核验门槛，进入本周产品雷达。",
        })
        used.add(product_id)

        if len(output) >= MAX_PRODUCTS:
            break

    if not ai_data:
        # 无AI时，上游products均已通过核验门槛，按资料完整度回填，不用随机商品补位。
        for product in eligible_products:
            product_id = clean_text(product.get("product_id"))
            if product_id in used:
                continue
            output.append({
                "product_id": product_id,
                "reason": clean_text(product.get("verification_reason")) or "具名商品已达到官方单源或两家独立可信来源的核验门槛。",
            })
            used.add(product_id)
            if len(output) >= MAX_PRODUCTS:
                break

    return output


def validate_watchlist(ai_data: dict[str, Any]) -> list[dict[str, Any]]:
    output = []

    for row in safe_list(ai_data.get("watchlist")):
        if not isinstance(row, dict):
            continue

        event_ids = valid_event_ids(row.get("event_ids"), 3)
        product_ids = valid_product_ids(row.get("product_ids"), 3)
        if not event_ids and not product_ids:
            continue

        evidence = " ".join(event_evidence_text(eligible_event_map[x]) for x in event_ids)
        evidence += " " + " ".join(product_evidence_text(eligible_product_map[x]) for x in product_ids)

        title = short_text(row.get("title"), 40)
        reason = sanitize_grounded_text(row.get("reason"), evidence, 100)
        if not title:
            continue

        output.append({
            "title": title,
            "event_ids": event_ids,
            "product_ids": product_ids,
            "reason": reason or "关注后续官方信息、渠道落地或产品资料补充。",
        })

        if len(output) >= MAX_WATCHLIST:
            break

    if not output:
        output = fallback_watchlist(eligible_events, eligible_products)

    return output[:MAX_WATCHLIST]


ai_data, ai_error = call_deepseek()
ai_used = bool(ai_data)

validated_key_rows = validate_key_developments(ai_data)
key_event_ids = [x["event_id"] for x in validated_key_rows]
validated_deep_dives = validate_deep_dives(ai_data, key_event_ids)
validated_product_rows = validate_product_selection(ai_data)

OWN_BRAND_MARKERS = ["361儿童", "361°儿童", "361度儿童", "361 Kids", "361度", "361°"]


def is_own_brand_event(event: dict[str, Any]) -> bool:
    brands = unique_strings(safe_list(event.get("brands")), 8)
    own_names = {"361", "361°", "361度", "361儿童", "361°儿童", "361度儿童", "361 kids"}
    if any(clean_text(brand).lower() in own_names for brand in brands):
        return True
    title = clean_text(event.get("title"))
    return any(marker.lower() in title.lower() for marker in OWN_BRAND_MARKERS)


competitor_channel_ids = [
    x for x in valid_event_ids(ai_data.get("competitor_channel_ids"), MAX_COMPETITOR_CHANNEL * 2)
    if x not in key_event_ids and not is_own_brand_event(eligible_event_map[x])
][:MAX_COMPETITOR_CHANNEL]
kids_consumer_ids = [
    x for x in valid_event_ids(ai_data.get("kids_consumer_ids"), MAX_KIDS_CONSUMER * 2)
    if x not in key_event_ids
][:MAX_KIDS_CONSUMER]

if not competitor_channel_ids:
    competitor_channel_ids = [
        clean_text(x.get("event_id"))
        for x in eligible_events
        if clean_text(x.get("category")) in ["品牌与公司", "电商与平台", "渠道与零售"]
        and clean_text(x.get("event_id")) not in key_event_ids
        and not is_own_brand_event(x)
    ][:MAX_COMPETITOR_CHANNEL]

if not kids_consumer_ids:
    kids_consumer_ids = [
        clean_text(x.get("event_id"))
        for x in eligible_events
        if clean_text(x.get("event_id")) not in key_event_ids
        and (
            clean_text(x.get("category")) == "儿童与青少年"
            or any("儿童" in clean_text(brand) for brand in safe_list(x.get("brands")))
        )
    ][:MAX_KIDS_CONSUMER]

kids_consumer_ids = [x for x in kids_consumer_ids if x not in competitor_channel_ids][:MAX_KIDS_CONSUMER]

validated_watchlist = validate_watchlist(ai_data)


# =========================================================
# 8. 物化输出：用ID回填原始事实
# =========================================================

key_developments = []
for row in validated_key_rows:
    event = event_public(eligible_event_map[row["event_id"]])
    event["editorial_reason"] = row["reason"]
    key_developments.append(event)

deep_dives = []
for row in validated_deep_dives:
    evidence_events = [event_public(eligible_event_map[x]) for x in row["event_ids"] if x in eligible_event_map]
    deep_divives_evidence = [
        {
            "event_id": x["event_id"],
            "title": x["title"],
            "source": x["source"],
            "url": x["url"],
            "published_date": x["published_date"],
        }
        for x in evidence_events
    ]
    deep_dives.append({
        "headline": row["headline"],
        "analysis": row["analysis"],
        "event_ids": row["event_ids"],
        "evidence": deep_divives_evidence,
    })

product_radar = []
for row in validated_product_rows:
    product = product_public(eligible_product_map[row["product_id"]])
    product["editorial_reason"] = row["reason"]
    product_radar.append(product)

image_counts = Counter(x.get("image_url") for x in product_radar if x.get("image_url"))
duplicate_images = {url for url, count in image_counts.items() if url and count > 1}
for product in product_radar:
    if product.get("image_url") in duplicate_images:
        product["image_url"] = ""

competitor_channel = [
    event_public(eligible_event_map[event_id])
    for event_id in competitor_channel_ids
    if event_id in eligible_event_map
]

kids_consumer = [
    event_public(eligible_event_map[event_id])
    for event_id in kids_consumer_ids
    if event_id in eligible_event_map
]


# =========================================================
# 9. 跟踪状态、矛盾核验和上周未出现事项
# =========================================================

def conflict_verification_queue() -> list[dict[str, Any]]:
    output = []

    for conflict in source_conflicts:
        event_ids = unique_strings(safe_list(conflict.get("event_ids")), 4)
        events = [event_map[x] for x in event_ids if x in event_map]

        output.append({
            "conflict_id": clean_text(conflict.get("conflict_id")),
            "reason": clean_text(conflict.get("reason")) or "相关报道存在相反表述，需要官方核验。",
            "events": [
                {
                    "event_id": clean_text(x.get("event_id")),
                    "title": clean_text(x.get("title")),
                    "source": event_source(x),
                    "url": event_url(x),
                    "published_date": event_date(x).isoformat() if event_date(x) else "",
                }
                for x in events
            ],
        })

    return output


def load_previous_analysis() -> dict[str, Any]:
    candidates = []

    for path in sorted(ARCHIVE_DIR.glob("weekly_analysis_*.json"))[-12:]:
        data = load_json(path, {})
        window = safe_dict(data.get("report_window")) if isinstance(data, dict) else {}
        prior_end = parse_date(window.get("end_date"))
        if prior_end and prior_end < REPORT_START_DATE:
            candidates.append((prior_end, data))

    if not candidates:
        return {}

    return sorted(candidates, key=lambda x: x[0])[-1][1]


def previous_items_not_seen(previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_titles = [clean_text(x.get("title")) for x in source_events]
    output = []

    for old in safe_list(previous.get("key_developments")):
        if not isinstance(old, dict):
            continue
        old_title = clean_text(old.get("title"))
        if not old_title:
            continue

        still_seen = any(title_similarity(old_title, current_title) >= 0.58 for current_title in current_titles)
        if still_seen:
            continue

        output.append({
            "event_id": clean_text(old.get("event_id")),
            "title": old_title,
            "source": clean_text(old.get("source")),
            "url": clean_url(old.get("url")),
            "last_seen": clean_text(old.get("published_date")),
            "note": "本周未检索到明确后续，不等同于事件已经结束。",
        })

        if len(output) >= 5:
            break

    return output


previous_analysis = load_previous_analysis()
not_seen_this_week = previous_items_not_seen(previous_analysis)
verification_queue = conflict_verification_queue()


# =========================================================
# 10. 本周主结论与观察清单
# =========================================================

all_selected_evidence = " ".join(
    [event_evidence_text(eligible_event_map[x]) for x in key_event_ids if x in eligible_event_map]
    + [product_evidence_text(eligible_product_map[x["product_id"]]) for x in validated_product_rows]
)

weekly_thesis = sanitize_grounded_text(
    ai_data.get("weekly_thesis"),
    all_selected_evidence,
    82,
) if ai_used else ""

if not weekly_thesis:
    weekly_thesis = fallback_weekly_thesis(rule_key_events, eligible_products)

week_in_one_paragraph = sanitize_grounded_text(
    ai_data.get("week_in_one_paragraph"),
    all_selected_evidence,
    180,
) if ai_used else ""

if not week_in_one_paragraph:
    selected_facts = [clean_text(x.get("title")) for x in key_developments[:3] if clean_text(x.get("title"))]
    if selected_facts:
        week_in_one_paragraph = short_text(
            f"本周已核验的主要变化包括：{'；'.join(selected_facts)}。"
            + (f"另有{len(product_radar)}项具名产品通过来源核验进入产品雷达。" if product_radar else "")
            + "证据不足或存在冲突的内容未进入核心结论。",
            180,
        )
    else:
        week_in_one_paragraph = "本周可核验的核心事件有限，证据不足内容未进入管理层结论。"

next_week_focus = []
for value in safe_list(ai_data.get("next_week_focus")):
    grounded = sanitize_grounded_text(value, all_selected_evidence, 60)
    if grounded:
        next_week_focus.append(grounded)
    if len(next_week_focus) >= 5:
        break

if not next_week_focus:
    next_week_focus = unique_strings(
        [clean_text(x.get("reason")) for x in validated_watchlist]
        + ["继续核验矛盾报道及单一来源事件的官方后续。"],
        5,
    )


# =========================================================
# 11. 来源目录
# =========================================================

def build_source_registry() -> list[dict[str, Any]]:
    rows = []
    used = set()

    def add(source_type: str, item_id: str, title: str, source: str, url: str, published_date: str) -> None:
        url = clean_url(url)
        if not is_evidence_url(url):
            return
        key = url
        if key in used:
            return
        used.add(key)
        rows.append({
            "type": source_type,
            "id": clean_text(item_id),
            "title": clean_text(title),
            "source": clean_text(source),
            "url": url,
            "published_date": clean_text(published_date),
        })

    for event in key_developments + competitor_channel + kids_consumer:
        add(
            "event",
            event.get("event_id", ""),
            event.get("title", ""),
            event.get("source", ""),
            event.get("url", ""),
            event.get("published_date", ""),
        )
        for evidence in safe_list(event.get("evidence")):
            if not isinstance(evidence, dict):
                continue
            evidence_date = parse_date(evidence.get("published_at"))
            add(
                "event_evidence",
                evidence.get("item_id", "") or event.get("event_id", ""),
                evidence.get("title", "") or event.get("title", ""),
                evidence.get("source", ""),
                evidence.get("url", ""),
                evidence_date.isoformat() if evidence_date else event.get("published_date", ""),
            )

    for dive in deep_dives:
        for evidence in safe_list(dive.get("evidence")):
            if isinstance(evidence, dict):
                add(
                    "event",
                    evidence.get("event_id", ""),
                    evidence.get("title", ""),
                    evidence.get("source", ""),
                    evidence.get("url", ""),
                    evidence.get("published_date", ""),
                )
                event_id = clean_text(evidence.get("event_id"))
                if event_id in eligible_event_map:
                    for row in event_evidence_rows(eligible_event_map[event_id]):
                        row_date = parse_date(row.get("published_at"))
                        add(
                            "event_evidence",
                            row.get("item_id", "") or event_id,
                            row.get("title", "") or evidence.get("title", ""),
                            row.get("source", ""),
                            row.get("url", ""),
                            row_date.isoformat() if row_date else evidence.get("published_date", ""),
                        )

    for product in product_radar:
        add(
            "product",
            product.get("product_id", ""),
            f"{product.get('brand', '')} {product.get('product_name', '')}",
            product.get("source", ""),
            product.get("url", ""),
            product.get("published_date", ""),
        )
        for coverage in safe_list(product.get("coverage")):
            if not isinstance(coverage, dict):
                continue
            add(
                "product_evidence",
                product.get("product_id", ""),
                coverage.get("headline", "") or f"{product.get('brand', '')} {product.get('product_name', '')}",
                coverage.get("source", ""),
                coverage.get("url", ""),
                coverage.get("published_date", "") or product.get("published_date", ""),
            )

    return rows


source_registry = build_source_registry()


def product_lead_public(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": clean_text(product.get("signal_id") or product.get("product_id")),
        "brand": clean_text(product.get("brand")),
        "product_name": clean_text(product.get("product_name")),
        "headline": clean_text(product.get("headline")),
        "source": clean_text(product.get("source")),
        "url": product_direct_url(product),
        "published_date": clean_text(product.get("published_date")),
        "lead_reason": clean_text(product.get("lead_reason")),
        "verification_reason": clean_text(product.get("verification_reason")),
        "note": clean_text(product.get("note")) or "证据尚未达到产品雷达门槛，仅供后续核验。",
    }


eligible_product_ids = {clean_text(x.get("product_id")) for x in eligible_products}
pending_product_leads = [
    product_lead_public(x)
    for x in product_leads[:20]
    if clean_text(x.get("product_id")) not in eligible_product_ids
    and product_direct_url(x)
    and is_specific_product_name(x.get("product_name"), x.get("brand"))
]


# =========================================================
# 12. 保存最终周报分析
# =========================================================

category_counts = Counter(clean_text(x.get("category")) or "行业动态" for x in eligible_events)
selected_status_counts = Counter(clean_text(x.get("status")) or "new" for x in key_developments)

output = {
    "schema_version": "3.1",
    "generated_at": GENERATED_AT.isoformat(timespec="minutes"),
    "report_window": {
        "start_date": REPORT_START_DATE.isoformat(),
        "end_date": REPORT_END_DATE.isoformat(),
        "timezone": TIMEZONE_NAME,
    },
    "editorial": {
        "weekly_thesis": weekly_thesis,
        "week_in_one_paragraph": week_in_one_paragraph,
        "next_week_focus": next_week_focus,
    },
    "key_developments": key_developments,
    "deep_dives": deep_dives,
    "product_radar": product_radar,
    "competitor_channel": competitor_channel,
    "kids_consumer": kids_consumer,
    "watchlist": validated_watchlist,
    "tracking": {
        "new_selected": [x for x in key_developments if x.get("status") == "new"],
        "follow_up_selected": [x for x in key_developments if x.get("status") == "follow_up"],
        "verification_queue": verification_queue,
        "product_leads_pending_verification": pending_product_leads[:8],
        "not_seen_this_week": not_seen_this_week,
        "note": "‘本周未出现’只表示检索期内没有明确后续，不代表事件已结束。",
    },
    "source_registry": source_registry,
    "data_quality": {
        "ai_used": ai_used,
        "ai_error": ai_error,
        "source_schema_version": clean_text(weekly_sources.get("schema_version")),
        "product_schema_version": clean_text(weekly_products.get("schema_version")),
        "raw_event_count": len(source_events_raw),
        "coalesced_event_count": len(source_events),
        "eligible_event_count": len(eligible_events),
        "selected_event_count": len(key_developments),
        "raw_product_count": len(product_rows),
        "product_lead_count": len(product_leads),
        "eligible_product_count": len(eligible_products),
        "selected_product_count": len(product_radar),
        "conflict_count": len(verification_queue),
        "source_link_count": len(source_registry),
        "selected_event_direct_link_count": sum(1 for x in key_developments if is_direct_url(x.get("url"))),
        "selected_product_direct_link_count": sum(1 for x in product_radar if is_direct_url(x.get("url"))),
        "event_rejections": dict(event_rejections),
        "product_rejections": dict(product_rejections),
        "eligible_categories": dict(category_counts),
        "selected_status": dict(selected_status_counts),
        "quality_notes": [
            "AI只能返回已有event_id/product_id，原始标题、日期、来源和链接由程序回填。",
            "冲突事件不会进入已确认重点，而是进入核验队列。",
            "同一品牌同一财务周期在分析层再次合并，避免一份财报被拆成多条重点。",
            "产品优先采用官方单源或至少两家独立可信来源；单一可信媒体报道可标记为媒体确认进入雷达。",
            "产品资料不足时允许产品雷达为空，不使用随机商品、通用品类名或占位图片补位。",
            "核心事件、产品雷达和来源目录优先保留原文直链；解析失败时允许Google News中转链接作为可点击证据。",
            "所有分数仅用于编辑和资料完整度判断，不代表销量或市场热度。",
        ],
    },
    "supporting_signals": {
        "product_categories": product_category_signals[:12],
        "product_leads": pending_product_leads[:20],
        "product_media_signals": product_media_signals[:30],
    },
    "input_files": {
        "weekly_sources": str(SOURCE_FILE),
        "weekly_products": str(PRODUCT_FILE),
    },
}

content = json.dumps(output, ensure_ascii=False, indent=2)
archive_file = ARCHIVE_DIR / (
    f"weekly_analysis_{REPORT_START_DATE.isoformat()}_{REPORT_END_DATE.isoformat()}.json"
)

temp_file = OUTPUT_FILE.with_suffix(".tmp")
temp_file.write_text(content, encoding="utf-8")
temp_file.replace(OUTPUT_FILE)
archive_file.write_text(content, encoding="utf-8")

print(f"weekly analysis saved: {OUTPUT_FILE}")
print(f"weekly analysis archived: {archive_file}")
print(f"AI used: {ai_used} | AI error: {ai_error or 'none'}")
print(
    f"events raw/coalesced/eligible/selected: "
    f"{len(source_events_raw)}/{len(source_events)}/{len(eligible_events)}/{len(key_developments)}"
)
print(f"products raw/eligible/selected: {len(product_rows)}/{len(eligible_products)}/{len(product_radar)}")
print(f"product leads pending verification: {len(pending_product_leads)}")
print(f"deep dives: {len(deep_dives)} | conflicts: {len(verification_queue)} | source links: {len(source_registry)}")

print("\nSelected developments:")
for index, event in enumerate(key_developments, start=1):
    print(
        f"{index}. [{event['status']}] [{event['verification']}] "
        f"{event['title']} | {event['source']}"
    )
