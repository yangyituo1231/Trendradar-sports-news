from __future__ import annotations

import json
import os
import re

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
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

MIN_EVENT_SCORE = 35
MAX_EVENT_CANDIDATES_FOR_AI = 55
MAX_PRODUCT_CANDIDATES_FOR_AI = 24
MAX_KEY_DEVELOPMENTS = 8
MIN_KEY_DEVELOPMENTS = 5
MAX_DEEP_DIVES = 4
MAX_PRODUCTS = 8
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
source_events = [x for x in safe_list(weekly_sources.get("events")) if isinstance(x, dict)]
source_conflicts = [x for x in safe_list(weekly_sources.get("conflict_groups")) if isinstance(x, dict)]
product_rows = [x for x in safe_list(weekly_products.get("products")) if isinstance(x, dict)]
product_media_signals = [x for x in safe_list(weekly_products.get("media_signals")) if isinstance(x, dict)]
product_category_signals = [x for x in safe_list(weekly_products.get("category_signals")) if isinstance(x, dict)]

item_map = {clean_text(x.get("id")): x for x in source_items if clean_text(x.get("id"))}
event_map = {clean_text(x.get("event_id")): x for x in source_events if clean_text(x.get("event_id"))}
product_map = {clean_text(x.get("product_id")): x for x in product_rows if clean_text(x.get("product_id"))}


# =========================================================
# 3. 事件和产品质量门槛
# =========================================================

INVALID_SOURCE_NAMES = {"", "公开资讯", "Google", "Google News", "网络资讯", "综合网络"}


def event_representative_item(event: dict[str, Any]) -> dict[str, Any]:
    representative_id = clean_text(event.get("representative_id"))
    if representative_id and representative_id in item_map:
        return item_map[representative_id]

    for item_id in safe_list(event.get("item_ids")):
        if clean_text(item_id) in item_map:
            return item_map[clean_text(item_id)]

    return {}


def event_url(event: dict[str, Any]) -> str:
    representative = event_representative_item(event)
    return (
        clean_url(representative.get("direct_url"))
        or clean_url(representative.get("url"))
        or clean_url(event.get("url"))
        or clean_url(representative.get("google_news_url"))
    )


def event_source(event: dict[str, Any]) -> str:
    representative = event_representative_item(event)
    return clean_text(representative.get("source") or event.get("source"))


def event_date(event: dict[str, Any]) -> date | None:
    representative = event_representative_item(event)
    return parse_date(
        representative.get("published_date")
        or representative.get("published_at")
        or event.get("published_at")
    )


def event_is_official(event: dict[str, Any]) -> bool:
    representative = event_representative_item(event)
    return bool(representative.get("is_official") or event.get("verification") == "official_source")


def event_quality_reason(event: dict[str, Any]) -> str:
    title = clean_text(event.get("title"))
    source = event_source(event)
    url = event_url(event)
    published_date = event_date(event)

    if not clean_text(event.get("event_id")):
        return "missing_event_id"
    if not title:
        return "missing_title"
    if source in INVALID_SOURCE_NAMES:
        return "invalid_source"
    if not url:
        return "missing_url"
    if not published_date:
        return "missing_date"
    if not (REPORT_START_DATE <= published_date <= REPORT_END_DATE):
        return "outside_window"
    if to_int(event.get("editorial_score"), 0) < MIN_EVENT_SCORE:
        return "low_editorial_score"
    if event.get("conflict_flag"):
        return "unresolved_conflict"
    return ""


def product_quality_reason(product: dict[str, Any]) -> str:
    product_name = clean_text(product.get("product_name"))
    brand = clean_text(product.get("brand"))
    source = clean_text(product.get("source"))
    url = clean_url(product.get("official_url") or product.get("article_url") or product.get("google_news_url"))
    published_date = parse_date(product.get("published_date") or product.get("published_at"))

    if not clean_text(product.get("product_id")):
        return "missing_product_id"
    if not brand:
        return "missing_brand"
    if not product_name:
        return "missing_product_name"
    if source in INVALID_SOURCE_NAMES:
        return "invalid_source"
    if not url:
        return "missing_url"
    if not published_date:
        return "missing_date"
    if not (REPORT_START_DATE <= published_date <= REPORT_END_DATE):
        return "outside_window"
    if to_int(product.get("confidence_score"), 0) < 46:
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
    if re.search(r"\d+(?:\.\d+)?%", title):
        score += 5
    if re.search(r"\d+(?:\.\d+)?(?:亿|万|元|美元|港元|门|家)", title):
        score += 4

    return score


def event_evidence_text(event: dict[str, Any]) -> str:
    representative = event_representative_item(event)
    cluster_items = [item_map.get(clean_text(x), {}) for x in safe_list(event.get("item_ids"))]
    parts = [
        clean_text(event.get("title")),
        clean_text(representative.get("meta_description")),
    ]

    for item in cluster_items:
        parts.extend([
            clean_text(item.get("title")),
            clean_text(item.get("meta_description")),
        ])

    return " ".join([x for x in parts if x])


def event_public(event: dict[str, Any]) -> dict[str, Any]:
    representative = event_representative_item(event)
    return {
        "event_id": clean_text(event.get("event_id")),
        "title": clean_text(event.get("title")),
        "category": clean_text(event.get("category")) or "行业动态",
        "brands": unique_strings(safe_list(event.get("brands")), 5),
        "source": event_source(event),
        "url": event_url(event),
        "published_at": clean_text(representative.get("published_at") or event.get("published_at")),
        "published_date": clean_text(representative.get("published_date")) or (
            event_date(event).isoformat() if event_date(event) else ""
        ),
        "status": clean_text(event.get("status")) or "new",
        "verification": clean_text(event.get("verification")) or "single_source",
        "is_official": event_is_official(event),
        "source_count": to_int(event.get("source_count"), 1),
        "mention_count": to_int(event.get("mention_count"), 1),
        "editorial_score": to_int(event.get("editorial_score"), 0),
        "selection_score": event_selection_score(event),
        "summary_snippet": short_text(representative.get("meta_description"), 240),
    }


def product_public(product: dict[str, Any]) -> dict[str, Any]:
    price = safe_dict(product.get("price"))
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
            "display": clean_text(price.get("display")) or "未披露",
            "basis": clean_text(price.get("basis")) or "not_disclosed",
        },
        "technologies": unique_strings(safe_list(product.get("technologies")), 10),
        "materials": unique_strings(safe_list(product.get("materials")), 8),
        "source": clean_text(product.get("source")),
        "url": clean_url(product.get("official_url") or product.get("article_url") or product.get("google_news_url")),
        "official_url": clean_url(product.get("official_url")),
        "image_url": clean_url(product.get("image_url")),
        "headline": clean_text(product.get("headline")),
        "published_at": clean_text(product.get("published_at")),
        "published_date": clean_text(product.get("published_date")),
        "verification": clean_text(product.get("verification")),
        "is_official": bool(product.get("is_official")),
        "confidence_score": to_int(product.get("confidence_score"), 0),
        "status": clean_text(product.get("status")) or "new",
        "first_seen": clean_text(product.get("first_seen")),
        "last_seen": clean_text(product.get("last_seen")),
        "evidence": safe_dict(product.get("evidence")),
        "coverage": safe_list(product.get("coverage"))[:6],
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

    for event in events:
        category = clean_text(event.get("category")) or "行业动态"
        brands = unique_strings(safe_list(event.get("brands")), 5)
        primary_brand = brands[0] if brands else ""

        if primary_brand and brand_counter[primary_brand] >= 2:
            continue
        if category_counter[category] >= 3:
            continue

        output.append(event)
        if primary_brand:
            brand_counter[primary_brand] += 1
        category_counter[category] += 1

        if len(output) >= limit:
            break

    if len(output) < min(limit, MIN_KEY_DEVELOPMENTS):
        used = {x.get("event_id") for x in output}
        for event in events:
            if event.get("event_id") in used:
                continue
            output.append(event)
            used.add(event.get("event_id"))
            if len(output) >= min(limit, MIN_KEY_DEVELOPMENTS):
                break

    return output[:limit]


def fallback_weekly_thesis(events: list[dict[str, Any]], products: list[dict[str, Any]]) -> str:
    categories = Counter(clean_text(x.get("category")) or "行业动态" for x in events[:12])
    top_categories = [name for name, _ in categories.most_common(3)]
    new_count = sum(1 for x in events[:12] if x.get("status") == "new")

    if top_categories:
        category_text = "、".join(top_categories)
        product_text = f"，并出现{len(products)}项具名产品证据" if products else ""
        return short_text(
            f"本周有效变化主要集中在{category_text}，其中{new_count}项为首次出现{product_text}。",
            78,
        )

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
        representative = event_representative_item(event)
        output.append({
            "event_id": public["event_id"],
            "title": public["title"],
            "category": public["category"],
            "brands": public["brands"],
            "source": public["source"],
            "published_date": public["published_date"],
            "status": public["status"],
            "verification": public["verification"],
            "source_count": public["source_count"],
            "editorial_score": public["editorial_score"],
            "description": short_text(representative.get("meta_description"), 260),
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
5. key_developments选择5至8项，并保持品牌、平台、商品、消费等方向适度分散。
6. deep_dives选择3至4个主题，每个主题必须绑定1至3个event_id。
7. product_selection最多8项；如果产品证据少，可以少选或不选，禁止凑数。
8. competitor_channel_ids和kids_consumer_ids只能来自事件候选。
9. 所有分析文字应说明“发生了什么、为什么值得关注、行业层面的变化”，不要写空泛经营口号。
10. 只输出严格JSON，不要Markdown，不要代码围栏，不要额外解释。

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

    for row in safe_list(ai_data.get("key_developments")):
        if not isinstance(row, dict):
            continue
        event_id = clean_text(row.get("event_id"))
        if event_id not in eligible_event_map or event_id in used:
            continue

        event = eligible_event_map[event_id]
        reason = sanitize_grounded_text(row.get("reason"), event_evidence_text(event), 80)
        output.append({"event_id": event_id, "reason": reason or fallback_key_reason(event)})
        used.add(event_id)

        if len(output) >= MAX_KEY_DEVELOPMENTS:
            break

    for event in rule_key_events:
        event_id = clean_text(event.get("event_id"))
        if event_id in used:
            continue
        output.append({"event_id": event_id, "reason": fallback_key_reason(event)})
        used.add(event_id)
        if len(output) >= MAX_KEY_DEVELOPMENTS:
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

    if len(output) < 3:
        fallback_events = [eligible_event_map[x] for x in key_event_ids if x in eligible_event_map]
        for row in fallback_deep_dives(fallback_events):
            key = norm_key(row.get("headline"))
            if any(norm_key(x.get("headline")) == key for x in output):
                continue
            output.append(row)
            if len(output) >= min(3, MAX_DEEP_DIVES):
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
            "reason": reason or "具备可核验的品牌、产品名、日期和来源，进入本周产品雷达。",
        })
        used.add(product_id)

        if len(output) >= MAX_PRODUCTS:
            break

    # 产品不强制补满，只补充高完整度或官方产品。
    for product in eligible_products:
        product_id = clean_text(product.get("product_id"))
        if product_id in used:
            continue
        if not product.get("is_official") and to_int(product.get("confidence_score"), 0) < 62:
            continue
        output.append({
            "product_id": product_id,
            "reason": "产品资料具备较高完整度或来自官方渠道，进入本周产品雷达。",
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

competitor_channel_ids = valid_event_ids(ai_data.get("competitor_channel_ids"), MAX_COMPETITOR_CHANNEL)
kids_consumer_ids = valid_event_ids(ai_data.get("kids_consumer_ids"), MAX_KIDS_CONSUMER)

if not competitor_channel_ids:
    competitor_channel_ids = [
        clean_text(x.get("event_id"))
        for x in eligible_events
        if clean_text(x.get("category")) in ["品牌与公司", "电商与平台", "渠道与零售"]
    ][:MAX_COMPETITOR_CHANNEL]

if not kids_consumer_ids:
    kids_consumer_ids = [
        clean_text(x.get("event_id"))
        for x in eligible_events
        if clean_text(x.get("category")) == "儿童与青少年"
        or any("儿童" in clean_text(brand) for brand in safe_list(x.get("brands")))
    ][:MAX_KIDS_CONSUMER]

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
    selected_categories = unique_strings([x.get("category") for x in key_developments], 4)
    selected_brands = unique_strings([brand for x in key_developments for brand in safe_list(x.get("brands"))], 5)
    week_in_one_paragraph = short_text(
        f"本周有效资讯主要覆盖{'、'.join(selected_categories) or '行业动态'}；"
        f"涉及{'、'.join(selected_brands) or '多个行业主体'}。"
        f"已筛选{len(key_developments)}项重点变化和{len(product_radar)}项具名产品证据，"
        "矛盾或证据不足的内容已单独进入核验队列。",
        180,
    )

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
        if not url:
            return
        key = (url, clean_text(title))
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

    for product in product_radar:
        add(
            "product",
            product.get("product_id", ""),
            f"{product.get('brand', '')} {product.get('product_name', '')}",
            product.get("source", ""),
            product.get("url", ""),
            product.get("published_date", ""),
        )

    return rows


source_registry = build_source_registry()


# =========================================================
# 12. 保存最终周报分析
# =========================================================

category_counts = Counter(clean_text(x.get("category")) or "行业动态" for x in eligible_events)
selected_status_counts = Counter(clean_text(x.get("status")) or "new" for x in key_developments)

output = {
    "schema_version": "3.0",
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
        "not_seen_this_week": not_seen_this_week,
        "note": "‘本周未出现’只表示检索期内没有明确后续，不代表事件已结束。",
    },
    "source_registry": source_registry,
    "data_quality": {
        "ai_used": ai_used,
        "ai_error": ai_error,
        "source_schema_version": clean_text(weekly_sources.get("schema_version")),
        "product_schema_version": clean_text(weekly_products.get("schema_version")),
        "raw_event_count": len(source_events),
        "eligible_event_count": len(eligible_events),
        "selected_event_count": len(key_developments),
        "raw_product_count": len(product_rows),
        "eligible_product_count": len(eligible_products),
        "selected_product_count": len(product_radar),
        "conflict_count": len(verification_queue),
        "source_link_count": len(source_registry),
        "event_rejections": dict(event_rejections),
        "product_rejections": dict(product_rejections),
        "eligible_categories": dict(category_counts),
        "selected_status": dict(selected_status_counts),
        "quality_notes": [
            "AI只能返回已有event_id/product_id，原始标题、日期、来源和链接由程序回填。",
            "冲突事件不会进入已确认重点，而是进入核验队列。",
            "产品资料不足时允许产品雷达为空，不使用随机商品补位。",
            "所有分数仅用于编辑和资料完整度判断，不代表销量或市场热度。",
        ],
    },
    "supporting_signals": {
        "product_categories": product_category_signals[:12],
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
print(f"events raw/eligible/selected: {len(source_events)}/{len(eligible_events)}/{len(key_developments)}")
print(f"products raw/eligible/selected: {len(product_rows)}/{len(eligible_products)}/{len(product_radar)}")
print(f"deep dives: {len(deep_dives)} | conflicts: {len(verification_queue)} | source links: {len(source_registry)}")

print("\nSelected developments:")
for index, event in enumerate(key_developments, start=1):
    print(
        f"{index}. [{event['status']}] [{event['verification']}] "
        f"{event['title']} | {event['source']}"
    )
