from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import json
import re
import html

HISTORY_DIR = Path("output/history")
WEEKLY_DIR = Path("output/weekly")
PRODUCT_DIR = Path("output/products")

ANALYSIS_FILE = WEEKLY_DIR / "weekly_analysis.json"
PRODUCT_SIGNAL_FILE = PRODUCT_DIR / "latest_product_signals.json"
IMAGE_CACHE_FILE = WEEKLY_DIR / "news_image_cache.json"
OUTPUT_HTML = WEEKLY_DIR / "weekly_report.html"

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load json error: {path} {repr(e)}")
    return default


def safe_list(v):
    return v if isinstance(v, list) else []


def raw(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ").strip())


def esc(v):
    return html.escape(raw(v), quote=True)


def clean_url(v):
    url = raw(v)
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return ""


def short(v, n=42):
    t = raw(v)
    return esc(t if len(t) <= n else t[:n] + "...")


def title_key(title):
    t = raw(title).lower()
    t = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|]+", "", t)
    return t[:60]


def norm_key(v):
    return title_key(v)[:50]


def link_text(title, link, n=42):
    title_html = short(title, n)
    link = clean_url(link)
    if link:
        return f"<a href='{esc(link)}' target='_blank' rel='noopener noreferrer'>{title_html}</a>"
    return title_html


analysis = load_json(ANALYSIS_FILE, {})
image_cache = load_json(IMAGE_CACHE_FILE, {})

product_signals = analysis.get("product_signals") if isinstance(analysis.get("product_signals"), dict) else {}
if not product_signals:
    product_signals = load_json(PRODUCT_SIGNAL_FILE, {})

history_files = sorted(HISTORY_DIR.glob("*.json"))[-7:]
history_days = []
for f in history_files:
    d = load_json(f, {})
    if isinstance(d, dict) and d:
        history_days.append(d)

generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")
summary = analysis.get("summary", {}) if isinstance(analysis.get("summary"), dict) else {}


def parse_ai_json(v):
    if not v:
        return {}
    if isinstance(v, dict):
        return v
    text = raw(v)
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


ai_judgement = parse_ai_json(analysis.get("ai_judgement") or summary.get("ai_judgement"))


def normalize_image_src(src):
    src = raw(src)
    if not src:
        return ""

    if src.startswith("http://") or src.startswith("https://"):
        return src

    src = src.replace("\\", "/")

    if src.startswith("output/weekly/"):
        return src.replace("output/weekly/", "")

    if src.startswith("output/"):
        return "../" + src.replace("output/", "")

    return src


def find_image(title):
    key = title_key(title)

    if isinstance(image_cache, dict):
        if key in image_cache:
            row = image_cache.get(key)
            if isinstance(row, dict):
                return normalize_image_src(
                    row.get("image")
                    or row.get("image_url")
                    or row.get("local_path")
                    or row.get("path")
                )
            return normalize_image_src(row)

        raw_title = raw(title)
        if raw_title in image_cache:
            row = image_cache.get(raw_title)
            if isinstance(row, dict):
                return normalize_image_src(
                    row.get("image")
                    or row.get("image_url")
                    or row.get("local_path")
                    or row.get("path")
                )
            return normalize_image_src(row)

    return ""


def pair_rows(items, key_name):
    rows = []
    for x in safe_list(items):
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            rows.append({key_name: x[0], "count": x[1]})
        elif isinstance(x, dict):
            rows.append(x)
    return rows


def count_row_name(row, keys):
    if not isinstance(row, dict):
        return ""
    for k in keys:
        if row.get(k):
            return raw(row.get(k))
    return ""


BRAND_ALIASES = {
    "安踏儿童": "安踏儿童",
    "安踏": "安踏",
    "FILA KIDS": "FILA KIDS",
    "FILA": "FILA",
    "李宁YOUNG": "李宁YOUNG",
    "李宁": "李宁",
    "特步儿童": "特步儿童",
    "特步": "特步",
    "Nike": "Nike",
    "耐克": "Nike",
    "Adidas": "Adidas",
    "阿迪": "Adidas",
    "阿迪达斯": "Adidas",
    "Puma": "Puma",
    "彪马": "Puma",
    "361儿童": "361儿童",
    "361度": "361",
    "361": "361",
    "巴拉巴拉": "巴拉巴拉",
    "HOKA": "HOKA",
    "昂跑": "On昂跑",
    "On": "On昂跑",
    "亚瑟士": "亚瑟士",
}

EVENT_WORDS = [
    "签约", "代言", "联名", "战略合作", "合作", "新品", "发布", "开店", "开业", "旗舰店",
    "实验室", "创新中心", "研发", "换帅", "总裁", "CEO", "收购", "投资", "出圈", "爆火",
    "防晒", "凉感", "拖鞋", "篮球", "跑鞋", "户外", "618", "大促", "战报", "直播",
]

BAD_WORDS = ["涨停", "跌停", "龙虎榜", "股价", "市值", "证券", "A股", "港股", "比分", "赛程", "转会", "主教练"]


def infer_brand(title):
    for k, v in BRAND_ALIASES.items():
        if k in title:
            return v
    return "行业"


def infer_event(title):
    hits = [w for w in EVENT_WORDS if w in title]
    if "库里" in title or "Curry" in title:
        hits.insert(0, "库里签约")
    if "创新中心" in title or "实验室" in title:
        hits.insert(0, "科技研发")
    if "拖鞋" in title:
        hits.insert(0, "恢复拖鞋")
    return "、".join(dict.fromkeys(hits[:3])) or "行业动态"


def event_impact(title, brand, event):
    text = title + event
    if "库里" in text or "篮球" in text:
        return "篮球专业化、青少年运动心智和明星资产竞争升温"
    if "拖鞋" in text or "恢复" in text:
        return "运动恢复、舒适脚感和夏季出行品类关注提升"
    if "创新中心" in text or "实验室" in text or "科技" in text:
        return "科技研发投入加速，产品专业背书和功能表达重要性提升"
    if "防晒" in text or "凉感" in text:
        return "夏季功能品类进入主推窗口，防晒凉感竞争加剧"
    if "618" in text or "大促" in text or "直播" in text:
        return "平台流量和价格心智强化，线上热词可能外溢到线下"
    if "开店" in text or "旗舰店" in text or "开业" in text:
        return "渠道形象和核心商圈曝光提升，终端体验竞争增强"
    return "品牌声量、品类认知和终端转化均需跟踪"


def collect_news_events():
    output = []

    for source_list in [analysis.get("major_events"), analysis.get("competitor_actions")]:
        for item in safe_list(source_list):
            if not isinstance(item, dict):
                continue

            title = raw(item.get("title"))
            if not title or any(w in title for w in BAD_WORDS):
                continue

            output.append({
                "date": raw(item.get("date")),
                "title": title,
                "brand": raw(item.get("brand")) or infer_brand(title),
                "event": raw(item.get("event_type") or item.get("action_type")) or infer_event(title),
                "source": raw(item.get("source")),
                "impact": raw(item.get("impact") or item.get("insight")) or event_impact(title, raw(item.get("brand")), raw(item.get("event_type"))),
                "score": int(item.get("heat") or 50),
                "link": clean_url(item.get("link")),
                "count": 1,
            })

    if output:
        used = set()
        deduped = []
        for x in sorted(output, key=lambda v: v.get("score", 0), reverse=True):
            key = norm_key(x.get("title"))
            if key in used:
                continue
            used.add(key)
            deduped.append(x)
        return deduped

    pool = []
    for day in history_days:
        date = day.get("date", "")
        for source_key in ["top_news", "competitor_news"]:
            for item in safe_list(day.get(source_key)):
                if not isinstance(item, dict):
                    continue

                title = raw(item.get("title"))
                if not title or any(w in title for w in BAD_WORDS):
                    continue

                brand = raw(item.get("brand")) or infer_brand(title)
                event = infer_event(title)

                base = 1
                if source_key == "competitor_news":
                    base += 2
                if any(w in title for w in EVENT_WORDS):
                    base += 3
                if brand != "行业":
                    base += 2

                pool.append({
                    "date": date,
                    "title": title,
                    "brand": brand,
                    "event": event,
                    "source": raw(item.get("source")),
                    "impact": event_impact(title, brand, event),
                    "score": base + int(item.get("score") or 0) // 10,
                    "link": clean_url(item.get("link")),
                    "count": 1,
                })

    merged = {}
    for x in pool:
        key = norm_key(x["title"])
        if key not in merged:
            merged[key] = x
            merged[key]["count"] = 0
        merged[key]["count"] += 1
        merged[key]["score"] += x.get("score", 0)

    return sorted(merged.values(), key=lambda x: (x.get("score", 0), x.get("count", 0)), reverse=True)


news_events = collect_news_events()


def collect_keywords():
    c = Counter()

    for row in safe_list(analysis.get("keywords")):
        if isinstance(row, dict):
            name = raw(row.get("word") or row.get("keyword") or row.get("name"))
            if name:
                c[name] += int(row.get("count") or 1)
        elif isinstance(row, str):
            c[raw(row)] += 1

    for day in history_days:
        for w in safe_list(day.get("words")):
            if raw(w):
                c[raw(w)] += 1

        for n in safe_list(day.get("top_news")) + safe_list(day.get("competitor_news")):
            if isinstance(n, dict):
                title = raw(n.get("title"))
                for k in EVENT_WORDS:
                    if k in title:
                        c[k] += 1
                b = infer_brand(title)
                if b != "行业":
                    c[b] += 1

    for row in pair_rows(product_signals.get("top_keywords", []), "keyword"):
        name = count_row_name(row, ["keyword", "word", "name"])
        if name:
            c[name] += int(row.get("count") or 1)

    return c.most_common(28)


def collect_brand_heat():
    c = Counter()
    for x in news_events:
        if x["brand"]:
            c[x["brand"]] += x.get("count", 1) + x.get("score", 0)

    for row in pair_rows(product_signals.get("top_brands", []), "brand"):
        name = count_row_name(row, ["brand", "name"])
        if name:
            c[name] += int(row.get("count") or 1)

    return c.most_common(10)


def collect_category_heat():
    rows = pair_rows(product_signals.get("top_categories", []), "category")
    if rows:
        return sorted(rows, key=lambda x: int(x.get("count") or 0), reverse=True)[:10]

    c = Counter()
    text = " ".join([x["title"] for x in news_events]) + " " + " ".join(w for w, _ in collect_keywords())

    rules = {
        "篮球专业": ["篮球", "库里"],
        "防晒凉感": ["防晒", "凉感", "速干"],
        "运动恢复": ["拖鞋", "恢复", "凉鞋"],
        "跑鞋科技": ["跑鞋", "碳板", "缓震"],
        "儿童户外": ["户外", "露营", "文旅"],
        "平台大促": ["618", "直播", "大促"],
    }

    for name, keys in rules.items():
        c[name] = sum(text.count(k) for k in keys)

    return [{"category": k, "count": v} for k, v in c.most_common(10) if v > 0]


def collect_regions():
    out = []
    analysis_regions = analysis.get("regions") or analysis.get("region_analysis") or []

    if isinstance(analysis_regions, list) and analysis_regions:
        for r in analysis_regions[:6]:
            if isinstance(r, dict):
                out.append({
                    "name": raw(r.get("region") or r.get("name") or "重点区域"),
                    "summary": raw(r.get("summary") or ""),
                    "suggestion": raw(r.get("suggestion") or ""),
                })

    if out:
        return out

    region_counter = defaultdict(list)

    for day in history_days:
        rr = day.get("region_reports")
        if isinstance(rr, dict):
            for _, r in rr.items():
                if isinstance(r, dict):
                    name = raw(r.get("name") or r.get("region"))
                    if name:
                        region_counter[name].append(
                            "；".join([raw(r.get(k)) for k in ["hot", "flow", "focus", "action"] if raw(r.get(k))])
                        )

    for name, texts in region_counter.items():
        out.append({
            "name": name,
            "summary": "；".join(texts[:2]),
            "suggestion": "结合天气、商圈和主推品类做区域差异化承接"
        })

    return out[:6]


def build_product_cards():
    signals = safe_list(product_signals.get("signals"))
    cards = []
    seen = set()

    for s in sorted([x for x in signals if isinstance(x, dict)], key=lambda x: int(x.get("heat") or 0), reverse=True):
        title = raw(s.get("short_title") or s.get("title"))
        if not title:
            continue

        key = norm_key(title)
        if key in seen:
            continue
        seen.add(key)

        keys = safe_list(s.get("keyword_hits"))[:3]
        brands = safe_list(s.get("brand_hits"))[:2]
        category = raw(s.get("category") or "商品趋势")
        text = title + " ".join(keys) + category

        icon = "👟"
        if any(k in text for k in ["防晒", "凉感", "速干"]):
            icon = "☀️"
        elif any(k in text for k in ["篮球", "库里"]):
            icon = "🏀"
        elif any(k in text for k in ["户外", "冲锋衣", "露营"]):
            icon = "⛰️"
        elif any(k in text for k in ["拖鞋", "凉鞋", "恢复"]):
            icon = "🩴"
        elif any(k in text for k in ["校园", "开学"]):
            icon = "🎒"

        insight = "关注商品卖点、竞品表达和终端陈列承接。"
        if "篮球" in text or "库里" in text:
            insight = "篮球专业化升温，可跟踪青少年篮球鞋与训练装备。"
        if "防晒" in text or "凉感" in text:
            insight = "夏季功能品类升温，建议关注防晒凉感组合。"
        if "拖鞋" in text or "恢复" in text:
            insight = "运动恢复与舒适出行场景值得重点跟踪。"

        cards.append({
            "title": title,
            "brand": "、".join([raw(b) for b in brands]) or infer_brand(title),
            "category": category,
            "heat": s.get("heat", ""),
            "tags": keys,
            "source": raw(s.get("source")),
            "icon": icon,
            "insight": insight,
            "link": clean_url(s.get("link")),
            "image": normalize_image_src(s.get("image") or s.get("image_url") or find_image(title)),
        })

        if len(cards) >= 12:
            break

    return cards


keywords = collect_keywords()
brand_heat = collect_brand_heat()
category_heat = collect_category_heat()
regions = collect_regions()
product_cards = build_product_cards()
signal_count = int(product_signals.get("signal_count") or len(safe_list(product_signals.get("signals"))) or 0)


def auto_core_points():
    points = []
    titles = " ".join([x["title"] for x in news_events])

    if "库里" in titles or "篮球" in titles:
        points.append("篮球专业化成为本周最明确的品牌竞争线索，明星资产与青少年运动心智同步升温。")
    if "拖鞋" in titles or "恢复" in titles:
        points.append("运动恢复与舒适出行场景热度提升，夏季鞋类机会不只集中在跑鞋和凉鞋。")
    if "创新中心" in titles or "实验室" in titles:
        points.append("品牌继续加码研发和专业科技表达，产品背书竞争进一步前置。")
    if any(k in titles for k in ["防晒", "凉感", "速干"]):
        points.append("防晒、凉感、速干仍是夏季最大确定性品类，需关注功能表达和组合销售。")
    if any(k in titles for k in ["618", "大促", "直播"]):
        points.append("618与直播内容持续影响消费者价格心智，线上爆款与线下陈列需联动观察。")

    if not points:
        points = ["本周行业热点主要围绕品牌动作、商品功能、平台流量和区域客流展开，需持续跟踪新闻事实变化。"]

    return points[:5]


def summary_text():
    if summary.get("core_judgement"):
        return raw(summary.get("core_judgement"))
    if ai_judgement.get("weekly_core_view"):
        return raw(ai_judgement.get("weekly_core_view"))
    return " ".join(auto_core_points()[:3])


def render_core_cards():
    html_text = ""
    icons = ["①", "②", "③", "④", "⑤"]

    for i, p in enumerate(auto_core_points()):
        html_text += f"<div class='core-card'><b>{icons[i]}</b><span>{esc(p)}</span></div>"

    return html_text


def render_event_table():
    if not news_events:
        return "<div class='empty'>暂无本周重大事件</div>"

    rows = ""

    for i, x in enumerate(news_events[:10], start=1):
        img = find_image(x.get("title"))
        title_html = link_text(x.get("title"), x.get("link"), 42)

        if img:
            event_main = f"""
            <div class='event-news'>
              <img src='{esc(img)}' loading='lazy'>
              <div>{title_html}<em>{esc(x.get('source',''))}</em></div>
            </div>
            """
        else:
            event_main = f"{title_html}<em>{esc(x.get('source',''))}</em>"

        rows += f"""
        <tr>
          <td><span class='rank'>{i}</span></td>
          <td class='event-title'>{event_main}</td>
          <td>{esc(x.get('brand'))}</td>
          <td>{esc(x.get('event'))}</td>
          <td>{esc(x.get('impact'))}</td>
        </tr>
        """

    return f"""
    <table class='event-table'>
      <thead>
        <tr>
          <th>#</th>
          <th>事件</th>
          <th>品牌</th>
          <th>类型</th>
          <th>影响判断</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def render_brand_bars():
    if not brand_heat:
        return "<div class='empty'>暂无品牌热度</div>"

    max_v = max(v for _, v in brand_heat[:8]) or 1
    html_text = ""

    for i, (name, v) in enumerate(brand_heat[:8], start=1):
        w = max(8, int(v / max_v * 100))
        html_text += f"<div class='bar-row'><label>{i}. {esc(name)}</label><div class='bar'><i style='width:{w}%'></i></div><b>{v}</b></div>"

    return html_text


def render_category_bars():
    if not category_heat:
        return "<div class='empty'>暂无品类热度</div>"

    rows = []

    for x in category_heat[:8]:
        name = raw(x.get("category") or x.get("name") or "")
        cnt = int(x.get("count") or 0)
        rows.append((name, cnt))

    max_v = max([v for _, v in rows] + [1])
    html_text = ""

    for i, (name, v) in enumerate(rows, start=1):
        w = max(8, int(v / max_v * 100))
        html_text += f"<div class='bar-row'><label>{i}. {esc(name)}</label><div class='bar green'><i style='width:{w}%'></i></div><b>{v}</b></div>"

    return html_text


def render_keyword_cloud():
    if not keywords:
        return "<div class='empty'>暂无热词</div>"

    html_text = ""

    for i, (w, c) in enumerate(keywords[:24], start=1):
        cls = "kw big" if i <= 4 else "kw mid" if i <= 10 else "kw"
        html_text += f"<span class='{cls}'>{esc(w)}</span>"

    return html_text


def render_regions():
    if not regions:
        return "<div class='empty'>暂无区域机会</div>"

    html_text = ""

    for r in regions[:6]:
        html_text += f"""
        <div class='region-card'>
          <h3>{esc(r.get('name'))}</h3>
          <p>{esc(r.get('summary') or '本周关注区域客流、天气品类和商圈活动变化。')}</p>
          <b>{esc(r.get('suggestion') or '建议结合门店主推、会员触达和陈列策略做承接。')}</b>
        </div>
        """

    return html_text


def render_product_cards():
    if not product_cards:
        return "<div class='empty'>暂无商品趋势信号</div>"

    html_text = ""

    for i, p in enumerate(product_cards[:12], start=1):
        tags = " / ".join(p.get("tags", []))
        title_html = link_text(p.get("title"), p.get("link"), 36)
        img = p.get("image") or find_image(p.get("title"))

        if img:
            cover = f"""
            <div class='product-cover has-img'>
              <span>TOP {i}</span>
              <img src='{esc(img)}' loading='lazy'>
              <strong>{esc(p.get('category'))}</strong>
            </div>
            """
        else:
            cover = f"""
            <div class='product-cover'>
              <span>TOP {i}</span>
              <i>{p.get('icon')}</i>
              <strong>{esc(p.get('category'))}</strong>
              <em>热度 {esc(p.get('heat'))}</em>
            </div>
            """

        html_text += f"""
        <div class='product-card'>
          {cover}
          <h4>{title_html}</h4>
          <p class='brand'>{esc(p.get('brand'))}｜{esc(p.get('source'))}</p>
          <p class='tags'>{esc(tags)}</p>
          <p class='insight'>{esc(p.get('insight'))}</p>
        </div>
        """

    return html_text


def render_ai():
    if not ai_judgement:
        return ""

    if ai_judgement.get("raw"):
        return f"<div class='ai-box'><h3>AI经营判断</h3><p>{esc(ai_judgement.get('raw'))}</p></div>"

    blocks = [
        ("核心判断", "weekly_core_view"),
        ("新闻变化", "news_summary"),
        ("竞品动作", "competitor_summary"),
        ("商品趋势", "product_summary"),
        ("区域天气", "region_weather_summary"),
        ("下周重点", "next_week_focus"),
    ]

    inner = ""

    for title, key in blocks:
        if ai_judgement.get(key):
            inner += f"<div><b>{title}</b><p>{esc(ai_judgement.get(key))}</p></div>"

    return f"<div class='ai-box'><h3>AI经营判断</h3>{inner}</div>" if inner else ""


def render_planning():
    suggestions = analysis.get("product_suggestions") if isinstance(analysis.get("product_suggestions"), list) else []

    if not suggestions:
        suggestions = [
            "围绕篮球专业化，跟踪青少年篮球鞋、训练服和校园运动装备。",
            "围绕防晒凉感，强化防晒衣、凉感T、速干短裤、运动凉鞋组合。",
            "围绕运动恢复，关注恢复拖鞋、舒适脚感和夏季出行鞋类机会。",
            "围绕科技研发，强化中底科技、足弓支撑和专业功能表达。",
        ]

    html_text = ""

    for s in suggestions[:4]:
        if isinstance(s, dict):
            text = s.get("suggestion") or s.get("desc") or s.get("title") or ""
        else:
            text = s

        html_text += f"<div class='plan-card'>{esc(text)}</div>"

    return html_text


date_range = summary.get("date_range") or (
    f"{history_days[0].get('date')} 至 {history_days[-1].get('date')}" if history_days else "最近7天"
)

html_text = f"""
<!DOCTYPE html>
<html lang='zh-CN'>
<head>
<meta charset='UTF-8'>
<title>运动品牌行业周报</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#eef4fb;font-family:'Microsoft YaHei','PingFang SC',Arial,sans-serif;color:#122b54;padding:24px}}
.report{{width:1280px;margin:0 auto}}
.cover{{height:300px;border-radius:30px;padding:38px 44px;position:relative;overflow:hidden;color:#fff;background:radial-gradient(circle at 84% 18%,rgba(255,142,31,.42),transparent 25%),radial-gradient(circle at 12% 90%,rgba(255,255,255,.18),transparent 30%),linear-gradient(135deg,#06235f,#075bd2 58%,#18a2ff);box-shadow:0 24px 50px rgba(6,42,111,.26);margin-bottom:20px}}
.cover:after{{content:'';position:absolute;right:-120px;bottom:-160px;width:480px;height:480px;border-radius:50%;border:48px solid rgba(255,255,255,.13)}}
.cover-tag{{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);padding:8px 15px;border-radius:999px;font-size:14px;font-weight:900;margin-bottom:20px}}
.cover h1{{font-size:60px;letter-spacing:-1px;line-height:1;font-weight:950}}
.cover h2{{font-size:23px;margin-top:16px;font-weight:850;opacity:.95}}
.cover-foot{{position:absolute;left:44px;bottom:30px;font-size:14px;font-weight:800;opacity:.9}}
.stats{{position:absolute;right:38px;top:38px;display:grid;grid-template-columns:repeat(4,104px);gap:10px}}
.stat{{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);border-radius:18px;padding:14px 8px;text-align:center;backdrop-filter:blur(6px)}}
.stat b{{font-size:31px;display:block}}
.stat span{{font-size:12px;font-weight:800;opacity:.9}}
.page{{background:#fff;border-radius:26px;padding:24px;box-shadow:0 16px 36px rgba(25,56,105,.12);margin-bottom:18px}}
.head{{display:flex;align-items:end;justify-content:space-between;border-bottom:2px solid #e3edf9;padding-bottom:12px;margin-bottom:18px}}
.head h2{{font-size:27px;color:#062b78;font-weight:950}}
.head span{{font-size:12px;color:#0b63d8;font-weight:950;letter-spacing:.8px}}
.summary{{font-size:20px;line-height:1.75;font-weight:850;color:#0d2d68;background:linear-gradient(135deg,#f6f9ff,#eef6ff);border:1px solid #dce8f8;border-radius:20px;padding:20px}}
.core-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:16px}}
.core-card{{background:#fbfdff;border:1px solid #dbe6f6;border-radius:18px;padding:16px;min-height:135px}}
.core-card b{{display:block;color:#ff7a00;font-size:24px;margin-bottom:8px}}
.core-card span{{font-size:15px;line-height:1.55;font-weight:850;color:#244268}}
.ai-box{{margin-top:16px;border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:18px}}
.ai-box h3{{color:#0b4db3;margin-bottom:12px}}
.ai-box div{{background:#f5f9ff;border-radius:14px;padding:12px;margin-top:10px}}
.ai-box b{{color:#0b4db3}}
.ai-box p{{font-size:14px;line-height:1.7;font-weight:760;margin-top:5px}}
.event-table{{width:100%;border-collapse:collapse}}
.event-table th{{text-align:left;background:#f3f8ff;color:#0b4db3;font-size:13px;padding:12px;border-bottom:1px solid #dbe6f6}}
.event-table td{{font-size:14px;line-height:1.45;font-weight:760;color:#233e68;padding:12px;border-bottom:1px solid #edf2fa;vertical-align:top}}
.rank{{display:inline-flex;width:28px;height:28px;align-items:center;justify-content:center;background:#0b63d8;color:#fff;border-radius:9px;font-weight:950}}
.event-title{{font-weight:950;color:#0d2d68}}
.event-title em{{display:block;font-size:11px;color:#7b8ca8;font-style:normal;margin-top:4px}}
.event-news{{display:flex;gap:12px;align-items:center;min-width:360px}}
.event-news img{{width:92px;height:62px;border-radius:12px;object-fit:cover;background:#edf5ff;border:1px solid #dbe6f6}}
.event-title a,.product-card h4 a{{color:#0b63d8;text-decoration:none}}
.event-title a:hover,.product-card h4 a:hover{{text-decoration:underline}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.panel{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:18px}}
.panel h3{{font-size:18px;color:#0b4db3;margin-bottom:14px}}
.bar-row{{display:grid;grid-template-columns:118px 1fr 42px;gap:10px;align-items:center;margin-bottom:12px}}
.bar-row label{{font-size:13px;font-weight:900;color:#183a76;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bar-row b{{font-size:13px;color:#0b63d8;text-align:right}}
.bar{{height:10px;background:#edf5ff;border-radius:999px;overflow:hidden}}
.bar i{{display:block;height:100%;background:linear-gradient(90deg,#0b63d8,#18a2ff);border-radius:999px}}
.bar.green i{{background:linear-gradient(90deg,#0f766e,#34d399)}}
.word-cloud{{min-height:260px;border:1px solid #dbe6f6;border-radius:20px;background:linear-gradient(135deg,#f8fbff,#eef6ff);display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:14px 18px;padding:22px}}
.kw{{background:#fff;border:1px solid #dbe6f6;border-radius:999px;padding:7px 14px;font-size:14px;font-weight:950;color:#0b63d8;box-shadow:0 6px 14px rgba(20,60,110,.06)}}
.kw.mid{{font-size:17px;background:#ecfdf5;color:#0f766e}}
.kw.big{{font-size:25px;background:#dcecff;color:#062b78}}
.region-card{{border:1px solid #dbe6f6;border-radius:20px;background:linear-gradient(135deg,#f7fbff,#fff);padding:17px;min-height:170px}}
.region-card h3{{font-size:21px;color:#0b4db3;margin-bottom:10px}}
.region-card p{{font-size:14px;line-height:1.55;font-weight:760;color:#315174}}
.region-card b{{display:block;margin-top:10px;font-size:13px;line-height:1.5;color:#0f766e}}
.products{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.product-card{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:13px;box-shadow:0 8px 18px rgba(20,60,110,.06)}}
.product-cover{{height:150px;border-radius:16px;background:radial-gradient(circle at 80% 20%,rgba(25,163,255,.22),transparent 30%),linear-gradient(135deg,#edf5ff,#f8fbff);display:flex;align-items:center;justify-content:center;flex-direction:column;position:relative;margin-bottom:11px;overflow:hidden}}
.product-cover span{{position:absolute;top:8px;left:8px;background:#062b78;color:#fff;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:950;z-index:2}}
.product-cover i{{font-style:normal;font-size:46px}}
.product-cover strong{{font-size:21px;color:#0b4db3;margin-top:8px;z-index:2}}
.product-cover em{{font-style:normal;color:#0f766e;background:#ecfdf5;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:900;margin-top:8px}}
.product-cover.has-img img{{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}}
.product-cover.has-img:after{{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.05),rgba(6,35,95,.55))}}
.product-cover.has-img strong{{position:absolute;left:12px;bottom:12px;color:#fff;font-size:18px;text-shadow:0 2px 8px rgba(0,0,0,.35)}}
.product-card h4{{font-size:15.5px;line-height:1.35;color:#0d2d68;min-height:42px}}
.brand{{font-size:12px;color:#0b63d8;font-weight:900;margin-top:6px}}
.tags{{font-size:12px;color:#1d8c54;font-weight:850;margin-top:7px}}
.insight{{margin-top:9px;background:#f0fdf4;color:#166534;border-radius:12px;padding:9px;font-size:12.5px;line-height:1.45;font-weight:850}}
.plan-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.plan-card{{border-radius:18px;background:linear-gradient(135deg,#fff7ed,#fff);border:1px solid #fed7aa;color:#7c2d12;font-size:15px;line-height:1.6;font-weight:850;padding:17px;min-height:132px}}
.empty{{color:#8a99ad;font-size:14px;text-align:center;padding:24px}}
.footer{{text-align:center;color:#7184a3;font-size:12px;margin:16px 0 4px}}
</style>
</head>
<body>
<div class='report'>
  <section class='cover'>
    <div class='cover-tag'>361°儿童 · 周度行业情报</div>
    <h1>运动品牌行业周报</h1>
    <h2>新闻事实驱动｜品牌动作 × 商品趋势 × 平台流量 × 区域机会</h2>
    <div class='cover-foot'>统计周期：{esc(date_range)} ｜ 生成时间：{generated_time}</div>
    <div class='stats'>
      <div class='stat'><b>{len(history_days)}</b><span>日报样本</span></div>
      <div class='stat'><b>{len(news_events)}</b><span>事件样本</span></div>
      <div class='stat'><b>{len(keywords)}</b><span>行业热词</span></div>
      <div class='stat'><b>{signal_count}</b><span>商品信号</span></div>
    </div>
  </section>

  <section class='page'>
    <div class='head'><h2>P2｜本周核心结论</h2><span>WEEKLY JUDGEMENT</span></div>
    <div class='summary'>{esc(summary_text())}</div>
    <div class='core-grid'>{render_core_cards()}</div>
    {render_ai()}
  </section>

  <section class='page'>
    <div class='head'><h2>P3-P4｜本周行业重大事件 TOP10</h2><span>NEWS CHANGES DRIVE CONTENT</span></div>
    {render_event_table()}
  </section>

  <section class='page'>
    <div class='head'><h2>P5-P7｜竞品热度与趋势地图</h2><span>BRAND / CATEGORY / KEYWORDS</span></div>
    <div class='grid-2'>
      <div class='panel'><h3>品牌热度排行</h3>{render_brand_bars()}</div>
      <div class='panel'><h3>品类/场景热度排行</h3>{render_category_bars()}</div>
    </div>
    <div style='height:16px'></div>
    <div class='word-cloud'>{render_keyword_cloud()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P8｜儿童行业专题 / 商品趋势信号</h2><span>PRODUCT SIGNALS</span></div>
    <div class='products'>{render_product_cards()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P9｜本周机会赛道</h2><span>OPPORTUNITY LANES</span></div>
    <div class='grid-3'>{render_regions()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P10｜对361°儿童启示</h2><span>NEXT ACTION</span></div>
    <div class='plan-grid'>{render_planning()}</div>
  </section>

  <div class='footer'>数据来源：TrendRadar 日报历史库 / 周报分析库 / 商品趋势信号库 ｜ 内容随每周新闻事实自动变化</div>
</div>
</body>
</html>
"""

OUTPUT_HTML.write_text(html_text, encoding="utf-8")

print(f"weekly html generated: {OUTPUT_HTML}")
print(f"news events: {len(news_events)} | keywords: {len(keywords)} | product signals: {signal_count}")
print(f"event link count: {sum(1 for x in news_events if x.get('link'))}")
print(f"product link count: {sum(1 for x in product_cards if x.get('link'))}")
print(f"event image count: {sum(1 for x in news_events if find_image(x.get('title')))}")
print(f"product image count: {sum(1 for x in product_cards if x.get('image') or find_image(x.get('title')))}")
