from __future__ import annotations

import html
import json
import re

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


# =========================================================
# 0. 文件配置
# =========================================================

TIMEZONE_NAME = "Asia/Shanghai"
LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

WEEKLY_DIR = Path("output/weekly")
ANALYSIS_FILE = WEEKLY_DIR / "weekly_analysis.json"
OUTPUT_HTML = WEEKLY_DIR / "weekly_report.html"

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# 1. 基础工具
# =========================================================

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"load json error: {path} {repr(exc)}")
        return default


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\n", " ").replace("\u200b", " ").strip()
    return re.sub(r"\s+", " ", text)


def esc(value: Any) -> str:
    return html.escape(clean_text(value), quote=True)


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
    host = host_of(value)
    if not host:
        return False
    blocked = ["news.google.com", "google.com", "consent.google.com", "accounts.google.com"]
    return not any(host == item or host.endswith("." + item) for item in blocked)


def valid_image_url(value: Any) -> str:
    url = clean_url(value)
    host = host_of(url)
    path = urlparse(url).path.lower() if url else ""
    full = f"{host}{path}"

    if not url or not host:
        return ""
    if any(
        host == item or host.endswith("." + item)
        for item in ["google.com", "googleusercontent.com", "gstatic.com", "ggpht.com", "news.google.com"]
    ):
        return ""
    if path.endswith((".svg", ".ico", ".gif")):
        return ""
    if any(token in full for token in ["logo", "icon", "favicon", "avatar", "placeholder", "sprite", "default"]):
        return ""
    return url


GOOGLE_BOILERPLATE = [
    "Comprehensive up-to-date news coverage",
    "aggregated from sources all over the world by Google News",
    "Google News provides comprehensive",
]


def clean_summary(value: Any) -> str:
    text = clean_text(value)
    if any(marker.lower() in text.lower() for marker in GOOGLE_BOILERPLATE):
        return ""
    return text


def short_text(value: Any, length: int) -> str:
    text = clean_text(value)
    if len(text) <= length:
        return text
    return text[:length].rstrip("，。；：,.;:") + "..."


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def format_date(value: Any, fallback: str = "") -> str:
    text = clean_text(value)
    if not text:
        return fallback

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return f"{dt.month:02d}月{dt.day:02d}日"
    except Exception:
        pass

    try:
        dt = datetime.strptime(text[:10], "%Y-%m-%d")
        return f"{dt.month:02d}月{dt.day:02d}日"
    except Exception:
        return text[:10] or fallback


def full_date(value: Any, fallback: str = "") -> str:
    text = clean_text(value)
    if not text:
        return fallback
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y年%m月%d日")
    except Exception:
        pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y年%m月%d日")
    except Exception:
        return text[:10] or fallback


def external_link(url: Any, label: Any, css_class: str = "") -> str:
    link = clean_url(url) if is_direct_url(url) else ""
    text = esc(label)
    class_attr = f' class="{esc(css_class)}"' if css_class else ""

    if not link:
        return text

    return (
        f'<a{class_attr} href="{esc(link)}" target="_blank" '
        f'rel="noopener noreferrer">{text}<span class="link-mark" aria-hidden="true">&#8599;&#65038;</span></a>'
    )


def compact_week_label(start: Any, end: Any) -> str:
    start_text = clean_text(start)
    end_text = clean_text(end)
    try:
        start_dt = datetime.strptime(start_text[:10], "%Y-%m-%d")
        end_dt = datetime.strptime(end_text[:10], "%Y-%m-%d")
        if start_dt.year == end_dt.year:
            return f"{start_dt:%Y.%m.%d} — {end_dt:%m.%d}"
        return f"{start_dt:%Y.%m.%d} — {end_dt:%Y.%m.%d}"
    except Exception:
        return f"{start_text} — {end_text}".strip(" —")


def compact_datetime(value: Any) -> str:
    text = clean_text(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return text.replace("T", " ")[:16]


def item_identity(item: dict[str, Any]) -> str:
    return clean_text(item.get("event_id")) or clean_text(item.get("product_id")) or clean_text(item.get("title"))


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    used = set()
    for item in items:
        key = re.sub(r"\W+", "", item_identity(item).lower())
        if not key or key in used:
            continue
        used.add(key)
        output.append(item)
    return output


def status_label(value: Any) -> str:
    mapping = {
        "new": "本周新增",
        "follow_up": "持续跟踪",
    }
    return mapping.get(clean_text(value), "本周记录")


def verification_label(value: Any, is_official: bool = False) -> str:
    if is_official:
        return "官方来源"
    mapping = {
        "official_source": "官方来源",
        "official": "官方来源",
        "multi_source": "多源交叉",
        "trusted_media": "可信媒体",
        "single_source": "单一来源",
        "media": "媒体报道",
    }
    return mapping.get(clean_text(value), "来源可查")


# =========================================================
# 2. 读取新分析结构
# =========================================================

analysis = load_json(ANALYSIS_FILE, {})

if not isinstance(analysis, dict) or not analysis:
    raise SystemExit(f"Missing or invalid weekly analysis: {ANALYSIS_FILE}")

schema_version = clean_text(analysis.get("schema_version"))
if schema_version and not schema_version.startswith("3"):
    print(f"WARNING: expected weekly_analysis schema 3.x, got {schema_version}")

report_window = safe_dict(analysis.get("report_window"))
editorial = safe_dict(analysis.get("editorial"))
data_quality = safe_dict(analysis.get("data_quality"))
tracking = safe_dict(analysis.get("tracking"))

key_developments = dedupe_items([x for x in safe_list(analysis.get("key_developments")) if isinstance(x, dict)])
deep_dives = [x for x in safe_list(analysis.get("deep_dives")) if isinstance(x, dict)]
product_radar = dedupe_items([x for x in safe_list(analysis.get("product_radar")) if isinstance(x, dict)])
competitor_channel = dedupe_items([x for x in safe_list(analysis.get("competitor_channel")) if isinstance(x, dict)])
kids_consumer = dedupe_items([x for x in safe_list(analysis.get("kids_consumer")) if isinstance(x, dict)])
watchlist = [x for x in safe_list(analysis.get("watchlist")) if isinstance(x, dict)]
source_registry = []
seen_source_urls = set()
for source_row in safe_list(analysis.get("source_registry")):
    if not isinstance(source_row, dict):
        continue
    source_url = clean_url(source_row.get("url"))
    if not is_direct_url(source_url) or source_url in seen_source_urls:
        continue
    seen_source_urls.add(source_url)
    source_registry.append(source_row)

new_selected = [x for x in safe_list(tracking.get("new_selected")) if isinstance(x, dict)]
follow_up_selected = [x for x in safe_list(tracking.get("follow_up_selected")) if isinstance(x, dict)]
verification_queue = [x for x in safe_list(tracking.get("verification_queue")) if isinstance(x, dict)]
product_leads_pending = [
    x for x in safe_list(tracking.get("product_leads_pending_verification")) if isinstance(x, dict)
]
not_seen_this_week = [x for x in safe_list(tracking.get("not_seen_this_week")) if isinstance(x, dict)]

start_date = clean_text(report_window.get("start_date"))
end_date = clean_text(report_window.get("end_date"))
generated_at = clean_text(analysis.get("generated_at")) or datetime.now(LOCAL_TZ).isoformat(timespec="minutes")

week_label = compact_week_label(start_date, end_date)
generated_label = compact_datetime(generated_at)
weekly_thesis = clean_summary(editorial.get("weekly_thesis")) or "本周暂无通过质量门槛的核心判断。"
week_paragraph = clean_summary(editorial.get("week_in_one_paragraph"))
next_week_focus = [clean_text(x) for x in safe_list(editorial.get("next_week_focus")) if clean_text(x)]

key_ids = {clean_text(x.get("event_id")) for x in key_developments if clean_text(x.get("event_id"))}
key_titles = {re.sub(r"\W+", "", clean_text(x.get("title")).lower()) for x in key_developments if clean_text(x.get("title"))}
competitor_unique = [
    x for x in competitor_channel
    if (
        (not clean_text(x.get("event_id")) or clean_text(x.get("event_id")) not in key_ids)
        and re.sub(r"\W+", "", clean_text(x.get("title")).lower()) not in key_titles
    )
]
competitor_ids = {clean_text(x.get("event_id")) for x in competitor_unique if clean_text(x.get("event_id"))}
competitor_titles = {re.sub(r"\W+", "", clean_text(x.get("title")).lower()) for x in competitor_unique if clean_text(x.get("title"))}
kids_unique = [
    x for x in kids_consumer
    if (not clean_text(x.get("event_id")) or clean_text(x.get("event_id")) not in key_ids)
    and (not clean_text(x.get("event_id")) or clean_text(x.get("event_id")) not in competitor_ids)
    and re.sub(r"\W+", "", clean_text(x.get("title")).lower()) not in key_titles
    and re.sub(r"\W+", "", clean_text(x.get("title")).lower()) not in competitor_titles
]
has_landscape = bool(competitor_unique or kids_unique)


# =========================================================
# 3. 通用渲染组件
# =========================================================

def render_empty(title: str, description: str) -> str:
    return f"""
    <div class="empty-state" role="status">
      <p class="empty-title">{esc(title)}</p>
      <p>{esc(description)}</p>
    </div>
    """


def render_event_meta(event: dict[str, Any], show_status: bool = True) -> str:
    parts = []

    if show_status:
        status = clean_text(event.get("status")) or "new"
        parts.append(
            f'<span class="status status-{esc(status)}">{esc(status_label(status))}</span>'
        )

    category = clean_text(event.get("category"))
    if category:
        parts.append(f'<span class="meta-label">{esc(category)}</span>')

    verification = verification_label(event.get("verification"), bool(event.get("is_official")))
    parts.append(f'<span class="meta-label">{esc(verification)}</span>')

    source_count = max(to_int(event.get("direct_source_count"), 0), to_int(event.get("source_count"), 0))
    if source_count >= 2:
        parts.append(f'<span class="meta-label evidence-badge">{source_count} 条独立来源</span>')

    return "".join(parts)


def render_developments() -> str:
    if not key_developments:
        return render_empty(
            "本周暂无通过核验的重点事件",
            "系统不会用旧新闻或低质量内容补足数量，请检查采集结果和来源状态。",
        )

    rows = []

    for index, event in enumerate(key_developments, start=1):
        title = clean_text(event.get("title")) or "未命名事件"
        source = clean_text(event.get("source")) or "来源未注明"
        published_date = format_date(event.get("published_date") or event.get("published_at"), "日期未注明")
        reason = clean_text(event.get("editorial_reason"))
        summary = clean_summary(event.get("summary_snippet"))
        brand_text = " / ".join([clean_text(x) for x in safe_list(event.get("brands")) if clean_text(x)])

        context_parts = [source, published_date]
        if brand_text:
            context_parts.insert(0, brand_text)

        rows.append(f"""
        <article class="change-row" id="event-{esc(event.get('event_id'))}">
          <div class="change-index" aria-label="编辑序号 {index}">{index:02d}</div>
          <div class="change-main">
            <div class="change-meta">{render_event_meta(event)}</div>
            <h3>{external_link(event.get('url'), title)}</h3>
            <p class="source-line">{esc(' · '.join(context_parts))}</p>
            {f'<p class="event-summary">{esc(summary)}</p>' if summary else ''}
            {f'<p class="editor-note"><span>入选理由</span>{esc(reason)}</p>' if reason else ''}
          </div>
        </article>
        """)

    return "".join(rows)


def render_deep_dives() -> str:
    if not deep_dives:
        return render_empty(
            "本周未形成可靠深读主题",
            "当可交叉验证的证据不足时，本栏目保持为空。",
        )

    rows = []

    for index, dive in enumerate(deep_dives, start=1):
        evidence_rows = []

        for evidence in safe_list(dive.get("evidence")):
            if not isinstance(evidence, dict):
                continue
            title = clean_text(evidence.get("title"))
            if not title:
                continue
            source_date = " · ".join([
                x for x in [
                    clean_text(evidence.get("source")),
                    format_date(evidence.get("published_date")),
                ] if x
            ])
            evidence_rows.append(f"""
              <li>
                <span>{external_link(evidence.get('url'), title)}</span>
                {f'<small>{esc(source_date)}</small>' if source_date else ''}
              </li>
            """)

        rows.append(f"""
        <article class="deep-article">
          <div class="deep-number">深读 {index}</div>
          <h3>{esc(dive.get('headline') or '本周主题')}</h3>
          <p class="deep-analysis">{esc(dive.get('analysis'))}</p>
          {f'<div class="evidence"><p>依据</p><ul>{"".join(evidence_rows)}</ul></div>' if evidence_rows else ''}
        </article>
        """)

    return "".join(rows)


def render_product_facts(product: dict[str, Any]) -> str:
    price = safe_dict(product.get("price"))
    facts = []

    def add(label: str, value: Any) -> None:
        text = clean_text(value)
        if text:
            facts.append(f"<div><dt>{esc(label)}</dt><dd>{esc(text)}</dd></div>")

    add("品类", product.get("category"))
    add("人群", product.get("audience"))
    add("发售日", product.get("release_date"))
    add("官方价格", price.get("display"))
    add("款号", product.get("model_code"))

    return f'<dl class="product-facts">{"".join(facts)}</dl>' if facts else ""


def render_products() -> str:
    if not product_radar:
        return render_empty(
            "本周暂无通过证据门槛的具名产品",
            "缺少明确产品名、品牌、日期或可点击来源的内容不会进入产品雷达，也不会使用随机商品补位。",
        )

    rows = []

    for product in product_radar:
        image_url = valid_image_url(product.get("image_url"))
        brand = clean_text(product.get("brand"))
        name = clean_text(product.get("product_name")) or "具名产品"
        title = f"{brand} {name}".strip()
        technologies = [clean_text(x) for x in safe_list(product.get("technologies")) if clean_text(x)]
        materials = [clean_text(x) for x in safe_list(product.get("materials")) if clean_text(x)]
        scenarios = [clean_text(x) for x in safe_list(product.get("scenarios")) if clean_text(x)]
        tags = technologies[:5] + [x for x in materials[:2] if x not in technologies] + [x for x in scenarios[:2] if x not in technologies]
        evidence_count = max(
            to_int(product.get("direct_source_count"), 0),
            to_int(product.get("credible_source_count"), 0),
        )
        source_line = " · ".join([
            x for x in [
                clean_text(product.get("source")),
                format_date(product.get("published_date") or product.get("published_at")),
                verification_label(product.get("verification"), bool(product.get("is_official"))),
                f"{evidence_count} 条原文证据" if evidence_count >= 2 else "",
            ] if x
        ])

        media_html = ""
        media_class = "no-media"
        if image_url:
            media_class = "has-media"
            media_html = f"""
            <figure class="product-media">
              <img src="{esc(image_url)}" alt="{esc(title)}" loading="lazy" referrerpolicy="no-referrer"
                onerror="this.parentElement.hidden=true;this.closest('.product-row').classList.remove('has-media');this.closest('.product-row').classList.add('no-media')">
            </figure>
            """

        rows.append(f"""
        <article class="product-row {media_class}" id="product-{esc(product.get('product_id'))}">
          {media_html}
          <div class="product-copy">
            <div class="product-kicker">
              <span>{esc(status_label(product.get('status')))}</span>
              <span>{esc(product.get('category') or '产品动态')}</span>
            </div>
            <h3>{external_link(product.get('url'), title)}</h3>
            <p class="source-line">{esc(source_line)}</p>
            {render_product_facts(product)}
            {f'<div class="term-list">{"".join(f"<span>{esc(tag)}</span>" for tag in tags)}</div>' if tags else ''}
            {f'<p class="editor-note"><span>信息价值</span>{esc(product.get("editorial_reason"))}</p>' if clean_text(product.get('editorial_reason')) else ''}
          </div>
        </article>
        """)

    return "".join(rows)


def render_compact_events(events: list[dict[str, Any]], empty_title: str) -> str:
    if not events:
        return render_empty(empty_title, "相关重点若已进入‘本周变化’，这里不重复展示。")

    rows = []
    for event in events:
        rows.append(f"""
        <article class="compact-event">
          <div>{render_event_meta(event, show_status=False)}</div>
          <h3>{external_link(event.get('url'), event.get('title') or '未命名事件')}</h3>
          <p>{esc(event.get('source'))} · {esc(format_date(event.get('published_date') or event.get('published_at')))}</p>
        </article>
        """)
    return "".join(rows)


def render_tracking_list(items: list[dict[str, Any]], empty_text: str) -> str:
    if not items:
        return f'<p class="tracking-empty">{esc(empty_text)}</p>'

    rows = []
    for item in items:
        title = clean_text(item.get("title")) or "未命名事项"
        rows.append(f"""
        <li>
          <span>{external_link(item.get('url'), title)}</span>
          <small>{esc(item.get('source'))}{' · ' if item.get('source') else ''}{esc(format_date(item.get('published_date') or item.get('last_seen')))}</small>
        </li>
        """)
    return f'<ul class="tracking-list">{"".join(rows)}</ul>'


def render_product_leads() -> str:
    if not product_leads_pending:
        return '<p class="tracking-empty">暂无待补充第二来源或官方来源的具名商品线索。</p>'

    rows = []
    for item in product_leads_pending[:6]:
        brand = clean_text(item.get("brand"))
        product_name = clean_text(item.get("product_name"))
        headline = clean_text(item.get("headline"))
        title = " ".join(x for x in [brand, product_name] if x) or headline or "待核验商品线索"
        context = " · ".join(
            x for x in [
                clean_text(item.get("source")),
                format_date(item.get("published_date")),
            ] if x
        )
        note = clean_text(item.get("verification_reason") or item.get("note"))
        rows.append(f"""
        <li>
          <span>{external_link(item.get('url'), title)}</span>
          {f'<small>{esc(context)}</small>' if context else ''}
          {f'<em>{esc(note)}</em>' if note else ''}
        </li>
        """)

    return f'<ul class="lead-list">{"".join(rows)}</ul>'


def render_conflicts() -> str:
    if not verification_queue:
        return ""

    rows = []
    for conflict in verification_queue:
        event_rows = []
        for event in safe_list(conflict.get("events")):
            if not isinstance(event, dict):
                continue
            event_rows.append(f"""
            <li>
              {external_link(event.get('url'), event.get('title') or '待核验报道')}
              <small>{esc(event.get('source'))} · {esc(format_date(event.get('published_date')))}</small>
            </li>
            """)

        rows.append(f"""
        <article class="conflict-item">
          <p class="conflict-reason">{esc(conflict.get('reason') or '相关报道存在相反表述，需要进一步核验。')}</p>
          {f'<ul>{"".join(event_rows)}</ul>' if event_rows else ''}
        </article>
        """)

    return f"""
    <div class="verification-alert" role="alert">
      <div class="alert-title">待核验信息</div>
      <p class="alert-intro">以下内容存在相反表述，未进入本周已确认重点。</p>
      {''.join(rows)}
    </div>
    """


def render_watchlist() -> str:
    rows = watchlist

    if not rows and next_week_focus:
        rows = [
            {"title": f"观察方向 {index}", "reason": value}
            for index, value in enumerate(next_week_focus, start=1)
        ]

    if not rows:
        return render_empty("暂无下周观察项", "本周没有形成具备证据基础的持续观察主题。")

    output = []
    for index, row in enumerate(rows[:6], start=1):
        reference_count = len(safe_list(row.get("event_ids"))) + len(safe_list(row.get("product_ids")))
        output.append(f"""
        <article class="watch-row">
          <span class="watch-index">{index:02d}</span>
          <div>
            <h3>{esc(row.get('title') or f'观察方向 {index}')}</h3>
            <p>{esc(row.get('reason'))}</p>
            {f'<small>关联本周证据 {reference_count} 项</small>' if reference_count else ''}
          </div>
        </article>
        """)

    return "".join(output)


def render_sources() -> str:
    if not source_registry:
        return render_empty(
            "暂无可点击来源",
            "请检查周度资讯池是否包含有效原文链接。",
        )

    rows = []
    type_map = {
        "event": "事件",
        "event_evidence": "事件证据",
        "product": "产品",
        "product_evidence": "产品证据",
    }
    for index, source in enumerate(source_registry, start=1):
        source_type = type_map.get(clean_text(source.get("type")), "来源")
        rows.append(f"""
        <tr>
          <td>{index:02d}</td>
          <td><span class="source-type">{esc(source_type)}</span></td>
          <td>{external_link(source.get('url'), source.get('title') or '查看原文')}</td>
          <td>{esc(source.get('source'))}</td>
          <td>{esc(format_date(source.get('published_date')))}</td>
        </tr>
        """)

    return f"""
    <div class="table-wrap">
      <table class="source-table">
        <thead>
          <tr><th>#</th><th>类型</th><th>原文</th><th>来源</th><th>日期</th></tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def render_quality_notes() -> str:
    notes = [clean_text(x) for x in safe_list(data_quality.get("quality_notes")) if clean_text(x)]
    note_html = "".join(f"<li>{esc(note)}</li>" for note in notes)
    ai_label = "AI辅助编辑已启用" if data_quality.get("ai_used") else "本期采用规则编辑兜底"

    metrics = [
        ("原始事件", data_quality.get("raw_event_count", 0)),
        ("合并后事件", data_quality.get("coalesced_event_count", 0)),
        ("通过门槛", data_quality.get("eligible_event_count", 0)),
        ("本期重点", data_quality.get("selected_event_count", len(key_developments))),
        ("已核验产品", data_quality.get("selected_product_count", len(product_radar))),
        ("原文链接", data_quality.get("source_link_count", len(source_registry))),
    ]

    metric_html = "".join(
        f'<div><dt>{esc(label)}</dt><dd>{to_int(value)}</dd></div>'
        for label, value in metrics
    )

    return f"""
    <details class="methodology">
      <summary>查看数据口径与质量说明</summary>
      <div class="method-body">
        <p class="method-status">{esc(ai_label)}</p>
        <dl class="quality-metrics">{metric_html}</dl>
        {f'<ul>{note_html}</ul>' if note_html else ''}
      </div>
    </details>
    """


# =========================================================
# 4. 页面正文
# =========================================================

low_evidence_notice = ""
if len(key_developments) < 4:
    low_evidence_notice = f"""
    <div class="quality-notice">
      本周只有 {len(key_developments)} 项事件通过质量门槛，系统没有使用旧新闻或低质量内容补足数量。
    </div>
    """

new_count = len(new_selected) if new_selected else sum(1 for x in key_developments if x.get("status") == "new")
follow_count = len(follow_up_selected) if follow_up_selected else sum(1 for x in key_developments if x.get("status") == "follow_up")

landscape_nav = '<a href="#landscape">竞品与儿童消费</a>' if has_landscape else ""
landscape_section = f"""
    <section class="report-section" id="landscape">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">04 / Market landscape</p>
          <div>
            <h2>竞品、渠道与儿童消费</h2>
            <p class="section-intro">对已进入“本周变化”的内容不做重复堆叠，这里只保留额外线索。</p>
          </div>
        </div>
        <div class="split-view">
          <div class="split-column">
            <h3 class="column-title">竞品与渠道</h3>
            {render_compact_events(competitor_unique, '暂无额外竞品与渠道线索')}
          </div>
          <div class="split-column">
            <h3 class="column-title">儿童与消费</h3>
            {render_compact_events(kids_unique, '暂无额外儿童消费线索')}
          </div>
        </div>
      </div>
    </section>
""" if has_landscape else ""

html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light">
  <meta name="description" content="361°儿童运动产业周度情报：基于可核验来源整理本周品牌、产品、渠道与消费变化。">
  <title>361°儿童｜运动产业周度情报｜{esc(start_date)}—{esc(end_date)}</title>
  <style>
    :root {{
      --orange: #f36c21;
      --orange-dark: #c94b0b;
      --orange-soft: #fff1e8;
      --ink: #17201d;
      --ink-soft: #35413c;
      --muted: #68736e;
      --line: #d9dfdb;
      --line-dark: #aeb8b2;
      --wash: #f5f7f4;
      --paper: #ffffff;
      --link: #245e7c;
      --danger: #a62b24;
      --danger-soft: #fff2f0;
      --display: "Arial Narrow", "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      --sans: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      --mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    }}

    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: var(--sans);
      font-size: 16px;
      line-height: 1.68;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }}

    a {{ color: var(--link); text-decoration-thickness: 1px; text-underline-offset: 0.18em; overflow-wrap: anywhere; }}
    a:hover {{ color: var(--orange-dark); }}
    a:focus-visible, button:focus-visible, summary:focus-visible {{
      outline: 3px solid rgba(243,108,33,.38);
      outline-offset: 4px;
      border-radius: 2px;
    }}

    .skip-link {{
      position: fixed;
      left: 16px;
      top: -80px;
      z-index: 100;
      background: var(--ink);
      color: #fff;
      padding: 10px 14px;
      transition: top .2s ease;
    }}
    .skip-link:focus {{ top: 16px; }}

    .shell {{ width: min(1220px, calc(100% - 64px)); margin: 0 auto; }}

    .masthead {{
      border-top: 8px solid var(--orange);
      padding: 40px 0 38px;
    }}
    .masthead-top {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 24px;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--line-dark);
    }}
    .brand-line {{
      font-family: var(--mono);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .13em;
      text-transform: uppercase;
      color: var(--orange-dark);
    }}
    .edition {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      text-align: right;
    }}
    .masthead-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr);
      gap: clamp(34px, 6vw, 82px);
      padding-top: 34px;
      align-items: end;
    }}
    h1 {{
      margin: 0;
      font-family: var(--display);
      font-size: clamp(46px, 5.4vw, 68px);
      font-weight: 900;
      letter-spacing: -.06em;
      line-height: 1.02;
    }}
    .deck {{
      margin: 18px 0 0;
      max-width: 680px;
      color: var(--muted);
      font-size: 15px;
      letter-spacing: .02em;
    }}
    .week-stamp {{ border-left: 4px solid var(--orange); padding-left: 22px; }}
    .week-stamp p {{ margin: 0; }}
    .week-stamp .week {{
      font-family: var(--display);
      font-size: clamp(20px, 2.1vw, 28px);
      font-weight: 850;
      line-height: 1.35;
    }}
    .week-stamp .generated {{ margin-top: 10px; color: var(--muted); font-size: 12px; }}

    .thesis {{
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      gap: 34px;
      margin-top: 44px;
      padding-top: 24px;
      border-top: 1px solid var(--line-dark);
    }}
    .thesis-label {{
      font-family: var(--mono);
      color: var(--orange-dark);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .1em;
      text-transform: uppercase;
    }}
    .thesis blockquote {{
      margin: 0;
      font-family: var(--display);
      font-size: clamp(24px, 2.9vw, 36px);
      font-weight: 850;
      line-height: 1.36;
      letter-spacing: -.025em;
    }}
    .thesis-summary {{ margin: 22px 0 0; color: var(--ink-soft); max-width: 820px; }}
    .evidence-line {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 24px;
      margin-top: 24px;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 12px;
    }}
    .evidence-line strong {{ color: var(--ink); }}

    .section-nav {{
      position: sticky;
      top: 0;
      z-index: 40;
      background: rgba(255,255,255,.94);
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .nav-inner {{ display: flex; align-items: center; gap: 28px; min-height: 52px; overflow-x: auto; scrollbar-width: none; }}
    .nav-inner::-webkit-scrollbar {{ display: none; }}
    .nav-inner a {{
      flex: 0 0 auto;
      color: var(--ink-soft);
      font-size: 13px;
      font-weight: 700;
      text-decoration: none;
    }}
    .nav-inner a:hover {{ color: var(--orange-dark); }}
    .nav-spacer {{ flex: 1 1 auto; }}
    .print-button {{
      flex: 0 0 auto;
      appearance: none;
      border: 0;
      background: transparent;
      color: var(--muted);
      font-family: var(--sans);
      font-size: 12px;
      cursor: pointer;
      padding: 8px 0;
    }}
    .print-button:hover {{ color: var(--orange-dark); }}

    main {{ display: block; }}
    .report-section {{ padding: 62px 0; border-bottom: 1px solid var(--line); scroll-margin-top: 70px; }}
    .section-heading {{
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      gap: 34px;
      margin-bottom: 34px;
      align-items: start;
    }}
    .section-kicker {{
      margin: 0;
      color: var(--orange-dark);
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    .section-heading h2 {{
      margin: 0;
      font-family: var(--display);
      font-size: clamp(31px, 3.5vw, 44px);
      font-weight: 900;
      letter-spacing: -.045em;
      line-height: 1.12;
    }}
    .section-heading .section-intro {{ margin: 12px 0 0; max-width: 760px; color: var(--muted); }}

    .quality-notice {{
      margin-bottom: 28px;
      border-left: 4px solid var(--orange);
      background: var(--orange-soft);
      padding: 14px 18px;
      color: var(--orange-dark);
      font-size: 14px;
      font-weight: 650;
    }}

    .change-list {{ position: relative; border-left: 2px solid var(--orange); }}
    .change-row {{
      display: grid;
      grid-template-columns: 52px minmax(0, 1fr);
      gap: 20px;
      position: relative;
      padding: 0 0 30px 26px;
      margin-left: -2px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 28px;
    }}
    .change-row:last-child {{ margin-bottom: 0; padding-bottom: 0; border-bottom: 0; }}
    .change-row::before {{
      content: "";
      position: absolute;
      left: -6px;
      top: 8px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--paper);
      border: 2px solid var(--orange);
    }}
    .change-index {{
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 700;
      color: var(--orange-dark);
      padding-top: 4px;
    }}
    .change-meta {{ display: flex; flex-wrap: wrap; gap: 7px 9px; margin-bottom: 12px; }}
    .status, .meta-label {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      font-size: 11px;
      line-height: 1.2;
      color: var(--muted);
      border-radius: 3px;
    }}
    .status {{ border-color: var(--orange); color: var(--orange-dark); font-weight: 800; }}
    .status-follow_up {{ border-color: var(--line-dark); color: var(--ink-soft); }}
    .evidence-badge {{ border-color: #f5b184; background: var(--orange-soft); color: var(--orange-dark); font-weight: 750; }}
    .link-mark {{
      display: inline-block;
      margin-left: .34em;
      color: var(--orange-dark);
      font-family: Arial, sans-serif;
      font-size: .72em;
      font-weight: 700;
      line-height: 1;
      vertical-align: .12em;
    }}
    .change-main h3 {{
      margin: 0;
      font-family: var(--display);
      font-size: clamp(22px, 2.4vw, 29px);
      font-weight: 850;
      line-height: 1.34;
      letter-spacing: -.018em;
      overflow-wrap: anywhere;
    }}
    .change-main h3 a {{ color: var(--ink); text-decoration: none; }}
    .change-main h3 a:hover {{ color: var(--orange-dark); text-decoration: underline; }}
    .source-line {{ margin: 9px 0 0; color: var(--muted); font-size: 12px; }}
    .event-summary {{ margin: 17px 0 0; color: var(--ink-soft); max-width: 820px; }}
    .editor-note {{
      margin: 17px 0 0;
      color: var(--ink-soft);
      font-size: 14px;
    }}
    .editor-note span {{
      margin-right: 10px;
      color: var(--orange-dark);
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .06em;
    }}

    .deep-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 44px; row-gap: 44px; }}
    .deep-article {{ padding-top: 18px; border-top: 3px solid var(--ink); }}
    .deep-number {{ color: var(--orange-dark); font-family: var(--mono); font-size: 11px; font-weight: 800; letter-spacing: .08em; }}
    .deep-article h3 {{ margin: 13px 0 0; font-family: var(--display); font-size: 26px; font-weight: 850; line-height: 1.3; letter-spacing: -.025em; }}
    .deep-analysis {{ margin: 18px 0 0; color: var(--ink-soft); }}
    .evidence {{ margin-top: 24px; padding-top: 15px; border-top: 1px solid var(--line); }}
    .evidence > p {{ margin: 0 0 8px; color: var(--muted); font-family: var(--mono); font-size: 11px; font-weight: 800; }}
    .evidence ul {{ margin: 0; padding: 0; list-style: none; }}
    .evidence li {{ margin-top: 8px; font-size: 13px; line-height: 1.5; }}
    .evidence li small {{ display: block; color: var(--muted); font-size: 11px; }}

    .product-list {{ border-top: 1px solid var(--line-dark); }}
    .product-row {{
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      gap: 32px;
      padding: 28px 0;
      border-bottom: 1px solid var(--line);
    }}
    .product-row.no-media {{ grid-template-columns: minmax(0, 1fr); }}
    .product-media {{ margin: 0; align-self: start; aspect-ratio: 4 / 3; overflow: hidden; background: var(--wash); }}
    .product-media img {{ width: 100%; height: 100%; display: block; object-fit: cover; }}
    .product-kicker {{ display: flex; flex-wrap: wrap; gap: 8px 14px; color: var(--orange-dark); font-family: var(--mono); font-size: 11px; font-weight: 800; }}
    .product-copy h3 {{ margin: 10px 0 0; font-family: var(--display); font-size: 27px; font-weight: 850; line-height: 1.3; overflow-wrap: anywhere; }}
    .product-copy h3 a {{ color: var(--ink); text-decoration: none; }}
    .product-copy h3 a:hover {{ color: var(--orange-dark); text-decoration: underline; }}
    .product-facts {{ display: flex; flex-wrap: wrap; gap: 12px 30px; margin: 20px 0 0; }}
    .product-facts div {{ min-width: 100px; }}
    .product-facts dt {{ color: var(--muted); font-size: 11px; }}
    .product-facts dd {{ margin: 1px 0 0; color: var(--ink); font-size: 14px; font-weight: 700; }}
    .term-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 18px; }}
    .term-list span {{ border-bottom: 1px solid var(--line-dark); color: var(--ink-soft); font-size: 12px; padding: 2px 0; margin-right: 12px; }}

    .split-view {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 48px; }}
    .split-column + .split-column {{ border-left: 1px solid var(--line); padding-left: 48px; }}
    .split-column h3.column-title {{ margin: 0 0 24px; color: var(--orange-dark); font-family: var(--mono); font-size: 12px; letter-spacing: .09em; }}
    .compact-event {{ padding: 20px 0; border-top: 1px solid var(--line); }}
    .compact-event:first-of-type {{ border-top-color: var(--line-dark); }}
    .compact-event h3 {{ margin: 9px 0 0; font-family: var(--display); font-size: 20px; font-weight: 800; line-height: 1.4; }}
    .compact-event h3 a {{ color: var(--ink); text-decoration: none; }}
    .compact-event h3 a:hover {{ color: var(--orange-dark); text-decoration: underline; }}
    .compact-event p {{ margin: 7px 0 0; color: var(--muted); font-size: 11px; }}

    .tracking-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px 48px; }}
    .tracking-block {{ border-top: 2px solid var(--ink); padding-top: 15px; }}
    .tracking-block h3 {{ margin: 0; font-size: 16px; }}
    .tracking-count {{ color: var(--orange-dark); font-family: var(--mono); font-size: 12px; }}
    .tracking-list {{ margin: 12px 0 0; padding: 0; list-style: none; }}
    .tracking-list li {{ padding: 10px 0; border-top: 1px solid var(--line); font-size: 13px; line-height: 1.5; }}
    .tracking-list li small {{ display: block; color: var(--muted); font-size: 10px; margin-top: 3px; }}
    .tracking-empty {{ margin: 13px 0 0; color: var(--muted); font-size: 13px; }}
    .tracking-summary {{ margin: 13px 0 0; color: var(--ink-soft); font-size: 13px; }}
    .lead-list {{ margin: 12px 0 0; padding: 0; list-style: none; }}
    .lead-list li {{ padding: 11px 0; border-top: 1px solid var(--line); font-size: 13px; line-height: 1.5; }}
    .lead-list small, .lead-list em {{ display: block; margin-top: 3px; color: var(--muted); font-size: 10px; font-style: normal; }}
    .lead-list em {{ color: var(--orange-dark); }}

    .verification-alert {{ margin-top: 44px; background: var(--danger-soft); border-left: 4px solid var(--danger); padding: 24px 26px; }}
    .alert-title {{ color: var(--danger); font-family: var(--mono); font-size: 12px; font-weight: 800; letter-spacing: .08em; }}
    .alert-intro {{ margin: 7px 0 0; color: #73302c; }}
    .conflict-item {{ margin-top: 20px; padding-top: 17px; border-top: 1px solid #edc8c4; }}
    .conflict-reason {{ margin: 0; font-weight: 700; color: #672720; }}
    .conflict-item ul {{ margin: 10px 0 0; padding-left: 20px; }}
    .conflict-item li {{ margin-top: 6px; font-size: 13px; }}
    .conflict-item small {{ display: block; color: #8c5a56; font-size: 10px; }}

    .watch-list {{ border-top: 1px solid var(--line-dark); }}
    .watch-row {{ display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 22px; padding: 25px 0; border-bottom: 1px solid var(--line); }}
    .watch-index {{ color: var(--orange-dark); font-family: var(--mono); font-size: 13px; font-weight: 800; }}
    .watch-row h3 {{ margin: 0; font-family: var(--display); font-size: 21px; font-weight: 850; }}
    .watch-row p {{ margin: 8px 0 0; color: var(--ink-soft); }}
    .watch-row small {{ display: block; margin-top: 8px; color: var(--muted); font-size: 11px; }}

    .table-wrap {{ overflow-x: auto; border-top: 1px solid var(--line-dark); }}
    .source-table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    .source-table th, .source-table td {{ padding: 14px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    .source-table th {{ color: var(--muted); font-family: var(--mono); font-size: 10px; letter-spacing: .07em; }}
    .source-table td {{ font-size: 13px; }}
    .source-table td:first-child {{ color: var(--orange-dark); font-family: var(--mono); }}
    .source-type {{ color: var(--muted); font-size: 11px; }}

    .methodology {{ margin-top: 34px; border-top: 1px solid var(--line); }}
    .methodology summary {{ cursor: pointer; padding: 17px 0; color: var(--muted); font-size: 13px; font-weight: 700; }}
    .method-body {{ padding: 10px 0 24px; }}
    .method-status {{ color: var(--orange-dark); font-weight: 700; }}
    .quality-metrics {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); margin: 18px 0 0; }}
    .quality-metrics div {{ background: var(--paper); padding: 13px; }}
    .quality-metrics dt {{ color: var(--muted); font-size: 10px; }}
    .quality-metrics dd {{ margin: 3px 0 0; font-family: var(--display); font-size: 24px; font-weight: 850; }}
    .method-body ul {{ margin: 20px 0 0; padding-left: 20px; color: var(--muted); font-size: 12px; }}

    .empty-state {{ border-top: 1px solid var(--line-dark); padding: 28px 0; max-width: 760px; }}
    .empty-state p {{ margin: 0; color: var(--muted); }}
    .empty-state .empty-title {{ color: var(--ink); font-family: var(--display); font-size: 21px; font-weight: 850; margin-bottom: 6px; }}

    footer {{ padding: 36px 0 52px; color: var(--muted); font-size: 11px; }}
    .footer-inner {{ display: flex; justify-content: space-between; gap: 24px; padding-top: 18px; border-top: 1px solid var(--line); }}

    @media (max-width: 900px) {{
      .shell {{ width: min(100% - 40px, 760px); }}
      .masthead-grid, .thesis, .section-heading {{ grid-template-columns: 1fr; gap: 24px; }}
      .masthead-grid {{ align-items: start; }}
      .week-stamp {{ margin-top: 10px; }}
      .thesis {{ margin-top: 44px; }}
      .deep-grid, .split-view, .tracking-grid {{ grid-template-columns: 1fr; }}
      .split-column + .split-column {{ border-left: 0; border-top: 1px solid var(--line); padding: 34px 0 0; }}
      .quality-metrics {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}

    @media (max-width: 640px) {{
      body {{ font-size: 15px; }}
      .shell {{ width: min(100% - 28px, 560px); }}
      .masthead {{ padding: 28px 0 32px; border-top-width: 6px; }}
      .masthead-top {{ align-items: flex-start; flex-direction: column; gap: 9px; padding-bottom: 20px; }}
      .edition {{ text-align: left; }}
      .masthead-grid {{ padding-top: 24px; }}
      h1 {{ font-size: 40px; }}
      .thesis {{ margin-top: 34px; }}
      .thesis blockquote {{ font-size: 23px; }}
      .evidence-line {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px 16px; }}
      .nav-inner {{ gap: 20px; }}
      .nav-spacer, .print-button {{ display: none; }}
      .report-section {{ padding: 44px 0; }}
      .section-heading {{ margin-bottom: 26px; }}
      .section-heading h2 {{ font-size: 33px; }}
      .change-row {{ grid-template-columns: 38px minmax(0, 1fr); gap: 12px; padding-left: 18px; padding-bottom: 28px; margin-bottom: 26px; }}
      .change-main h3 {{ font-size: 22px; }}
      .product-row {{ grid-template-columns: 1fr; gap: 20px; }}
      .product-media {{ max-width: 340px; }}
      .product-copy h3 {{ font-size: 24px; }}
      .quality-metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .footer-inner {{ flex-direction: column; gap: 8px; }}
    }}

    @media print {{
      .section-nav, .print-button, .skip-link {{ display: none !important; }}
      .shell {{ width: 100%; }}
      body {{ color: #000; }}
      a {{ color: inherit; text-decoration: none; }}
      .masthead, .report-section {{ break-inside: avoid; }}
      .change-row, .deep-article, .product-row, .watch-row {{ break-inside: avoid; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      html {{ scroll-behavior: auto; }}
      *, *::before, *::after {{ transition-duration: .01ms !important; animation-duration: .01ms !important; }}
    }}
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content">跳到正文</a>

  <header class="masthead">
    <div class="shell">
      <div class="masthead-top">
        <div class="brand-line">361° KIDS / VERIFIED WEEKLY BRIEF</div>
        <div class="edition">基于可核验来源整理 · {esc(end_date[:4] if end_date else '')} 周度档案</div>
      </div>

      <div class="masthead-grid">
        <div>
          <h1>运动产业<br>周度情报</h1>
          <p class="deck">品牌动作、产品变化、渠道与儿童消费信息的管理层证据简报。</p>
        </div>
        <div class="week-stamp">
          <p class="week">{esc(week_label)}</p>
          <p class="generated">生成时间 {esc(generated_label)}</p>
        </div>
      </div>

      <div class="thesis">
        <div class="thesis-label">The week in one line</div>
        <div>
          <blockquote>{esc(weekly_thesis)}</blockquote>
          {f'<p class="thesis-summary">{esc(week_paragraph)}</p>' if week_paragraph else ''}
          <div class="evidence-line" aria-label="本周证据摘要">
            <span><strong>{len(key_developments)}</strong> 项核心变化</span>
            <span><strong>{new_count}</strong> 项本周新增</span>
            <span><strong>{follow_count}</strong> 项持续跟踪</span>
            <span><strong>{len(product_radar)}</strong> 项已核验产品</span>
            <span><strong>{len(source_registry)}</strong> 条原文证据</span>
          </div>
        </div>
      </div>
    </div>
  </header>

  <nav class="section-nav" aria-label="周报目录">
    <div class="shell nav-inner">
      <a href="#changes">本周变化</a>
      <a href="#deep-dives">深读</a>
      <a href="#products">产品雷达</a>
      {landscape_nav}
      <a href="#tracking">跟踪台账</a>
      <a href="#watchlist">下周观察</a>
      <a href="#sources">来源</a>
      <span class="nav-spacer"></span>
      <button class="print-button" type="button" onclick="window.print()">打印 / 导出PDF</button>
    </div>
  </nav>

  <main id="main-content">
    <section class="report-section" id="changes">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">01 / Change ledger</p>
          <div>
            <h2>本周真正发生了什么</h2>
            <p class="section-intro">只呈现时间、来源和链接通过质量门槛的变化；序号代表本期编辑优先级，不代表市场热度。</p>
          </div>
        </div>
        {low_evidence_notice}
        <div class="change-list">{render_developments()}</div>
      </div>
    </section>

    <section class="report-section" id="deep-dives">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">02 / Editorial reads</p>
          <div>
            <h2>从事件到趋势</h2>
            <p class="section-intro">把同一方向的多条证据放在一起阅读，区分单条新闻与值得持续跟踪的行业变化。</p>
          </div>
        </div>
        <div class="deep-grid">{render_deep_dives()}</div>
      </div>
    </section>

    <section class="report-section" id="products">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">03 / Verified products</p>
          <div>
            <h2>具名产品雷达</h2>
            <p class="section-intro">仅收录经官方单源或两家独立可信来源核验的具名商品；原文没有提供的价格、发售日和技术字段不展示。</p>
          </div>
        </div>
        <div class="product-list">{render_products()}</div>
      </div>
    </section>

    {landscape_section}

    <section class="report-section" id="tracking">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">05 / Tracking desk</p>
          <div>
            <h2>事件跟踪台账</h2>
            <p class="section-intro">本周重点不在此重复罗列；这里只呈现延续状态、未出现后续和仍待核验的证据线索。</p>
          </div>
        </div>
        <div class="tracking-grid">
          <div class="tracking-block">
            <h3>本周新增 <span class="tracking-count">{new_count}</span></h3>
            <p class="tracking-summary">已在“本周变化”集中呈现，不在台账重复占用阅读空间。</p>
          </div>
          <div class="tracking-block">
            <h3>持续跟踪 <span class="tracking-count">{follow_count}</span></h3>
            {render_tracking_list(follow_up_selected, '本期没有从上周延续的重点事件。')}
          </div>
          <div class="tracking-block">
            <h3>本周未出现后续 <span class="tracking-count">{len(not_seen_this_week)}</span></h3>
            {render_tracking_list(not_seen_this_week, '暂无需要标记为“本周未出现后续”的上期重点。')}
          </div>
          <div class="tracking-block">
            <h3>待核验产品线索 <span class="tracking-count">{len(product_leads_pending)}</span></h3>
            {render_product_leads()}
          </div>
        </div>
        <p class="tracking-summary">另有 {len(verification_queue)} 组矛盾事件进入核验队列，未混入已确认重点。</p>
        {render_conflicts()}
      </div>
    </section>

    <section class="report-section" id="watchlist">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">06 / Next watch</p>
          <div>
            <h2>下周继续看什么</h2>
            <p class="section-intro">观察项必须与本周事件或产品证据关联，不使用固定经营口号。</p>
          </div>
        </div>
        <div class="watch-list">{render_watchlist()}</div>
      </div>
    </section>

    <section class="report-section" id="sources">
      <div class="shell">
        <div class="section-heading">
          <p class="section-kicker">07 / Source book</p>
          <div>
            <h2>来源与核验口径</h2>
            <p class="section-intro">每项重点均保留原媒体直链；无法解析到原媒体的中转链接不会进入来源目录。</p>
          </div>
        </div>
        {render_sources()}
        {render_quality_notes()}
      </div>
    </section>
  </main>

  <footer>
    <div class="shell footer-inner">
      <span>361°儿童 · 运动产业周度情报</span>
      <span>统计周期 {esc(start_date)}—{esc(end_date)} · 内容随本周可核验事实变化</span>
    </div>
  </footer>
</body>
</html>
"""


# =========================================================
# 5. 原子写入
# =========================================================

temp_file = OUTPUT_HTML.with_suffix(".tmp")
temp_file.write_text(html_text, encoding="utf-8")
temp_file.replace(OUTPUT_HTML)

print(f"weekly html generated: {OUTPUT_HTML}")
print(f"schema version: {schema_version or 'unknown'}")
print(f"key developments: {len(key_developments)}")
print(f"deep dives: {len(deep_dives)}")
print(f"verified products: {len(product_radar)}")
print(f"verification groups: {len(verification_queue)}")
print(f"source links: {len(source_registry)}")
