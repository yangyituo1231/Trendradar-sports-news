from pathlib import Path
from datetime import datetime
import json
import re
from collections import Counter
from urllib.parse import quote

WEEKLY_FILE = Path("output/weekly/latest_week.json")
ANALYSIS_FILE = Path("output/weekly/weekly_analysis.json")
PRODUCT_FILE = Path("output/products/latest_products.json")

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
    return text


def short(text, n=36):
    text = clean(text)
    return text if len(text) <= n else text[:n] + "..."


def get_list(data, key):
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def dict_to_sentence(item):
    if not isinstance(item, dict):
        return clean(item)

    theme = item.get("theme", "")
    heat = item.get("heat", "")
    suggestion = item.get("suggestion", "")
    risk = item.get("risk", "")
    action = item.get("action", "")
    title = item.get("title", "")

    parts = []
    if theme:
        parts.append(f"【{theme}】")
    elif title:
        parts.append(f"【{title}】")

    if heat != "":
        parts.append(f"热度{heat}。")
    if suggestion:
        parts.append(suggestion)
    elif risk:
        parts.append(risk)
    elif action:
        parts.append(action)

    return "".join(parts) or clean(item)


def render_list(items, limit=5):
    html = ""
    for item in items[:limit]:
        html += f"<li>{dict_to_sentence(item)}</li>"
    return html


weekly = load_json(WEEKLY_FILE, {})
analysis = load_json(ANALYSIS_FILE, {})
products_data = load_json(PRODUCT_FILE, {})

generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")

days = get_list(weekly, "days")
top_news = get_list(weekly, "top_news")
keywords = get_list(weekly, "keywords")
regions = get_list(weekly, "regions")

news_titles = []
for item in top_news:
    if isinstance(item, dict):
        title = item.get("title", "")
        if title:
            news_titles.append(clean(title))
    elif isinstance(item, str):
        news_titles.append(clean(item))

top_news_list = Counter(news_titles).most_common(8)

keyword_values = []
for item in keywords:
    if isinstance(item, dict):
        for k in ["word", "keyword", "name", "title"]:
            if item.get(k):
                keyword_values.append(clean(item.get(k)))
                break
    elif isinstance(item, str):
        keyword_values.append(clean(item))

top_keywords = Counter(keyword_values).most_common(22)

region_values = []
for item in regions:
    if isinstance(item, dict):
        name = item.get("region") or item.get("name") or item.get("area")
        if name:
            region_values.append(clean(name))
    elif isinstance(item, str):
        region_values.append(clean(item))

top_regions = Counter(region_values).most_common(6)

summary_raw = analysis.get("summary") or analysis.get("weekly_summary") or ""

if isinstance(summary_raw, dict):
    date_range = summary_raw.get("date_range", "")
    core_judgement = summary_raw.get("core_judgement", "")
    product_direction = summary_raw.get("product_direction", "")
    regional_direction = summary_raw.get("regional_direction", "")
    next_action = summary_raw.get("next_action", "")

    weekly_summary = "｜".join([
        x for x in [
            f"统计周期：{date_range}" if date_range else "",
            core_judgement,
            product_direction,
            regional_direction,
            next_action
        ] if x
    ])
else:
    weekly_summary = clean(
        summary_raw
        or "本周行业热点围绕运动消费、平台流量、天气品类、儿童运动和轻户外场景展开，后续需重点关注商品节奏、区域客流和热卖品类变化。"
    )

opportunities = get_list(analysis, "opportunities")
risks = get_list(analysis, "risks")
actions = get_list(analysis, "actions")
product_suggestions = get_list(analysis, "product_suggestions")

if not opportunities:
    opportunities = [
        "夏季功能品类继续升温，防晒、凉感、速干、透气鞋服值得重点跟踪。",
        "儿童运动场景成人化趋势明显，青少年跑鞋、篮球鞋、训练服存在成长机会。",
        "轻户外、城市骑行、文旅出行带动帽包、外套、户外鞋及亲子组合需求。"
    ]

if not risks:
    risks = [
        "平台大促强化价格心智，门店需关注折扣敏感度和核心价格带竞争。",
        "天气波动可能扰动线下客流，降雨区域需强化室内运动和防滑防雨商品承接。",
        "品牌竞争加剧，爆款同质化风险提升，需通过场景陈列和组合销售提升转化。"
    ]

if not actions:
    actions = [
        "重点跟踪防晒、凉感、速干、透气鞋、运动凉鞋等夏季功能品类。",
        "围绕青少年运动、校园体育、亲子运动做商品组合和内容表达。",
        "将线上热词、平台爆款和门店陈列联动，形成周度商品机会清单。"
    ]

if not product_suggestions:
    product_suggestions = [
        "增加青少年跑鞋、篮球鞋、训练服的成人化设计表达。",
        "强化防晒衣、凉感T恤、速干短裤、运动凉鞋组合开发。",
        "补充轻户外鞋服、帽包配件、亲子同款和校园运动套装。"
    ]


product_cards = []
brands = products_data.get("brands", [])

if isinstance(brands, list):
    for brand_block in brands:
        brand = brand_block.get("brand", "")
        products = brand_block.get("products", [])
        if not isinstance(products, list):
            continue

        for p in products:
            product_cards.append({
                "brand": brand,
                "name": p.get("name", ""),
                "category": p.get("category", ""),
                "price": p.get("price", ""),
                "heat": p.get("sales_heat", 0),
                "trend": p.get("trend", ""),
                "tags": p.get("tags", []),
                "reason": p.get("reason", ""),
                "image": p.get("image", "")
            })

product_cards = sorted(product_cards, key=lambda x: int(x.get("heat") or 0), reverse=True)[:12]


def image_url(p):
    img = clean(p.get("image", ""))
    if img:
        return img
    text = quote(f"{p.get('brand','')} {p.get('category','')}")
    return f"https://placehold.co/420x300/eaf2ff/0b4db3?text={text}"


def render_news():
    if not top_news_list:
        return "<div class='empty'>暂无本周重点资讯数据</div>"

    html = ""
    for i, (title, count) in enumerate(top_news_list, start=1):
        html += f"""
        <div class="news-row">
          <div class="news-rank">{i}</div>
          <div>
            <div class="news-title">{short(title, 48)}</div>
            <div class="news-meta">本周出现 {count} 次</div>
          </div>
        </div>
        """
    return html


def render_keywords():
    if not top_keywords:
        data = [(x, 1) for x in ["防晒", "凉感", "速干", "轻户外", "儿童运动", "青少年", "情绪消费", "城市骑行", "AI电商", "会员复购"]]
    else:
        data = top_keywords

    html = ""
    for i, (word, count) in enumerate(data[:22], start=1):
        cls = "hot-word big" if i <= 3 else "hot-word mid" if i <= 9 else "hot-word"
        html += f"<span class='{cls}'>{word}</span>"
    return html


def render_regions():
    if not top_regions:
        rows = [
            ("华东", "关注商圈活动、亲子运动与夏季功能品类。"),
            ("华南", "关注降雨天气、防滑防雨与室内运动承接。"),
            ("西南", "关注文旅出行、轻户外和直播承接。"),
            ("西北", "关注防晒、户外和价格带机会。"),
        ]
    else:
        rows = [(name, f"本周出现 {count} 次，建议跟踪区域客流、天气品类和主推商品。") for name, count in top_regions]

    html = ""
    for name, desc in rows[:6]:
        html += f"""
        <div class="region-card">
          <div class="region-name">{name}</div>
          <div class="region-desc">{desc}</div>
        </div>
        """
    return html


def render_product_cards():
    if not product_cards:
        return "<div class='empty'>暂无商品趋势数据</div>"

    html = ""
    for idx, p in enumerate(product_cards, start=1):
        tags = p.get("tags", [])
        tag_text = " / ".join(tags[:3]) if isinstance(tags, list) else ""
        trend = p.get("trend", "")
        trend_text = {"up": "上升", "hot": "高热", "flat": "平稳", "new": "新品"}.get(trend, trend)

        html += f"""
        <div class="product-card">
          <div class="product-img-wrap">
            <img class="product-img" src="{image_url(p)}" alt="">
            <div class="product-rank">TOP {idx}</div>
          </div>
          <div class="product-brand">{p.get("brand", "")}</div>
          <div class="product-name">{short(p.get("name", ""), 30)}</div>
          <div class="product-meta">
            <span>{p.get("category", "")}</span>
            <span>¥{p.get("price", "")}</span>
            <span>热度 {p.get("heat", "")}</span>
            <span>{trend_text}</span>
          </div>
          <div class="product-tags">{tag_text}</div>
        </div>
        """
    return html


def render_product_suggestion_cards():
    html = ""
    for item in product_suggestions[:4]:
        html += f"<div class='suggest-card'>{dict_to_sentence(item)}</div>"
    return html


html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>运动品牌行业周报</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:#eaf1fb;
  font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;
  color:#102a5c;
  padding:24px;
}}
.report{{
  width:1280px;
  margin:auto;
}}
.cover{{
  position:relative;
  height:260px;
  border-radius:26px;
  overflow:hidden;
  background:
    radial-gradient(circle at 85% 20%, rgba(255,139,0,.32), transparent 28%),
    radial-gradient(circle at 16% 88%, rgba(11,99,216,.24), transparent 30%),
    linear-gradient(135deg,#052b78 0%,#0b63d8 52%,#1d8fff 100%);
  color:#fff;
  padding:34px 42px;
  box-shadow:0 20px 46px rgba(9,55,128,.26);
  margin-bottom:18px;
}}
.cover::after{{
  content:"";
  position:absolute;
  right:-80px;
  bottom:-120px;
  width:420px;
  height:420px;
  border-radius:50%;
  border:42px solid rgba(255,255,255,.12);
}}
.cover-tag{{
  display:inline-block;
  padding:7px 14px;
  border-radius:999px;
  background:rgba(255,255,255,.16);
  font-size:14px;
  font-weight:900;
  margin-bottom:18px;
}}
.cover-title{{
  font-size:56px;
  line-height:1.05;
  font-weight:950;
  letter-spacing:-1px;
}}
.cover-sub{{
  margin-top:14px;
  font-size:22px;
  font-weight:850;
  opacity:.95;
}}
.cover-footer{{
  position:absolute;
  left:42px;
  bottom:28px;
  font-size:15px;
  font-weight:800;
  opacity:.9;
}}
.stats{{
  position:absolute;
  right:34px;
  top:34px;
  display:grid;
  grid-template-columns:repeat(3,112px);
  gap:10px;
}}
.stat{{
  background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.24);
  border-radius:18px;
  padding:15px 12px;
  text-align:center;
  backdrop-filter:blur(6px);
}}
.stat-num{{
  font-size:32px;
  font-weight:950;
}}
.stat-label{{
  font-size:12px;
  margin-top:4px;
  opacity:.9;
}}

.page{{
  background:#fff;
  border-radius:24px;
  padding:22px;
  box-shadow:0 18px 38px rgba(20,50,100,.12);
  margin-bottom:18px;
}}
.section-head{{
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:15px;
  border-bottom:2px solid #e1ebf8;
  padding-bottom:10px;
}}
.section-title{{
  font-size:25px;
  font-weight:950;
  color:#062b78;
}}
.section-kicker{{
  color:#0b63d8;
  font-weight:950;
  font-size:13px;
}}
.summary-box{{
  background:linear-gradient(135deg,#f4f8ff,#eef6ff);
  border:1px solid #dbe6f6;
  border-radius:20px;
  padding:20px 22px;
  font-size:20px;
  line-height:1.7;
  font-weight:850;
  color:#0d2d68;
}}
.grid-2{{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px;
}}
.grid-3{{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:14px;
}}
.card{{
  border:1px solid #dbe6f6;
  border-radius:18px;
  background:#fbfdff;
  padding:16px;
}}
.card-title{{
  font-size:17px;
  font-weight:950;
  color:#0b4db3;
  margin-bottom:10px;
}}
ul{{padding-left:20px}}
li{{
  margin-bottom:10px;
  font-size:15px;
  line-height:1.55;
  font-weight:760;
  color:#233e68;
}}
.news-row{{
  display:grid;
  grid-template-columns:38px 1fr;
  gap:12px;
  align-items:center;
  padding:10px 0;
  border-bottom:1px solid #edf2fa;
}}
.news-row:last-child{{border-bottom:none}}
.news-rank{{
  width:32px;
  height:32px;
  border-radius:10px;
  background:linear-gradient(135deg,#063b88,#0d7df2);
  color:#fff;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:950;
}}
.news-title{{
  font-size:15.5px;
  font-weight:950;
  color:#0d2d68;
}}
.news-meta{{
  font-size:12px;
  color:#6b7f9f;
  margin-top:3px;
}}
.word-cloud{{
  min-height:250px;
  padding:22px;
  display:flex;
  flex-wrap:wrap;
  align-content:center;
  justify-content:center;
  gap:14px 18px;
  background:linear-gradient(135deg,#f8fbff,#eef6ff);
  border-radius:18px;
  border:1px solid #dbe6f6;
}}
.hot-word{{
  font-weight:950;
  color:#0b63d8;
  background:#fff;
  border:1px solid #dbe6f6;
  border-radius:999px;
  padding:7px 14px;
  font-size:14px;
  box-shadow:0 5px 14px rgba(20,60,110,.06);
}}
.hot-word.mid{{
  font-size:17px;
  color:#0f766e;
  background:#ecfdf5;
}}
.hot-word.big{{
  font-size:24px;
  color:#062b78;
  background:#dcecff;
}}
.region-card{{
  border-radius:18px;
  background:linear-gradient(135deg,#f7fbff,#ffffff);
  border:1px solid #dbe6f6;
  padding:16px;
  min-height:112px;
}}
.region-name{{
  font-size:20px;
  font-weight:950;
  color:#0b4db3;
  margin-bottom:8px;
}}
.region-desc{{
  font-size:14.5px;
  line-height:1.5;
  color:#315174;
  font-weight:750;
}}
.products{{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:16px;
}}
.product-card{{
  border:1px solid #dbe6f6;
  border-radius:18px;
  background:#fbfdff;
  padding:12px;
  box-shadow:0 8px 18px rgba(20,60,110,.06);
}}
.product-img-wrap{{
  position:relative;
  width:100%;
  height:150px;
  border-radius:15px;
  overflow:hidden;
  background:#edf5ff;
  margin-bottom:10px;
}}
.product-img{{
  width:100%;
  height:100%;
  object-fit:cover;
  display:block;
}}
.product-rank{{
  position:absolute;
  top:8px;
  left:8px;
  padding:4px 8px;
  border-radius:999px;
  background:rgba(6,43,120,.88);
  color:#fff;
  font-size:11px;
  font-weight:950;
}}
.product-brand{{
  font-size:13px;
  color:#0b63d8;
  font-weight:950;
}}
.product-name{{
  font-size:15.5px;
  line-height:1.35;
  font-weight:950;
  color:#0d2d68;
  margin-top:5px;
  min-height:42px;
}}
.product-meta{{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  margin-top:8px;
  font-size:11px;
  color:#51698d;
}}
.product-meta span{{
  background:#edf5ff;
  padding:3px 6px;
  border-radius:8px;
}}
.product-tags{{
  margin-top:8px;
  font-size:12px;
  color:#1d8c54;
  font-weight:850;
}}
.suggest-grid{{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:14px;
}}
.suggest-card{{
  border-radius:18px;
  background:linear-gradient(135deg,#fff7ed,#ffffff);
  border:1px solid #fed7aa;
  padding:16px;
  font-size:15px;
  line-height:1.55;
  font-weight:850;
  color:#7c2d12;
  min-height:130px;
}}
.footer{{
  text-align:center;
  color:#7184a3;
  font-size:12px;
  margin:14px 0 4px;
}}
.empty{{
  color:#8a99ad;
  font-size:14px;
  padding:20px;
  text-align:center;
}}
</style>
</head>

<body>
<div class="report">

  <section class="cover">
    <div class="cover-tag">361°儿童 · 周度经营洞察</div>
    <div class="cover-title">运动品牌行业周报</div>
    <div class="cover-sub">宏观消费 × 平台流量 × 渠道变化 × 品牌动作 × 商品机会</div>
    <div class="cover-footer">ONE DEGREE BEYOND｜经营管理部｜生成时间 {generated_time}</div>
    <div class="stats">
      <div class="stat"><div class="stat-num">{len(days)}</div><div class="stat-label">统计天数</div></div>
      <div class="stat"><div class="stat-num">{len(news_titles)}</div><div class="stat-label">资讯样本</div></div>
      <div class="stat"><div class="stat-num">{len(product_cards)}</div><div class="stat-label">商品观察</div></div>
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <div class="section-title">一、本周核心判断</div>
      <div class="section-kicker">WEEKLY JUDGEMENT</div>
    </div>
    <div class="summary-box">{weekly_summary}</div>
  </section>

  <section class="page">
    <div class="section-head">
      <div class="section-title">二、本周趋势总览</div>
      <div class="section-kicker">TREND OVERVIEW</div>
    </div>
    <div class="grid-3">
      <div class="card">
        <div class="card-title">机会方向</div>
        <ul>{render_list(opportunities, 4)}</ul>
      </div>
      <div class="card">
        <div class="card-title">风险提示</div>
        <ul>{render_list(risks, 4)}</ul>
      </div>
      <div class="card">
        <div class="card-title">经营动作</div>
        <ul>{render_list(actions, 4)}</ul>
      </div>
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <div class="section-title">三、本周重点资讯与热词</div>
      <div class="section-kicker">NEWS & KEYWORDS</div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title">本周 TOP 资讯</div>
        {render_news()}
      </div>
      <div>
        <div class="word-cloud">{render_keywords()}</div>
      </div>
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <div class="section-title">四、区域机会与渠道观察</div>
      <div class="section-kicker">REGIONAL INSIGHT</div>
    </div>
    <div class="grid-3">
      {render_regions()}
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <div class="section-title">五、热卖运动品牌鞋服商品观察</div>
      <div class="section-kicker">HOT PRODUCTS</div>
    </div>
    <div class="products">
      {render_product_cards()}
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <div class="section-title">六、下季度商品开发建议</div>
      <div class="section-kicker">PRODUCT PLANNING</div>
    </div>
    <div class="suggest-grid">
      {render_product_suggestion_cards()}
    </div>
  </section>

  <div class="footer">
    数据来源：TrendRadar 日报历史库 / 周报库 / 商品趋势库 ｜ 制作：运动品牌行业周报自动化系统
  </div>

</div>
</body>
</html>
"""

OUTPUT_HTML.write_text(html, encoding="utf-8")
print(f"weekly html generated: {OUTPUT_HTML}")
