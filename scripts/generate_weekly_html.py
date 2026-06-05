from pathlib import Path
from datetime import datetime
import json
import re
import html
from collections import Counter

# =========================================================
# 文件路径
# =========================================================
WEEKLY_FILE = Path("output/weekly/latest_week.json")
ANALYSIS_FILE = Path("output/weekly/weekly_analysis.json")
PRODUCT_SIGNAL_FILE = Path("output/products/latest_product_signals.json")

OUTPUT_DIR = Path("output/weekly")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_HTML = OUTPUT_DIR / "weekly_report.html"


# =========================================================
# 基础工具
# =========================================================
def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"load json error: {path} {repr(e)}")
    return default


def clean_raw(text):
    text = str(text or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def safe_html(text):
    return html.escape(clean_raw(text))


def short_raw(text, n=42):
    text = clean_raw(text)
    return text if len(text) <= n else text[:n] + "..."


def short(text, n=42):
    return safe_html(short_raw(text, n))


def get_list(data, key):
    value = data.get(key, []) if isinstance(data, dict) else []
    return value if isinstance(value, list) else []


def to_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def pair_to_rows(items, name_key):
    rows = []
    for item in items or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append({name_key: item[0], "count": item[1]})
        elif isinstance(item, dict):
            rows.append(item)
    return rows


def parse_ai_judgement(value):
    if not value:
        return {}

    if isinstance(value, dict):
        return value

    text = clean_raw(value)
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


def dict_to_sentence(item):
    if not isinstance(item, dict):
        return safe_html(item)

    theme = item.get("theme") or item.get("title") or ""
    heat = item.get("heat", "")
    suggestion = (
        item.get("suggestion")
        or item.get("risk")
        or item.get("action")
        or item.get("desc")
        or ""
    )

    prefix = f"<b>【{safe_html(theme)}】</b>" if theme else ""
    heat_text = f"<span class='heat-pill'>热度 {safe_html(heat)}</span>" if heat != "" else ""

    return f"{prefix}{heat_text}{safe_html(suggestion)}"


def render_list(items, limit=5):
    html_text = ""
    for item in items[:limit]:
        html_text += f"<li>{dict_to_sentence(item)}</li>"
    return html_text


def contains_any(text, keys):
    text = clean_raw(text)
    return any(k in text for k in keys)


# =========================================================
# 读取数据
# =========================================================
weekly = load_json(WEEKLY_FILE, {})
analysis = load_json(ANALYSIS_FILE, {})
product_signal_data = load_json(PRODUCT_SIGNAL_FILE, {})

generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")

summary = analysis.get("summary", {}) if isinstance(analysis, dict) else {}
if not isinstance(summary, dict):
    summary = {}

news = analysis.get("news", {}) if isinstance(analysis, dict) else {}
if not isinstance(news, dict):
    news = {}

product_signals = analysis.get("product_signals", {}) if isinstance(analysis, dict) else {}
if not isinstance(product_signals, dict) or not product_signals:
    product_signals = product_signal_data if isinstance(product_signal_data, dict) else {}

days = get_list(weekly, "days")
if not days and summary.get("date_range"):
    days = [summary.get("date_range")]

news_pool = news.get("news_pool", []) if isinstance(news, dict) else []
if not isinstance(news_pool, list) or not news_pool:
    news_pool = get_list(weekly, "top_news")

keywords = analysis.get("keywords", []) if isinstance(analysis, dict) else []
if not isinstance(keywords, list):
    keywords = get_list(weekly, "keywords")

regions = analysis.get("regions") or analysis.get("region_analysis") or []
if not isinstance(regions, list):
    regions = []

opportunities = get_list(analysis, "opportunities")
risks = get_list(analysis, "risks")
actions = get_list(analysis, "actions")
product_suggestions = get_list(analysis, "product_suggestions")

ai_judgement = parse_ai_judgement(
    analysis.get("ai_judgement") or summary.get("ai_judgement") or ""
)

signal_count = to_int(
    product_signals.get("signal_count")
    or len(product_signals.get("signals", []))
    or 0
)

signal_brands = pair_to_rows(product_signals.get("top_brands", []), "brand")
signal_keywords = pair_to_rows(product_signals.get("top_keywords", []), "keyword")
signal_categories = pair_to_rows(product_signals.get("top_categories", []), "category")
signal_seasons = pair_to_rows(product_signals.get("top_seasons", []), "season")
signal_items = get_list(product_signals, "signals")


# =========================================================
# 默认数据兜底
# =========================================================
def build_weekly_summary_parts():
    parts = []

    if summary.get("date_range"):
        parts.append(("统计周期", summary.get("date_range")))

    mapping = [
        ("核心判断", "core_judgement"),
        ("商品方向", "product_direction"),
        ("区域方向", "regional_direction"),
        ("下周动作", "next_action"),
    ]

    for label, key in mapping:
        if summary.get(key):
            parts.append((label, summary.get(key)))

    if not parts:
        parts = [
            ("核心判断", "本周行业热点围绕品牌动作、平台流量、商品趋势、区域客流和天气品类展开。"),
            ("下周动作", "后续需重点关注竞品动向、商品开发输入和重点区域承接效率。")
        ]

    return parts


if not opportunities:
    opportunities = [
        {"theme": "品牌动作", "suggestion": "重点关注本周竞品签约、联名、新品、渠道和社媒声量变化。"},
        {"theme": "商品趋势", "suggestion": "重点关注儿童运动鞋、防晒凉感、轻户外和青少年成人化趋势。"},
        {"theme": "平台流量", "suggestion": "重点关注直播、大促、搜索热词和内容种草对商品心智的影响。"}
    ]

if not risks:
    risks = [
        "平台大促强化价格心智，线下门店需关注折扣敏感度和核心价格带竞争。",
        "天气波动可能扰动线下客流，降雨区域需强化室内运动和防滑防雨商品承接。",
        "品牌竞争加剧，爆款同质化风险提升，需通过场景陈列和组合销售提升转化。"
    ]

if not actions:
    actions = [
        "每周沉淀竞品品牌动作，形成可跟踪的商品、内容和渠道观察清单。",
        "重点跟踪防晒、凉感、速干、透气鞋、运动凉鞋等夏季功能品类。",
        "围绕青少年运动、校园体育、亲子运动做商品组合和内容表达。"
    ]

if not product_suggestions:
    product_suggestions = [
        "增加青少年跑鞋、篮球鞋、训练服的成人化设计表达。",
        "强化防晒衣、凉感T恤、速干短裤、运动凉鞋组合开发。",
        "补充轻户外鞋服、帽包配件、亲子同款和校园运动套装。"
    ]


# =========================================================
# 内容渲染
# =========================================================
def render_summary_parts():
    blocks = ""
    for label, text in build_weekly_summary_parts():
        blocks += f"""
        <div class="judgement-item">
          <div class="judgement-label">{safe_html(label)}</div>
          <div class="judgement-text">{safe_html(text)}</div>
        </div>
        """
    return blocks


def render_ai_judgement():
    if not ai_judgement:
        return ""

    if ai_judgement.get("raw"):
        return f"""
        <div class="ai-panel">
          <div class="panel-title">AI 经营判断</div>
          <div class="ai-content">{safe_html(ai_judgement.get("raw"))}</div>
        </div>
        """

    sections = [
        ("核心判断", ai_judgement.get("core_judgement", "")),
        ("机会判断", ai_judgement.get("opportunity", "")),
        ("风险判断", ai_judgement.get("risk", "")),
        ("下周动作", ai_judgement.get("action", "")),
    ]

    inner = ""
    for title, text in sections:
        if text:
            inner += f"""
            <div class="ai-cell">
              <div class="ai-subtitle">{safe_html(title)}</div>
              <div class="ai-text">{safe_html(text)}</div>
            </div>
            """

    if not inner:
        return ""

    return f"""
    <div class="ai-panel">
      <div class="panel-title">AI 经营判断</div>
      <div class="ai-grid">{inner}</div>
    </div>
    """


def extract_news_titles():
    result = []
    for item in news_pool:
        if isinstance(item, dict):
            title = item.get("title", "")
            tag = item.get("tag", "")
            source = item.get("source", "")
            desc = item.get("desc", "")
            if title:
                result.append({
                    "title": clean_raw(title),
                    "tag": clean_raw(tag),
                    "source": clean_raw(source),
                    "desc": clean_raw(desc),
                })
        elif isinstance(item, str):
            result.append({"title": clean_raw(item), "tag": "", "source": "", "desc": ""})
    return result


def render_news():
    items = extract_news_titles()
    if not items:
        return "<div class='empty'>暂无本周重点资讯数据</div>"

    counter = Counter([x["title"] for x in items])
    first_info = {}
    for x in items:
        first_info.setdefault(x["title"], x)

    html_text = ""
    for i, (title, count) in enumerate(counter.most_common(8), start=1):
        info = first_info.get(title, {})
        tag = info.get("tag") or "行业资讯"
        source = info.get("source") or "公开资讯"
        html_text += f"""
        <div class="news-card">
          <div class="news-rank">{i}</div>
          <div class="news-main">
            <div class="news-title">{short(title, 58)}</div>
            <div class="news-meta">
              <span>{safe_html(tag)}</span>
              <span>{safe_html(source)}</span>
              <span>出现 {count} 次</span>
            </div>
          </div>
        </div>
        """
    return html_text


def render_keywords():
    values = []

    for item in keywords:
        if isinstance(item, dict):
            word = item.get("word") or item.get("keyword") or item.get("name") or item.get("title")
            if word:
                values.append(clean_raw(word))
        elif isinstance(item, str):
            values.append(clean_raw(item))

    if not values:
        values = ["品牌签约", "防晒凉感", "儿童跑鞋", "轻户外", "青少年", "直播电商", "平台大促", "校园体育"]

    rows = Counter(values).most_common(22)

    html_text = ""
    for i, (word, count) in enumerate(rows, start=1):
        cls = "hot-word big" if i <= 3 else "hot-word mid" if i <= 9 else "hot-word"
        html_text += f"<span class='{cls}'>{safe_html(word)}</span>"
    return html_text


def render_regions():
    if not regions:
        return "<div class='empty'>暂无区域数据</div>"

    html_text = ""

    for idx, region in enumerate(regions[:6], start=1):
        if not isinstance(region, dict):
            continue

        name = region.get("region") or region.get("name") or "重点区域"
        summary_text = region.get("summary", "")
        suggestion = region.get("suggestion", "")

        if not summary_text:
            focuses = region.get("top_focus", [])
            focus_text = "、".join([
                clean_raw(x.get("focus", ""))
                for x in focuses[:2]
                if isinstance(x, dict) and x.get("focus")
            ])
            summary_text = f"本周重点关注：{focus_text or '区域客流、天气品类、商圈活动'}。"

        desc = f"{summary_text} 建议：{suggestion}" if suggestion else summary_text

        icon = "☔" if contains_any(desc, ["雨", "防滑", "防雨"]) else "☀️" if contains_any(desc, ["高温", "防晒", "凉感"]) else "📍"

        html_text += f"""
        <div class="region-card">
          <div class="region-top">
            <span class="region-icon">{icon}</span>
            <span class="region-name">{safe_html(name)}</span>
          </div>
          <div class="region-desc">{safe_html(desc)}</div>
        </div>
        """

    return html_text


def render_signal_rank(rows, name_key, title, limit=10):
    if not rows:
        return f"""
        <div class="signal-card">
          <div class="signal-title">{safe_html(title)}</div>
          <div class="empty">暂无趋势信号</div>
        </div>
        """

    max_count = max([to_int(x.get("count", 0)) for x in rows[:limit]] + [1])

    html_text = f"""
    <div class="signal-card">
      <div class="signal-title">{safe_html(title)}</div>
    """

    for idx, row in enumerate(rows[:limit], start=1):
        name = safe_html(row.get(name_key, ""))
        count = to_int(row.get("count", 0))
        width = max(8, int(count / max_count * 100))

        html_text += f"""
        <div class="rank-bar-row">
          <div class="rank-label"><span>{idx}</span>{name}</div>
          <div class="rank-bar"><i style="width:{width}%"></i></div>
          <div class="rank-count">{count}</div>
        </div>
        """

    html_text += "</div>"
    return html_text


def render_signal_tags(rows, name_key, limit=24):
    if not rows:
        return "<div class='empty'>暂无关键词信号</div>"

    html_text = "<div class='signal-tags'>"

    for idx, row in enumerate(rows[:limit], start=1):
        name = safe_html(row.get(name_key, ""))
        count = to_int(row.get("count", 0))
        cls = "tag-large" if idx <= 5 else "tag-mid" if idx <= 12 else ""
        html_text += f"<span class='{cls}'>{name}<em>{count}</em></span>"

    html_text += "</div>"
    return html_text


def get_visual_icon(category, keywords, title):
    text = f"{category} {' '.join(keywords)} {title}"

    if "足弓" in text or "跑鞋" in text:
        return "👟"
    if "防晒" in text or "凉感" in text:
        return "☀️"
    if "篮球" in text:
        return "🏀"
    if "户外" in text or "冲锋衣" in text:
        return "⛰️"
    if "羽绒服" in text or "保暖" in text:
        return "❄️"
    if "校园" in text or "开学" in text:
        return "🎒"
    if "童装" in text or "儿童服装" in text:
        return "👕"

    return "✨"


def make_product_insight(category, keywords, title):
    text = f"{category} {' '.join(keywords)} {title}"

    if "足弓" in text:
        return "关注儿童足弓支撑、成长跑鞋、医学背书与专业科技表达。"
    if "防晒" in text or "凉感" in text:
        return "关注夏季防晒、凉感、速干和轻薄透气组合。"
    if "碳板" in text or "竞速" in text:
        return "关注青少年跑鞋成人化，但需控制专业科技使用边界。"
    if "篮球" in text:
        return "关注校园篮球、训练场景和中大童运动鞋升级。"
    if "户外" in text or "冲锋衣" in text:
        return "关注轻户外、防水防风、亲子户外和场景陈列。"
    if "校园" in text or "开学" in text:
        return "关注开学季、校园体育、书包鞋服组合销售。"
    if "护脊" in text:
        return "关注护脊书包、儿童人体工学和开学季功能卖点。"

    return "关注该信号背后的品牌动作、商品卖点和终端陈列表达。"


def build_product_cards():
    cards = []
    brand_limit = Counter()
    category_limit = Counter()

    sorted_items = sorted(
        signal_items,
        key=lambda x: to_int(x.get("heat", 0)) if isinstance(x, dict) else 0,
        reverse=True
    )

    for s in sorted_items:
        if not isinstance(s, dict):
            continue

        brands = s.get("brand_hits", [])
        keywords = s.get("keyword_hits", [])

        if not isinstance(brands, list):
            brands = []
        if not isinstance(keywords, list):
            keywords = []

        brand = "、".join(brands[:2]) if brands else "行业趋势"
        category = s.get("category", "")
        title = s.get("short_title") or s.get("title", "")

        if brand_limit[brand] >= 2:
            continue
        if category_limit[category] >= 3:
            continue

        brand_limit[brand] += 1
        category_limit[category] += 1

        cards.append({
            "brand": brand,
            "name": title,
            "category": category,
            "heat": s.get("heat", ""),
            "trend": s.get("season_tag", ""),
            "tags": keywords[:3],
            "source": s.get("source", ""),
            "icon": get_visual_icon(category, keywords, title),
            "insight": make_product_insight(category, keywords, title)
        })

        if len(cards) >= 12:
            break

    return cards


product_cards = build_product_cards()


def render_product_cards():
    if not product_cards:
        return "<div class='empty'>暂无商品趋势数据</div>"

    html_text = ""

    for idx, p in enumerate(product_cards, start=1):
        tag_text = " / ".join([clean_raw(x) for x in p.get("tags", [])[:3]])

        html_text += f"""
        <div class="product-card">
          <div class="product-cover">
            <div class="product-rank">TOP {idx}</div>
            <div class="product-icon">{p.get("icon", "✨")}</div>
            <div class="product-category">{safe_html(p.get("category", ""))}</div>
            <div class="product-heat">热度 {safe_html(p.get("heat", ""))}</div>
          </div>
          <div class="product-brand">{safe_html(p.get("brand", ""))}</div>
          <div class="product-name">{short(p.get("name", ""), 42)}</div>
          <div class="product-meta">
            <span>{safe_html(p.get("trend", ""))}</span>
            <span>{safe_html(p.get("source", ""))}</span>
          </div>
          <div class="product-tags">{safe_html(tag_text)}</div>
          <div class="product-insight">{safe_html(p.get("insight", ""))}</div>
        </div>
        """

    return html_text


def render_hot_signal_items():
    if not signal_items:
        return "<div class='empty'>暂无高热商品信号</div>"

    html_text = ""

    sorted_items = sorted(
        [x for x in signal_items if isinstance(x, dict)],
        key=lambda x: to_int(x.get("heat", 0)),
        reverse=True
    )

    for idx, s in enumerate(sorted_items[:8], start=1):
        brands = s.get("brand_hits", [])
        brands = "、".join(brands[:3]) if isinstance(brands, list) else ""

        html_text += f"""
        <div class="signal-news-row">
          <div class="signal-news-rank">{idx}</div>
          <div class="signal-news-main">
            <div class="signal-news-title">{short(s.get("title", ""), 58)}</div>
            <div class="signal-news-meta">
              <span>{safe_html(s.get("category", "综合趋势"))}</span>
              <span>{safe_html(s.get("season_tag", "全年"))}</span>
              <span>热度 {safe_html(s.get("heat", ""))}</span>
              <span>{safe_html(s.get("source", "公开资讯"))}</span>
            </div>
            <div class="signal-news-brand">{safe_html(brands)}</div>
          </div>
        </div>
        """

    return html_text


def render_product_suggestion_cards():
    html_text = ""
    for idx, item in enumerate(product_suggestions[:4], start=1):
        html_text += f"""
        <div class="suggest-card">
          <div class="suggest-no">0{idx}</div>
          <div class="suggest-text">{dict_to_sentence(item)}</div>
        </div>
        """
    return html_text


# =========================================================
# HTML输出
# =========================================================
html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>运动品牌行业周报</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:
    radial-gradient(circle at 8% 6%, rgba(255,139,0,.12), transparent 25%),
    radial-gradient(circle at 92% 10%, rgba(0,102,255,.12), transparent 30%),
    linear-gradient(180deg,#eef5ff 0%,#f7fbff 100%);
  font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;
  color:#132b55;
  padding:28px;
}}
.report{{width:1320px;margin:auto}}
.cover{{
  position:relative;height:290px;border-radius:30px;overflow:hidden;
  background:
    radial-gradient(circle at 82% 18%, rgba(255,145,0,.42), transparent 26%),
    radial-gradient(circle at 12% 90%, rgba(32,202,255,.25), transparent 30%),
    linear-gradient(135deg,#061b54 0%,#073f9d 48%,#0c83ff 100%);
  color:#fff;padding:38px 44px;box-shadow:0 24px 58px rgba(5,45,105,.28);margin-bottom:22px;
}}
.cover:before{{content:"";position:absolute;right:30px;top:26px;width:240px;height:240px;border-radius:50%;border:34px solid rgba(255,255,255,.11)}}
.cover:after{{content:"";position:absolute;right:-130px;bottom:-155px;width:430px;height:430px;border-radius:50%;border:46px solid rgba(255,255,255,.11)}}
.cover-tag{{display:inline-block;padding:8px 16px;border-radius:999px;background:rgba(255,255,255,.17);border:1px solid rgba(255,255,255,.25);font-size:14px;font-weight:900;margin-bottom:20px;backdrop-filter:blur(8px)}}
.cover-title{{font-size:60px;line-height:1.02;font-weight:950;letter-spacing:-1px}}
.cover-sub{{margin-top:16px;font-size:22px;font-weight:850;opacity:.95}}
.cover-footer{{position:absolute;left:44px;bottom:30px;font-size:15px;font-weight:800;opacity:.92}}
.stats{{position:absolute;right:34px;bottom:30px;display:grid;grid-template-columns:repeat(4,108px);gap:10px}}
.stat{{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.24);border-radius:18px;padding:15px 10px;text-align:center;backdrop-filter:blur(8px)}}
.stat-num{{font-size:31px;font-weight:950}}
.stat-label{{font-size:12px;margin-top:4px;opacity:.9}}

.page{{background:rgba(255,255,255,.96);border:1px solid rgba(216,228,246,.9);border-radius:26px;padding:24px;box-shadow:0 18px 42px rgba(21,58,112,.12);margin-bottom:20px}}
.section-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;border-bottom:2px solid #e2ecfa;padding-bottom:12px}}
.section-title{{font-size:26px;font-weight:950;color:#062b78}}
.section-kicker{{color:#0b63d8;font-weight:950;font-size:13px;letter-spacing:.8px}}

.judgement-grid{{display:grid;grid-template-columns:1.12fr .88fr;gap:18px}}
.judgement-box{{background:linear-gradient(135deg,#f3f8ff,#ffffff);border:1px solid #dbe6f6;border-radius:22px;padding:18px}}
.judgement-item{{display:grid;grid-template-columns:86px 1fr;gap:12px;padding:12px 0;border-bottom:1px dashed #d6e3f4}}
.judgement-item:last-child{{border-bottom:none}}
.judgement-label{{font-size:14px;font-weight:950;color:#0b63d8}}
.judgement-text{{font-size:16px;line-height:1.7;font-weight:760;color:#1d355d}}
.ai-panel{{background:linear-gradient(135deg,#f9fbff,#ffffff);border:1px solid #dbe6f6;border-radius:22px;padding:18px}}
.panel-title{{font-size:18px;font-weight:950;color:#062b78;margin-bottom:12px}}
.ai-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.ai-cell{{padding:12px;border-radius:15px;background:#f3f8ff;border:1px solid #dbe6f6}}
.ai-subtitle{{font-size:14px;font-weight:950;color:#0b4db3;margin-bottom:7px}}
.ai-text,.ai-content{{font-size:14px;line-height:1.7;color:#294461;font-weight:720}}

.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.card,.signal-card{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:18px;box-shadow:0 8px 20px rgba(20,60,110,.05)}}
.card-title,.signal-title{{font-size:18px;font-weight:950;color:#0b4db3;margin-bottom:12px}}
ul{{padding-left:20px}}
li{{margin-bottom:11px;font-size:15px;line-height:1.6;font-weight:760;color:#273f62}}
.heat-pill{{display:inline-block;margin:0 6px 0 0;padding:2px 8px;border-radius:999px;background:#ecfdf5;color:#0f766e;font-size:12px;font-weight:950}}

.news-card{{display:grid;grid-template-columns:40px 1fr;gap:12px;align-items:flex-start;padding:12px 0;border-bottom:1px solid #edf2fa}}
.news-card:last-child{{border-bottom:none}}
.news-rank{{width:34px;height:34px;border-radius:12px;background:linear-gradient(135deg,#063b88,#0d7df2);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:950}}
.news-title{{font-size:15.5px;line-height:1.45;font-weight:950;color:#0d2d68}}
.news-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.news-meta span{{font-size:11px;background:#edf5ff;color:#426081;border-radius:8px;padding:3px 7px;font-weight:850}}

.word-cloud{{min-height:310px;padding:24px;display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:15px 18px;background:linear-gradient(135deg,#f8fbff,#eef6ff);border-radius:20px;border:1px solid #dbe6f6}}
.hot-word{{font-weight:950;color:#0b63d8;background:#fff;border:1px solid #dbe6f6;border-radius:999px;padding:8px 15px;font-size:14px;box-shadow:0 6px 15px rgba(20,60,110,.06)}}
.hot-word.mid{{font-size:17px;color:#0f766e;background:#ecfdf5}}
.hot-word.big{{font-size:24px;color:#062b78;background:#dcecff}}

.region-card{{border-radius:20px;background:linear-gradient(135deg,#f7fbff,#ffffff);border:1px solid #dbe6f6;padding:17px;min-height:140px;box-shadow:0 8px 20px rgba(20,60,110,.04)}}
.region-top{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.region-icon{{font-size:22px}}
.region-name{{font-size:20px;font-weight:950;color:#0b4db3}}
.region-desc{{font-size:14.5px;line-height:1.6;color:#315174;font-weight:750}}

.signal-grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}}
.rank-bar-row{{display:grid;grid-template-columns:145px 1fr 38px;gap:10px;align-items:center;margin-bottom:11px}}
.rank-label{{font-size:13px;font-weight:900;color:#183a76;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.rank-label span{{display:inline-flex;width:22px;height:22px;align-items:center;justify-content:center;background:#0b63d8;color:#fff;border-radius:7px;margin-right:7px;font-size:11px}}
.rank-bar{{height:10px;background:#edf5ff;border-radius:999px;overflow:hidden}}
.rank-bar i{{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#0b63d8,#19a3ff)}}
.rank-count{{font-size:13px;font-weight:950;color:#0b63d8;text-align:right}}
.signal-tags{{display:flex;flex-wrap:wrap;gap:10px}}
.signal-tags span{{display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border-radius:999px;background:#f3f8ff;border:1px solid #dbe6f6;color:#0b4db3;font-size:13px;font-weight:900}}
.signal-tags span.tag-mid{{font-size:15px;background:#ecfdf5;color:#0f766e}}
.signal-tags span.tag-large{{font-size:18px;background:#dcecff;color:#062b78}}
.signal-tags em{{font-style:normal;background:#fff;border-radius:999px;padding:2px 6px;color:#64748b;font-size:11px}}

.signal-news-row{{display:grid;grid-template-columns:34px 1fr;gap:12px;padding:11px 0;border-bottom:1px solid #edf2fa}}
.signal-news-row:last-child{{border-bottom:none}}
.signal-news-rank{{width:30px;height:30px;border-radius:10px;background:#0f766e;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:950}}
.signal-news-title{{font-size:15px;line-height:1.45;font-weight:950;color:#0d2d68}}
.signal-news-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}}
.signal-news-meta span{{font-size:11px;background:#edf5ff;color:#365379;border-radius:8px;padding:3px 6px;font-weight:800}}
.signal-news-brand{{font-size:12px;color:#0f766e;font-weight:850;margin-top:5px}}

.products{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.product-card{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:12px;box-shadow:0 10px 22px rgba(20,60,110,.06)}}
.product-cover{{position:relative;width:100%;height:150px;border-radius:16px;overflow:hidden;margin-bottom:11px;display:flex;flex-direction:column;justify-content:center;align-items:center;background:radial-gradient(circle at 80% 20%,rgba(25,163,255,.22),transparent 30%),linear-gradient(135deg,#edf5ff,#f8fbff)}}
.product-icon{{font-size:42px;line-height:1;margin-bottom:8px}}
.product-category{{font-size:21px;font-weight:950;color:#0b4db3;text-align:center}}
.product-heat{{margin-top:9px;font-size:13px;font-weight:900;color:#0f766e;background:#ecfdf5;padding:5px 12px;border-radius:999px}}
.product-rank{{position:absolute;top:8px;left:8px;padding:4px 8px;border-radius:999px;background:rgba(6,43,120,.88);color:#fff;font-size:11px;font-weight:950}}
.product-brand{{font-size:13px;color:#0b63d8;font-weight:950}}
.product-name{{font-size:15px;line-height:1.38;font-weight:950;color:#0d2d68;margin-top:5px;min-height:62px}}
.product-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;font-size:11px;color:#51698d}}
.product-meta span{{background:#edf5ff;padding:3px 6px;border-radius:8px}}
.product-tags{{margin-top:8px;font-size:12px;color:#1d8c54;font-weight:850}}
.product-insight{{margin-top:10px;padding:10px;border-radius:12px;background:#f0fdf4;color:#166534;font-size:12.5px;line-height:1.45;font-weight:850;min-height:72px}}

.suggest-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.suggest-card{{position:relative;border-radius:20px;background:linear-gradient(135deg,#fff7ed,#ffffff);border:1px solid #fed7aa;padding:18px 16px 16px 16px;font-size:15px;line-height:1.55;font-weight:850;color:#7c2d12;min-height:150px;box-shadow:0 8px 18px rgba(180,83,9,.07)}}
.suggest-no{{font-size:24px;font-weight:950;color:#fb923c;margin-bottom:8px}}
.suggest-text{{font-size:15px;line-height:1.62}}
.empty{{color:#8a99ad;font-size:14px;padding:20px;text-align:center}}
.footer{{text-align:center;color:#7184a3;font-size:12px;margin:14px 0 4px}}
</style>
</head>

<body>
<div class="report">

<section class="cover">
  <div class="cover-tag">361°儿童 · 周度经营洞察</div>
  <div class="cover-title">运动品牌行业周报</div>
  <div class="cover-sub">品牌动作 × 商品趋势 × 平台流量 × 区域机会 × 终端建议</div>
  <div class="cover-footer">ONE DEGREE BEYOND｜经营管理部｜生成时间 {generated_time}</div>
  <div class="stats">
    <div class="stat"><div class="stat-num">{len(days)}</div><div class="stat-label">统计天数</div></div>
    <div class="stat"><div class="stat-num">{len(news_pool)}</div><div class="stat-label">资讯样本</div></div>
    <div class="stat"><div class="stat-num">{signal_count}</div><div class="stat-label">趋势信号</div></div>
    <div class="stat"><div class="stat-num">{len(product_cards)}</div><div class="stat-label">商品观察</div></div>
  </div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">一、本周核心判断</div>
    <div class="section-kicker">WEEKLY JUDGEMENT</div>
  </div>
  <div class="judgement-grid">
    <div class="judgement-box">{render_summary_parts()}</div>
    {render_ai_judgement()}
  </div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">二、本周趋势总览</div>
    <div class="section-kicker">TREND OVERVIEW</div>
  </div>
  <div class="grid-3">
    <div class="card"><div class="card-title">机会方向</div><ul>{render_list(opportunities, 4)}</ul></div>
    <div class="card"><div class="card-title">风险提示</div><ul>{render_list(risks, 4)}</ul></div>
    <div class="card"><div class="card-title">下周动作</div><ul>{render_list(actions, 4)}</ul></div>
  </div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">三、本周重点资讯与热词</div>
    <div class="section-kicker">NEWS & KEYWORDS</div>
  </div>
  <div class="grid-2">
    <div class="card"><div class="card-title">本周 TOP 资讯</div>{render_news()}</div>
    <div><div class="word-cloud">{render_keywords()}</div></div>
  </div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">四、区域机会与渠道观察</div>
    <div class="section-kicker">REGIONAL INSIGHT</div>
  </div>
  <div class="grid-3">{render_regions()}</div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">五、真实商品趋势信号看板</div>
    <div class="section-kicker">PRODUCT SIGNALS</div>
  </div>

  <div class="signal-grid">
    {render_signal_rank(signal_brands, "brand", "品牌热度 TOP10", 10)}
    {render_signal_rank(signal_categories, "category", "品类/场景热度 TOP10", 10)}
  </div>

  <div class="signal-grid">
    <div class="signal-card">
      <div class="signal-title">关键词信号</div>
      {render_signal_tags(signal_keywords, "keyword", 24)}
    </div>
    {render_signal_rank(signal_seasons, "season", "四季趋势分布", 8)}
  </div>

  <div class="signal-card">
    <div class="signal-title">高热商品/新品信号</div>
    {render_hot_signal_items()}
  </div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">六、代表商品观察</div>
    <div class="section-kicker">REPRESENTATIVE PRODUCTS</div>
  </div>
  <div class="products">{render_product_cards()}</div>
</section>

<section class="page">
  <div class="section-head">
    <div class="section-title">七、下季度商品开发建议</div>
    <div class="section-kicker">PRODUCT PLANNING</div>
  </div>
  <div class="suggest-grid">{render_product_suggestion_cards()}</div>
</section>

<div class="footer">
  数据来源：TrendRadar 日报历史库 / 周报库 / 商品趋势信号库 ｜ 制作：运动品牌行业周报自动化系统
</div>

</div>
</body>
</html>
"""

OUTPUT_HTML.write_text(html_text, encoding="utf-8")
print(f"weekly html generated: {OUTPUT_HTML}")
