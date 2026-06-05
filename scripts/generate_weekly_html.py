from pathlib import Path
from datetime import datetime
import json, re, html
from collections import Counter

WEEKLY_FILE = Path("output/weekly/latest_week.json")
ANALYSIS_FILE = Path("output/weekly/weekly_analysis.json")
PRODUCT_SIGNAL_FILE = Path("output/products/latest_product_signals.json")

OUTPUT_DIR = Path("output/weekly")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_HTML = OUTPUT_DIR / "weekly_report.html"


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"load json error: {path} {repr(e)}")
    return default


def clean(text):
    text = str(text or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return html.escape(text)


def clean_raw(text):
    text = str(text or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def short(text, n=42):
    text = clean_raw(text)
    return clean(text if len(text) <= n else text[:n] + "...")


def get_list(data, key):
    value = data.get(key, [])
    return value if isinstance(value, list) else []


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
        return clean(item)

    theme = item.get("theme") or item.get("title") or ""
    heat = item.get("heat", "")
    suggestion = item.get("suggestion") or item.get("risk") or item.get("action") or item.get("desc") or ""

    prefix = f"【{clean(theme)}】" if theme else ""
    heat_text = f"热度{clean(heat)}。" if heat != "" else ""

    return f"{prefix}{heat_text}{clean(suggestion)}"


def render_list(items, limit=5):
    html_text = ""
    for item in items[:limit]:
        html_text += f"<li>{dict_to_sentence(item)}</li>"
    return html_text


weekly = load_json(WEEKLY_FILE, {})
analysis = load_json(ANALYSIS_FILE, {})
product_signal_data = load_json(PRODUCT_SIGNAL_FILE, {})

generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")

summary = analysis.get("summary", {})
if not isinstance(summary, dict):
    summary = {}

news = analysis.get("news", {})
if not isinstance(news, dict):
    news = {}

product_signals = analysis.get("product_signals", {})
if not isinstance(product_signals, dict) or not product_signals:
    product_signals = product_signal_data if isinstance(product_signal_data, dict) else {}

days = get_list(weekly, "days")
if not days and summary.get("date_range"):
    days = [summary.get("date_range")]

news_pool = news.get("news_pool", [])
if not isinstance(news_pool, list):
    news_pool = []

if not news_pool:
    news_pool = get_list(weekly, "top_news")

keywords = analysis.get("keywords", [])
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

signal_count = int(
    product_signals.get("signal_count")
    or len(product_signals.get("signals", []))
    or 0
)

signal_brands = pair_to_rows(product_signals.get("top_brands", []), "brand")
signal_keywords = pair_to_rows(product_signals.get("top_keywords", []), "keyword")
signal_categories = pair_to_rows(product_signals.get("top_categories", []), "category")
signal_seasons = pair_to_rows(product_signals.get("top_seasons", []), "season")
signal_items = get_list(product_signals, "signals")


def build_weekly_summary():
    parts = []

    if summary.get("date_range"):
        parts.append(f"统计周期：{summary.get('date_range')}")

    for key in ["core_judgement", "product_direction", "regional_direction", "next_action"]:
        if summary.get(key):
            parts.append(summary.get(key))

    if not parts:
        return "本周行业热点围绕品牌动作、平台流量、商品趋势、区域客流和天气品类展开。后续需重点关注竞品动向、商品开发输入和重点区域承接效率。"

    return "｜".join(parts)


weekly_summary = clean(build_weekly_summary())

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


def render_ai_judgement():
    if not ai_judgement:
        return ""

    if ai_judgement.get("raw"):
        return f"""
        <div class="card ai-card">
          <div class="card-title">AI经营判断</div>
          <div class="ai-content">{clean(ai_judgement.get("raw"))}</div>
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
            <div class="ai-section">
              <div class="ai-subtitle">{title}</div>
              <div class="ai-text">{clean(text)}</div>
            </div>
            """

    if not inner:
        return ""

    return f"""
    <div class="card ai-card">
      <div class="card-title">AI经营判断</div>
      {inner}
    </div>
    """


def render_news():
    titles = []

    for item in news_pool:
        if isinstance(item, dict):
            title = item.get("title", "")
            if title:
                titles.append(clean_raw(title))
        elif isinstance(item, str):
            titles.append(clean_raw(item))

    if not titles:
        return "<div class='empty'>暂无本周重点资讯数据</div>"

    rows = Counter(titles).most_common(8)

    html_text = ""
    for i, (title, count) in enumerate(rows, start=1):
        html_text += f"""
        <div class="news-row">
          <div class="news-rank">{i}</div>
          <div>
            <div class="news-title">{short(title, 50)}</div>
            <div class="news-meta">本周出现 {count} 次</div>
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
        html_text += f"<span class='{cls}'>{clean(word)}</span>"
    return html_text


def render_regions():
    if not regions:
        return "<div class='empty'>暂无区域数据</div>"

    html_text = ""

    for region in regions[:6]:
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

        if suggestion:
            desc = f"{summary_text} 建议：{suggestion}"
        else:
            desc = summary_text

        html_text += f"""
        <div class="region-card">
          <div class="region-name">{clean(name)}</div>
          <div class="region-desc">{clean(desc)}</div>
        </div>
        """

    return html_text


def render_signal_rank(rows, name_key, title, limit=10):
    if not rows:
        return f"""
        <div class="signal-card">
          <div class="signal-title">{title}</div>
          <div class="empty">暂无趋势信号</div>
        </div>
        """

    max_count = max([int(x.get("count", 0) or 0) for x in rows[:limit]] + [1])

    html_text = f"""
    <div class="signal-card">
      <div class="signal-title">{title}</div>
    """

    for idx, row in enumerate(rows[:limit], start=1):
        name = clean(row.get(name_key, ""))
        count = int(row.get("count", 0) or 0)
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
        name = clean(row.get(name_key, ""))
        count = int(row.get("count", 0) or 0)
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

    return "关注该信号背后的品牌动作、商品卖点和终端陈列表达。"


def build_product_cards():
    cards = []
    brand_limit = Counter()
    category_limit = Counter()

    sorted_items = sorted(
        signal_items,
        key=lambda x: int(x.get("heat", 0) or 0) if isinstance(x, dict) else 0,
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
          <div class="product-img-wrap product-signal-cover">
            <div class="product-rank">TOP {idx}</div>
            <div class="product-icon">{p.get("icon", "✨")}</div>
            <div class="product-signal-category">{clean(p.get("category", ""))}</div>
            <div class="product-signal-heat">热度 {clean(p.get("heat", ""))}</div>
          </div>
          <div class="product-brand">{clean(p.get("brand", ""))}</div>
          <div class="product-name">{short(p.get("name", ""), 42)}</div>
          <div class="product-meta">
            <span>{clean(p.get("category", ""))}</span>
            <span>{clean(p.get("trend", ""))}</span>
            <span>{clean(p.get("source", ""))}</span>
          </div>
          <div class="product-tags">{clean(tag_text)}</div>
          <div class="product-insight">{clean(p.get("insight", ""))}</div>
        </div>
        """

    return html_text


def render_hot_signal_items():
    if not signal_items:
        return "<div class='empty'>暂无高热商品信号</div>"

    html_text = ""

    sorted_items = sorted(
        [x for x in signal_items if isinstance(x, dict)],
        key=lambda x: int(x.get("heat", 0) or 0),
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
              <span>{clean(s.get("category", "综合趋势"))}</span>
              <span>{clean(s.get("season_tag", "全年"))}</span>
              <span>热度 {clean(s.get("heat", ""))}</span>
              <span>{clean(s.get("source", "公开资讯"))}</span>
            </div>
            <div class="signal-news-brand">{clean(brands)}</div>
          </div>
        </div>
        """

    return html_text


def render_product_suggestion_cards():
    html_text = ""
    for item in product_suggestions[:4]:
        html_text += f"<div class='suggest-card'>{dict_to_sentence(item)}</div>"
    return html_text


html_text = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>运动品牌行业周报</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#eaf1fb;font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;color:#102a5c;padding:24px}}
.report{{width:1280px;margin:auto}}
.cover{{position:relative;height:260px;border-radius:26px;overflow:hidden;background:radial-gradient(circle at 85% 20%,rgba(255,139,0,.32),transparent 28%),radial-gradient(circle at 16% 88%,rgba(11,99,216,.24),transparent 30%),linear-gradient(135deg,#052b78 0%,#0b63d8 52%,#1d8fff 100%);color:#fff;padding:34px 42px;box-shadow:0 20px 46px rgba(9,55,128,.26);margin-bottom:18px}}
.cover::after{{content:"";position:absolute;right:-80px;bottom:-120px;width:420px;height:420px;border-radius:50%;border:42px solid rgba(255,255,255,.12)}}
.cover-tag{{display:inline-block;padding:7px 14px;border-radius:999px;background:rgba(255,255,255,.16);font-size:14px;font-weight:900;margin-bottom:18px}}
.cover-title{{font-size:56px;line-height:1.05;font-weight:950;letter-spacing:-1px}}
.cover-sub{{margin-top:14px;font-size:22px;font-weight:850;opacity:.95}}
.cover-footer{{position:absolute;left:42px;bottom:28px;font-size:15px;font-weight:800;opacity:.9}}
.stats{{position:absolute;right:34px;top:34px;display:grid;grid-template-columns:repeat(4,104px);gap:10px}}
.stat{{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.24);border-radius:18px;padding:15px 12px;text-align:center;backdrop-filter:blur(6px)}}
.stat-num{{font-size:30px;font-weight:950}}
.stat-label{{font-size:12px;margin-top:4px;opacity:.9}}
.page{{background:#fff;border-radius:24px;padding:22px;box-shadow:0 18px 38px rgba(20,50,100,.12);margin-bottom:18px}}
.section-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;border-bottom:2px solid #e1ebf8;padding-bottom:10px}}
.section-title{{font-size:25px;font-weight:950;color:#062b78}}
.section-kicker{{color:#0b63d8;font-weight:950;font-size:13px}}
.summary-box{{background:linear-gradient(135deg,#f4f8ff,#eef6ff);border:1px solid #dbe6f6;border-radius:20px;padding:20px 22px;font-size:20px;line-height:1.7;font-weight:850;color:#0d2d68}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.card{{border:1px solid #dbe6f6;border-radius:18px;background:#fbfdff;padding:16px}}
.card-title{{font-size:17px;font-weight:950;color:#0b4db3;margin-bottom:10px}}
ul{{padding-left:20px}}
li{{margin-bottom:10px;font-size:15px;line-height:1.55;font-weight:760;color:#233e68}}
.news-row{{display:grid;grid-template-columns:38px 1fr;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid #edf2fa}}
.news-rank{{width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#063b88,#0d7df2);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:950}}
.news-title{{font-size:15.5px;font-weight:950;color:#0d2d68}}
.news-meta{{font-size:12px;color:#6b7f9f;margin-top:3px}}
.word-cloud{{min-height:250px;padding:22px;display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:14px 18px;background:linear-gradient(135deg,#f8fbff,#eef6ff);border-radius:18px;border:1px solid #dbe6f6}}
.hot-word{{font-weight:950;color:#0b63d8;background:#fff;border:1px solid #dbe6f6;border-radius:999px;padding:7px 14px;font-size:14px;box-shadow:0 5px 14px rgba(20,60,110,.06)}}
.hot-word.mid{{font-size:17px;color:#0f766e;background:#ecfdf5}}
.hot-word.big{{font-size:24px;color:#062b78;background:#dcecff}}
.region-card{{border-radius:18px;background:linear-gradient(135deg,#f7fbff,#ffffff);border:1px solid #dbe6f6;padding:16px;min-height:112px}}
.region-name{{font-size:20px;font-weight:950;color:#0b4db3;margin-bottom:8px}}
.region-desc{{font-size:14.5px;line-height:1.5;color:#315174;font-weight:750}}
.signal-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.signal-card{{border:1px solid #dbe6f6;border-radius:18px;background:#fbfdff;padding:16px}}
.signal-title{{font-size:18px;font-weight:950;color:#0b4db3;margin-bottom:12px}}
.rank-bar-row{{display:grid;grid-template-columns:132px 1fr 38px;gap:10px;align-items:center;margin-bottom:10px}}
.rank-label{{font-size:13px;font-weight:900;color:#183a76;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.rank-label span{{display:inline-flex;width:22px;height:22px;align-items:center;justify-content:center;background:#0b63d8;color:#fff;border-radius:7px;margin-right:7px;font-size:11px}}
.rank-bar{{height:9px;background:#edf5ff;border-radius:999px;overflow:hidden}}
.rank-bar i{{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#0b63d8,#19a3ff)}}
.rank-count{{font-size:13px;font-weight:950;color:#0b63d8;text-align:right}}
.signal-tags{{display:flex;flex-wrap:wrap;gap:10px}}
.signal-tags span{{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;background:#f3f8ff;border:1px solid #dbe6f6;color:#0b4db3;font-size:13px;font-weight:900}}
.signal-tags span.tag-mid{{font-size:15px;background:#ecfdf5;color:#0f766e}}
.signal-tags span.tag-large{{font-size:18px;background:#dcecff;color:#062b78}}
.signal-tags em{{font-style:normal;background:#fff;border-radius:999px;padding:2px 6px;color:#64748b;font-size:11px}}
.signal-news-row{{display:grid;grid-template-columns:34px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid #edf2fa}}
.signal-news-rank{{width:30px;height:30px;border-radius:9px;background:#0f766e;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:950}}
.signal-news-title{{font-size:15px;font-weight:950;color:#0d2d68}}
.signal-news-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.signal-news-meta span{{font-size:11px;background:#edf5ff;color:#365379;border-radius:8px;padding:3px 6px;font-weight:800}}
.signal-news-brand{{font-size:12px;color:#0f766e;font-weight:850;margin-top:5px}}
.products{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.product-card{{border:1px solid #dbe6f6;border-radius:18px;background:#fbfdff;padding:12px;box-shadow:0 8px 18px rgba(20,60,110,.06)}}
.product-img-wrap{{position:relative;width:100%;height:150px;border-radius:15px;overflow:hidden;background:#edf5ff;margin-bottom:10px}}
.product-signal-cover{{display:flex;flex-direction:column;justify-content:center;align-items:center;background:radial-gradient(circle at 80% 20%,rgba(25,163,255,.22),transparent 30%),linear-gradient(135deg,#edf5ff,#f8fbff)}}
.product-icon{{font-size:46px;line-height:1;margin-bottom:10px}}
.product-signal-category{{font-size:22px;font-weight:950;color:#0b4db3}}
.product-signal-heat{{margin-top:10px;font-size:14px;font-weight:900;color:#0f766e;background:#ecfdf5;padding:5px 12px;border-radius:999px}}
.product-rank{{position:absolute;top:8px;left:8px;padding:4px 8px;border-radius:999px;background:rgba(6,43,120,.88);color:#fff;font-size:11px;font-weight:950}}
.product-brand{{font-size:13px;color:#0b63d8;font-weight:950}}
.product-name{{font-size:15.5px;line-height:1.35;font-weight:950;color:#0d2d68;margin-top:5px;min-height:42px}}
.product-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;font-size:11px;color:#51698d}}
.product-meta span{{background:#edf5ff;padding:3px 6px;border-radius:8px}}
.product-tags{{margin-top:8px;font-size:12px;color:#1d8c54;font-weight:850}}
.product-insight{{margin-top:10px;padding:10px;border-radius:12px;background:#f0fdf4;color:#166534;font-size:12.5px;line-height:1.45;font-weight:850}}
.suggest-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.suggest-card{{border-radius:18px;background:linear-gradient(135deg,#fff7ed,#ffffff);border:1px solid #fed7aa;padding:16px;font-size:15px;line-height:1.55;font-weight:850;color:#7c2d12;min-height:130px}}
.ai-card{{margin-top:16px;background:linear-gradient(135deg,#f8fbff,#ffffff)}}
.ai-section{{margin-top:14px;padding:14px;border-radius:12px;background:#f8fbff;border:1px solid #dbe6f6}}
.ai-subtitle{{font-size:15px;font-weight:950;color:#0b4db3;margin-bottom:8px}}
.ai-text{{font-size:14px;line-height:1.8;color:#233e68;font-weight:700}}
.ai-content{{font-size:16px;line-height:1.75;font-weight:800;color:#233e68;white-space:pre-wrap}}
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
  <div class="summary-box">{weekly_summary}</div>
  {render_ai_judgement()}
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
