from pathlib import Path
from datetime import datetime
import json
import re
from collections import Counter

# =========================================================
# 文件路径
# =========================================================
WEEKLY_FILE = Path("output/weekly/latest_week.json")
ANALYSIS_FILE = Path("output/weekly/weekly_analysis.json")
PRODUCT_FILE = Path("output/products/latest_products.json")

OUTPUT_DIR = Path("output/weekly")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_HTML = OUTPUT_DIR / "weekly_report.html"

# =========================================================
# 工具函数
# =========================================================
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

def short(text, n=38):
    text = clean(text)
    return text if len(text) <= n else text[:n] + "..."

def get_list(data, key):
    value = data.get(key, [])
    return value if isinstance(value, list) else []

# =========================================================
# 读取数据
# =========================================================
weekly = load_json(WEEKLY_FILE, {})
analysis = load_json(ANALYSIS_FILE, {})
products_data = load_json(PRODUCT_FILE, {})

generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")

days = get_list(weekly, "days")
top_news = get_list(weekly, "top_news")
keywords = get_list(weekly, "keywords")
regions = get_list(weekly, "regions")

# =========================================================
# 资讯统计
# =========================================================
news_titles = []

for item in top_news:
    if isinstance(item, dict):
        title = item.get("title", "")
        if title:
            news_titles.append(clean(title))
    elif isinstance(item, str):
        news_titles.append(clean(item))

news_counter = Counter(news_titles)
top_news_list = news_counter.most_common(10)

# =========================================================
# 热词统计
# =========================================================
keyword_values = []

for item in keywords:
    if isinstance(item, dict):
        for k in ["word", "keyword", "name", "title"]:
            if item.get(k):
                keyword_values.append(clean(item.get(k)))
                break
    elif isinstance(item, str):
        keyword_values.append(clean(item))

keyword_counter = Counter(keyword_values)
top_keywords = keyword_counter.most_common(20)

# =========================================================
# 区域统计
# =========================================================
region_values = []

for item in regions:
    if isinstance(item, dict):
        name = item.get("region") or item.get("name") or item.get("area")
        if name:
            region_values.append(clean(name))
    elif isinstance(item, str):
        region_values.append(clean(item))

region_counter = Counter(region_values)
top_regions = region_counter.most_common(8)

# =========================================================
# 周报分析
# =========================================================
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
        or "本周行业热点围绕运动消费、天气品类、平台流量、儿童运动和轻户外场景展开，后续需关注品类节奏、区域客流和爆款商品趋势。"
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

# =========================================================
# 商品趋势
# =========================================================
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
                "reason": p.get("reason", "")
            })

product_cards = sorted(product_cards, key=lambda x: int(x.get("heat") or 0), reverse=True)[:12]

# =========================================================
# HTML组件
# =========================================================
def render_news():
    if not top_news_list:
        return "<div class='empty'>暂无本周重点资讯数据</div>"

    html = ""
    for i, (title, count) in enumerate(top_news_list, start=1):
        html += f"""
        <div class="news-row">
          <div class="rank">{i}</div>
          <div class="news-main">
            <div class="news-title">{short(title, 46)}</div>
            <div class="news-meta">本周出现 {count} 次</div>
          </div>
        </div>
        """
    return html

def render_keywords():
    if not top_keywords:
        fallback = ["防晒", "凉感", "速干", "轻户外", "儿童运动", "青少年", "情绪消费", "城市骑行", "AI电商", "会员复购"]
        data = [(x, 1) for x in fallback]
    else:
        data = top_keywords

    html = ""
    for i, (word, count) in enumerate(data[:20], start=1):
        size = 18 if i <= 3 else 15 if i <= 8 else 13
        html += f"<span class='word w{i}' style='font-size:{size}px'>{word}</span>"
    return html

def render_regions():
    if not top_regions:
        return """
        <div class="region-card">华东｜关注商圈活动、亲子运动与夏季功能品类</div>
        <div class="region-card">华南｜关注降雨天气、防滑防雨与室内运动承接</div>
        <div class="region-card">西南｜关注文旅出行、轻户外和直播承接</div>
        <div class="region-card">西北｜关注防晒、户外和价格带机会</div>
        """

    html = ""
    for name, count in top_regions:
        html += f"<div class='region-card'><b>{name}</b><span>本周出现 {count} 次，建议跟踪区域客流、天气品类和主推商品。</span></div>"
    return html

def render_product_cards():
    if not product_cards:
        return "<div class='empty'>暂无商品趋势数据</div>"

    html = ""
    for p in product_cards:
        tags = p.get("tags", [])
        tag_text = " / ".join(tags[:3]) if isinstance(tags, list) else ""
        html += f"""
        <div class="product-card">
          <div class="product-brand">{p.get("brand", "")}</div>
          <div class="product-name">{short(p.get("name", ""), 28)}</div>
          <div class="product-meta">
            <span>{p.get("category", "")}</span>
            <span>¥{p.get("price", "")}</span>
            <span>热度 {p.get("heat", "")}</span>
          </div>
          <div class="product-tags">{tag_text}</div>
        </div>
        """
    return html

def render_list(items):
    html = ""
    for item in items[:6]:
        if isinstance(item, dict):
            theme = item.get("theme", "")
            heat = item.get("heat", "")
            suggestion = item.get("suggestion", "")

            text_parts = []
            if theme:
                text_parts.append(f"【{theme}】")
            if heat != "":
                text_parts.append(f"热度{heat}。")
            if suggestion:
                text_parts.append(suggestion)

            text = "".join(text_parts) or clean(item)
        else:
            text = clean(item)

        html += f"<li>{text}</li>"
    return html

# =========================================================
# 输出HTML
# =========================================================
html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>运动品牌行业周报</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:#edf3fb;
  font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;
  color:#102a5c;
  padding:20px;
}}
.page{{
  width:1280px;
  margin:auto;
  background:#fff;
  border-radius:22px;
  padding:24px;
  box-shadow:0 18px 40px rgba(20,50,100,.14);
}}
.header{{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  border-bottom:1px solid #dbe6f6;
  padding-bottom:18px;
  margin-bottom:18px;
}}
.title{{
  font-size:48px;
  font-weight:950;
  color:#06276a;
  letter-spacing:-1px;
}}
.subtitle{{
  margin-top:8px;
  font-size:18px;
  color:#31527f;
  font-weight:800;
}}
.stats{{
  display:grid;
  grid-template-columns:repeat(3,120px);
  gap:10px;
}}
.stat{{
  background:#f3f8ff;
  border:1px solid #dbe6f6;
  border-radius:14px;
  padding:14px;
  text-align:center;
}}
.stat-num{{
  font-size:30px;
  color:#0b63d8;
  font-weight:950;
}}
.stat-label{{
  font-size:12px;
  color:#526b95;
  margin-top:5px;
}}
.grid{{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px;
}}
.section{{
  background:#fff;
  border:1px solid #dbe6f6;
  border-radius:16px;
  overflow:hidden;
  margin-bottom:16px;
}}
.section-title{{
  background:linear-gradient(90deg,#062b78,#0968df);
  color:#fff;
  font-size:18px;
  font-weight:950;
  padding:10px 14px;
}}
.section-body{{
  padding:14px;
}}
.summary{{
  font-size:18px;
  line-height:1.7;
  font-weight:800;
  background:#f3f8ff;
  border:1px solid #dbe6f6;
  border-radius:16px;
  padding:18px;
  margin-bottom:16px;
}}
.news-row{{
  display:grid;
  grid-template-columns:34px 1fr;
  gap:12px;
  align-items:center;
  padding:9px 0;
  border-bottom:1px solid #edf2fa;
}}
.news-row:last-child{{border-bottom:none}}
.rank{{
  width:30px;
  height:30px;
  border-radius:9px;
  background:#0b63d8;
  color:#fff;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:950;
}}
.news-title{{
  font-size:15px;
  font-weight:900;
  color:#0d2d68;
}}
.news-meta{{
  font-size:12px;
  color:#6b7f9f;
  margin-top:3px;
}}
.word-cloud{{
  min-height:230px;
  padding:20px;
  display:flex;
  flex-wrap:wrap;
  align-content:center;
  gap:14px 18px;
  background:#f8fbff;
  border-radius:14px;
}}
.word{{
  font-weight:950;
  color:#0b63d8;
  background:#eef6ff;
  border-radius:999px;
  padding:6px 12px;
}}
.w1,.w2,.w3{{color:#063b88;background:#dcecff}}
.w4,.w5,.w6{{color:#0f766e;background:#e7f8f2}}
.w7,.w8,.w9{{color:#c2410c;background:#fff3e8}}
.region-card{{
  padding:12px;
  border-radius:12px;
  background:#f7fbff;
  border:1px solid #dbe6f6;
  margin-bottom:10px;
  line-height:1.5;
}}
.region-card b{{
  color:#0b4db3;
  margin-right:10px;
}}
.region-card span{{
  color:#355174;
  font-weight:700;
}}
ul{{
  padding-left:20px;
}}
li{{
  margin-bottom:9px;
  font-size:15px;
  line-height:1.55;
  font-weight:750;
}}
.products{{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:12px;
}}
.product-card{{
  border:1px solid #dbe6f6;
  border-radius:14px;
  background:#f9fcff;
  padding:12px;
  min-height:132px;
}}
.product-brand{{
  font-size:13px;
  color:#0b63d8;
  font-weight:950;
}}
.product-name{{
  font-size:15px;
  line-height:1.35;
  font-weight:950;
  color:#0d2d68;
  margin-top:6px;
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
  font-weight:800;
}}
.footer{{
  margin-top:18px;
  padding-top:12px;
  border-top:1px solid #dbe6f6;
  display:flex;
  justify-content:space-between;
  color:#6b7f9f;
  font-size:12px;
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
<div class="page">

  <div class="header">
    <div>
      <div class="title">运动品牌行业周报</div>
      <div class="subtitle">趋势复盘 · 商品机会 · 区域洞察 · 下季开发建议</div>
    </div>
    <div class="stats">
      <div class="stat"><div class="stat-num">{len(days)}</div><div class="stat-label">统计天数</div></div>
      <div class="stat"><div class="stat-num">{len(news_titles)}</div><div class="stat-label">资讯样本</div></div>
      <div class="stat"><div class="stat-num">{len(product_cards)}</div><div class="stat-label">商品观察</div></div>
    </div>
  </div>

  <div class="summary">
    {weekly_summary}
  </div>

  <div class="grid">
    <div class="section">
      <div class="section-title">一、本周TOP资讯</div>
      <div class="section-body">
        {render_news()}
      </div>
    </div>

    <div class="section">
      <div class="section-title">二、本周热词雷达</div>
      <div class="section-body">
        <div class="word-cloud">
          {render_keywords()}
        </div>
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="section">
      <div class="section-title">三、本周区域机会</div>
      <div class="section-body">
        {render_regions()}
      </div>
    </div>

    <div class="section">
      <div class="section-title">四、本周机会与风险</div>
      <div class="section-body">
        <b>机会：</b>
        <ul>{render_list(opportunities)}</ul>
        <br>
        <b>风险：</b>
        <ul>{render_list(risks)}</ul>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">五、热卖运动品牌鞋服商品观察</div>
    <div class="section-body">
      <div class="products">
        {render_product_cards()}
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="section">
      <div class="section-title">六、经营动作建议</div>
      <div class="section-body">
        <ul>{render_list(actions)}</ul>
      </div>
    </div>

    <div class="section">
      <div class="section-title">七、下季度开发建议</div>
      <div class="section-body">
        <ul>{render_list(product_suggestions)}</ul>
      </div>
    </div>
  </div>

  <div class="footer">
    <div>数据来源：TrendRadar 日报历史库 / 周报库 / 商品趋势库</div>
    <div>生成时间：{generated_time}</div>
    <div>制作：运动品牌行业周报自动化系统</div>
  </div>

</div>
</body>
</html>
"""

OUTPUT_HTML.write_text(html, encoding="utf-8")

print(f"weekly html generated: {OUTPUT_HTML}")
