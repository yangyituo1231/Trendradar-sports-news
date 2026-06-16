from pathlib import Path
from datetime import datetime
from collections import Counter
import json
import re
import html

# =========================================================
# 文件路径
# =========================================================
WEEKLY_DIR = Path("output/weekly")
PRODUCT_DIR = Path("output/products")

WEEKLY_NEWS_FILE = WEEKLY_DIR / "weekly_news.json"
PRODUCT_SIGNAL_FILE = PRODUCT_DIR / "latest_product_signals.json"
OUTPUT_HTML = WEEKLY_DIR / "weekly_report.html"

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# 基础工具
# =========================================================
def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load json error: {path} {repr(e)}")
    return default


def safe_list(v):
    return v if isinstance(v, list) else []


def esc(v):
    return html.escape(str(v or "").replace("\n", " ").strip())


def raw(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ").strip())


def short(v, n=46):
    t = raw(v)
    return esc(t if len(t) <= n else t[:n] + "...")


def has_any(text, words):
    return any(w in text for w in words)


# =========================================================
# 读取数据
# =========================================================
weekly = load_json(WEEKLY_NEWS_FILE, {})
product_signals = load_json(PRODUCT_SIGNAL_FILE, {})

generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")

levels = weekly.get("levels", {}) if isinstance(weekly.get("levels"), dict) else {}
a_items = safe_list(levels.get("A", {}).get("items"))
b_items = safe_list(levels.get("B", {}).get("items"))
c_items = safe_list(levels.get("C", {}).get("items"))
all_items = safe_list(weekly.get("items"))

weekly_summary = weekly.get("summary", {}) if isinstance(weekly.get("summary"), dict) else {}
campaign = weekly.get("campaign", "日常经营")

# 优先使用商品信号自己的 recent_days
recent_days = product_signals.get("recent_days") or weekly.get("recent_days") or 8
product_items = safe_list(product_signals.get("signals"))
product_signal_count = product_signals.get("signal_count") or len(product_items)

# =========================================================
# 词库与规则
# =========================================================
BRAND_WORDS = [
    "Nike", "耐克", "Adidas", "阿迪达斯", "Puma", "彪马",
    "安踏", "安踏儿童", "FILA", "FILA KIDS", "FILA Kids",
    "李宁", "李宁YOUNG", "特步", "特步儿童",
    "361", "361度", "361°", "361儿童",
    "巴拉巴拉", "On", "昂跑", "HOKA", "Hoka",
    "亚瑟士", "ASICS", "Asics", "Saucony", "索康尼",
    "Salomon", "萨洛蒙", "lululemon",
    "始祖鸟", "Arc'teryx", "北面", "The North Face",
    "迪桑特", "Descente", "凯乐石", "KAILAS",
    "伯希和", "PELLIOT", "蕉下", "Beneunder",
    "New Balance", "Skechers", "Crocs", "Vans", "Converse",
    "泰兰尼斯", "moodytiger", "modytiger", "GMT",
]

CATEGORY_RULES = {
    "平台大促": ["618", "大促", "预售", "战报", "直播", "抖音", "天猫", "京东", "唯品"],
    "防晒凉感": ["防晒", "防晒衣", "防晒服", "凉感", "速干", "清凉", "冰感"],
    "儿童运动": ["儿童", "童装", "童鞋", "青少年", "亲子", "校园", "足弓"],
    "跑步科技": ["跑鞋", "跑步", "缓震", "碳板", "竞速", "厚底", "回弹"],
    "篮球足球": ["篮球", "足球", "篮球鞋", "足球鞋", "库里", "Curry"],
    "户外轻运动": ["户外", "露营", "骑行", "徒步", "冲锋衣", "户外鞋", "轻户外", "溯溪"],
    "运动恢复": ["恢复拖鞋", "拖鞋", "运动凉鞋", "洞洞鞋", "凉鞋"],
    "品牌新品": ["新品", "上新", "发布", "首发", "上市", "联名", "推出", "登场"],
    "AI营销": ["AI", "人工智能", "大模型", "智能", "算法"],
    "商圈渠道": ["商场", "商圈", "门店", "奥莱", "客流", "旗舰店"],
}

BAD_PRODUCT_WORDS = [
    "AI", "人工智能", "白皮书", "报告", "ESG", "可持续", "财报", "营收", "净利润",
    "市值", "股票", "股价", "融资", "财经", "消费洞察", "市场规模", "指南",
    "测评", "实测", "推荐", "排行榜", "怎么买", "哪款好",
    "直降", "红包", "最低", "入手", "优惠", "特价", "券后", "凑单",
    "世界杯观察", "比分", "赛程", "转会", "主教练", "球员",
]

# =========================================================
# 推断函数
# =========================================================
def source_name(item):
    return raw(item.get("source") or "公开资讯")


def infer_brand(title):
    for b in BRAND_WORDS:
        if b in title:
            if b == "耐克":
                return "Nike"
            if b == "阿迪达斯":
                return "Adidas"
            if b in ["昂跑", "On"]:
                return "On昂跑"
            if b in ["亚瑟士", "ASICS"]:
                return "Asics"
            if b == "索康尼":
                return "Saucony"
            return b
    return "行业"


def infer_category(title):
    for name, words in CATEGORY_RULES.items():
        if has_any(title, words):
            return name
    return "行业动态"


def infer_impact(title):
    if has_any(title, ["618", "大促", "直播", "抖音", "天猫", "京东"]):
        return "平台流量与价格心智仍在强化，需关注线上热词向线下陈列和会员触达外溢。"
    if has_any(title, ["防晒", "凉感", "速干", "清凉"]):
        return "夏季功能品类进入主推窗口，防晒、凉感、速干组合仍是确定性机会。"
    if has_any(title, ["儿童", "童装", "童鞋", "青少年", "亲子", "足弓"]):
        return "儿童运动消费持续被细分场景驱动，专业功能和亲子体验是核心抓手。"
    if has_any(title, ["跑鞋", "缓震", "碳板", "厚底", "回弹"]):
        return "跑鞋科技与专业功能表达升温，可迁移到青少年成人化产品卖点。"
    if has_any(title, ["篮球", "足球", "库里"]):
        return "专业运动心智升温，赛事、明星资产和训练装备值得持续跟踪。"
    if has_any(title, ["户外", "露营", "骑行", "文旅", "出行", "冲锋衣"]):
        return "户外生活方式继续扩散，可联动轻户外、防晒、防雨和亲子出行产品。"
    return "品牌声量、品类认知和终端转化均需持续跟踪。"


# =========================================================
# 数据构建
# =========================================================
def build_core_points():
    text = " ".join([raw(x.get("title")) for x in a_items + b_items + c_items])
    points = []

    if has_any(text, ["618", "大促", "抖音", "天猫", "京东"]):
        points.append("618与平台内容仍是本周最强经营变量，运动户外、防晒凉感和品牌尖货是主要增量线索。")
    if has_any(text, ["防晒", "凉感", "速干", "清凉"]):
        points.append("夏季功能品类继续升温，防晒衣、凉感T、速干短裤等卖点需要前置表达。")
    if has_any(text, ["儿童", "童装", "童鞋", "青少年", "亲子"]):
        points.append("儿童运动消费从单一服饰购买转向场景化需求，亲子、校园、户外和专业训练共同驱动。")
    if has_any(text, ["Nike", "耐克", "安踏", "李宁", "Adidas", "lululemon", "FILA", "亚瑟士", "On"]):
        points.append("竞品动作集中在品牌资产、专业科技和本土化表达，头部品牌正在争夺更高价值心智。")
    if has_any(text, ["AI", "人工智能", "大模型"]):
        points.append("AI营销、内容种草与平台效率成为新变量，品牌投放从流量竞争转向内容效率竞争。")

    if not points:
        points = ["本周行业信息围绕品牌动作、商品功能、平台流量和区域机会展开，需持续观察新闻事实变化。"]

    return points[:5]


def build_summary_text():
    return " ".join(build_core_points()[:3])


def build_brand_heat():
    c = Counter()
    for x in a_items + b_items + c_items:
        title = raw(x.get("title"))
        b = infer_brand(title)
        if b != "行业":
            c[b] += int(x.get("level_score") or 1)

    for x in product_items:
        for b in safe_list(x.get("brand_hits")):
            c[raw(b)] += int(x.get("heat") or 1)

    return c.most_common(8)


def build_category_heat():
    c = Counter()
    for x in a_items + b_items + c_items:
        title = raw(x.get("title"))
        c[infer_category(title)] += int(x.get("level_score") or 1)

    for x in product_items:
        cat = raw(x.get("category")) or infer_category(raw(x.get("title")))
        c[cat] += int(x.get("heat") or 1)

    return c.most_common(8)


def build_keywords():
    c = Counter()
    for w in safe_list(weekly.get("keywords")):
        if raw(w):
            c[raw(w)] += 5

    for row in safe_list(product_signals.get("top_keywords")):
        if isinstance(row, list) and len(row) >= 2:
            c[raw(row[0])] += int(row[1] or 1)

    pool = [
        "618", "防晒衣", "凉感", "速干", "运动户外", "儿童运动",
        "亲子消费", "平台大促", "品牌竞争", "商场客流",
        "新品发布", "联名合作", "户外生活", "暑期消费",
        "抖音电商", "奥莱折扣", "运动童装", "跑鞋", "篮球专业",
        "足弓健康", "防雨防滑", "碳板跑鞋", "轻户外",
    ]

    text = " ".join([raw(x.get("title")) for x in all_items[:120] + product_items[:80]])
    for w in pool:
        if w in text:
            c[w] += text.count(w) + 1

    return c.most_common(24)


def is_good_product_card(item):
    title = raw(item.get("title"))
    if not title:
        return False
    if has_any(title, BAD_PRODUCT_WORDS):
        return False
    if raw(item.get("category")) in ["AI营销", "行业动态"]:
        return False
    return True


def build_product_cards():
    cards = []
    for x in product_items:
        if not is_good_product_card(x):
            continue

        title = raw(x.get("title"))
        category = raw(x.get("category")) or infer_category(title)
        brands = safe_list(x.get("brand_hits"))
        brand = "、".join([raw(b) for b in brands]) if brands else infer_brand(title)
        score = x.get("heat") or ""

        icon = "👟"
        if has_any(title, ["防晒", "凉感", "速干", "清凉"]):
            icon = "☀️"
        elif has_any(title, ["篮球", "足球", "库里"]):
            icon = "🏀"
        elif has_any(title, ["户外", "露营", "徒步", "冲锋", "溯溪"]):
            icon = "⛰️"
        elif has_any(title, ["拖鞋", "凉鞋", "恢复"]):
            icon = "🩴"
        elif has_any(title, ["儿童", "童鞋", "青少年", "足弓"]):
            icon = "🧒"

        cards.append({
            "title": title,
            "brand": brand,
            "category": category,
            "score": score,
            "source": source_name(x),
            "icon": icon,
            "insight": infer_impact(title),
        })

    return cards[:9]


def build_361_actions():
    text = " ".join([raw(x.get("title")) for x in a_items + b_items + c_items + product_items])
    actions = []

    if has_any(text, ["防晒", "凉感", "速干", "清凉"]):
        actions.append("商品：继续强化防晒衣、凉感T、速干短裤、防晒帽包组合，突出夏季功能闭环。")
    if has_any(text, ["儿童", "童鞋", "足弓", "青少年", "亲子"]):
        actions.append("商品：围绕儿童足弓健康、校园运动、亲子户外建立更清晰的专业卖点表达。")
    if has_any(text, ["篮球", "足球", "跑鞋", "缓震", "碳板"]):
        actions.append("品类：关注青少年篮球鞋、足球鞋、跑鞋缓震科技和训练装备，提升专业运动心智。")
    if has_any(text, ["618", "大促", "直播", "抖音", "天猫", "京东"]):
        actions.append("渠道：618后关注价格带修复与爆款延续，线上热词同步给线下陈列和会员触达。")
    if has_any(text, ["户外", "露营", "文旅", "骑行", "出行", "冲锋衣"]):
        actions.append("场景：围绕暑期亲子出行、轻户外、防雨防滑建立区域化主题陈列。")
    if has_any(text, ["新品", "联名", "发布", "上市"]):
        actions.append("营销：借鉴成人运动与户外品牌新品表达方式，强化青少年产品成人化设计和科技感。")

    if not actions:
        actions = [
            "商品：聚焦当季核心品类，强化功能卖点和场景表达。",
            "渠道：把线上热点同步到线下陈列、会员触达和导购话术。",
            "营销：结合品牌案例优化内容种草和新品表达。",
        ]

    return actions[:6]


# =========================================================
# HTML渲染
# =========================================================
def render_core_cards():
    icons = ["①", "②", "③", "④", "⑤"]
    return "".join(
        f"<div class='core-card'><b>{icons[i]}</b><span>{esc(p)}</span></div>"
        for i, p in enumerate(build_core_points())
    )


def render_level_section(title, items, label):
    if not items:
        return "<div class='empty'>暂无数据</div>"

    rows = ""
    for i, x in enumerate(items[:8], start=1):
        t = raw(x.get("title"))
        rows += f"""
        <tr>
          <td><span class='rank'>{i}</span></td>
          <td class='event-title'>{short(t, 48)}<em>{esc(source_name(x))}</em></td>
          <td>{esc(infer_brand(t))}</td>
          <td>{esc(infer_category(t))}</td>
          <td>{esc(infer_impact(t))}</td>
        </tr>
        """
    return f"""
    <div class='sub-title'>{esc(title)} <span>{esc(label)}</span></div>
    <table class='event-table'>
      <thead><tr><th>#</th><th>事件</th><th>品牌</th><th>类型</th><th>经营判断</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def render_bars(data, green=False):
    if not data:
        return "<div class='empty'>暂无数据</div>"
    max_v = max(v for _, v in data) or 1
    cls = "bar green" if green else "bar"
    html_text = ""
    for i, (name, v) in enumerate(data, start=1):
        w = max(8, int(v / max_v * 100))
        html_text += f"<div class='bar-row'><label>{i}. {esc(name)}</label><div class='{cls}'><i style='width:{w}%'></i></div><b>{v}</b></div>"
    return html_text


def render_keyword_cloud():
    data = build_keywords()
    if not data:
        return "<div class='empty'>暂无热词</div>"
    html_text = ""
    for i, (w, _) in enumerate(data, start=1):
        cls = "kw big" if i <= 4 else "kw mid" if i <= 10 else "kw"
        html_text += f"<span class='{cls}'>{esc(w)}</span>"
    return html_text


def render_product_cards():
    cards = build_product_cards()
    if not cards:
        return "<div class='empty'>暂无商品尖货信号</div>"

    html_text = ""
    for i, p in enumerate(cards, start=1):
        html_text += f"""
        <div class='product-card'>
          <div class='product-cover'>
            <span>TOP {i}</span>
            <i>{p.get('icon')}</i>
            <strong>{esc(p.get('category'))}</strong>
            <em>热度 {esc(p.get('score'))}</em>
          </div>
          <h4>{short(p.get('title'), 42)}</h4>
          <p class='brand'>{esc(p.get('brand'))}｜{esc(p.get('source'))}</p>
          <p class='insight'>{esc(p.get('insight'))}</p>
        </div>
        """
    return html_text


def render_361_actions():
    return "".join(f"<div class='plan-card'>{esc(x)}</div>" for x in build_361_actions())


date_range = f"最近{recent_days}天"
total_count = weekly_summary.get("total") or len(all_items)
a_count = weekly_summary.get("a_count") or len(a_items)
b_count = weekly_summary.get("b_count") or len(b_items)
hot_count = product_signal_count

# =========================================================
# 输出HTML
# =========================================================
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
.stat b{{font-size:31px;display:block}}.stat span{{font-size:12px;font-weight:800;opacity:.9}}
.page{{background:#fff;border-radius:26px;padding:24px;box-shadow:0 16px 36px rgba(25,56,105,.12);margin-bottom:18px}}
.head{{display:flex;align-items:end;justify-content:space-between;border-bottom:2px solid #e3edf9;padding-bottom:12px;margin-bottom:18px}}
.head h2{{font-size:27px;color:#062b78;font-weight:950}}.head span{{font-size:12px;color:#0b63d8;font-weight:950;letter-spacing:.8px}}
.summary{{font-size:20px;line-height:1.75;font-weight:850;color:#0d2d68;background:linear-gradient(135deg,#f6f9ff,#eef6ff);border:1px solid #dce8f8;border-radius:20px;padding:20px}}
.core-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:16px}}
.core-card{{background:#fbfdff;border:1px solid #dbe6f6;border-radius:18px;padding:16px;min-height:135px}}
.core-card b{{display:block;color:#ff7a00;font-size:24px;margin-bottom:8px}}.core-card span{{font-size:15px;line-height:1.55;font-weight:850;color:#244268}}
.sub-title{{font-size:20px;color:#062b78;font-weight:950;margin:18px 0 12px}}.sub-title span{{font-size:12px;color:#0b63d8;margin-left:8px}}
.event-table{{width:100%;border-collapse:collapse;margin-bottom:12px}}.event-table th{{text-align:left;background:#f3f8ff;color:#0b4db3;font-size:13px;padding:12px;border-bottom:1px solid #dbe6f6}}.event-table td{{font-size:14px;line-height:1.45;font-weight:760;color:#233e68;padding:12px;border-bottom:1px solid #edf2fa;vertical-align:top}}
.rank{{display:inline-flex;width:28px;height:28px;align-items:center;justify-content:center;background:#0b63d8;color:#fff;border-radius:9px;font-weight:950}}.event-title{{font-weight:950;color:#0d2d68}}.event-title em{{display:block;font-size:11px;color:#7b8ca8;font-style:normal;margin-top:4px}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.panel{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:18px}}.panel h3{{font-size:18px;color:#0b4db3;margin-bottom:14px}}
.bar-row{{display:grid;grid-template-columns:118px 1fr 42px;gap:10px;align-items:center;margin-bottom:12px}}.bar-row label{{font-size:13px;font-weight:900;color:#183a76;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.bar-row b{{font-size:13px;color:#0b63d8;text-align:right}}.bar{{height:10px;background:#edf5ff;border-radius:999px;overflow:hidden}}.bar i{{display:block;height:100%;background:linear-gradient(90deg,#0b63d8,#18a2ff);border-radius:999px}}.bar.green i{{background:linear-gradient(90deg,#0f766e,#34d399)}}
.word-cloud{{min-height:240px;border:1px solid #dbe6f6;border-radius:20px;background:linear-gradient(135deg,#f8fbff,#eef6ff);display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:14px 18px;padding:22px}}.kw{{background:#fff;border:1px solid #dbe6f6;border-radius:999px;padding:7px 14px;font-size:14px;font-weight:950;color:#0b63d8;box-shadow:0 6px 14px rgba(20,60,110,.06)}}.kw.mid{{font-size:17px;background:#ecfdf5;color:#0f766e}}.kw.big{{font-size:25px;background:#dcecff;color:#062b78}}
.products{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.product-card{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:15px;box-shadow:0 8px 18px rgba(20,60,110,.06)}}.product-cover{{height:145px;border-radius:16px;background:radial-gradient(circle at 80% 20%,rgba(25,163,255,.22),transparent 30%),linear-gradient(135deg,#edf5ff,#f8fbff);display:flex;align-items:center;justify-content:center;flex-direction:column;position:relative;margin-bottom:11px}}.product-cover span{{position:absolute;top:8px;left:8px;background:#062b78;color:#fff;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:950}}.product-cover i{{font-style:normal;font-size:44px}}.product-cover strong{{font-size:21px;color:#0b4db3;margin-top:8px}}.product-cover em{{font-style:normal;color:#0f766e;background:#ecfdf5;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:900;margin-top:8px}}.product-card h4{{font-size:16px;line-height:1.38;color:#0d2d68;min-height:46px}}.brand{{font-size:12px;color:#0b63d8;font-weight:900;margin-top:7px}}.insight{{margin-top:9px;background:#f0fdf4;color:#166534;border-radius:12px;padding:9px;font-size:12.5px;line-height:1.45;font-weight:850}}
.plan-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.plan-card{{border-radius:18px;background:linear-gradient(135deg,#fff7ed,#fff);border:1px solid #fed7aa;color:#7c2d12;font-size:15px;line-height:1.6;font-weight:850;padding:17px;min-height:116px}}
.empty{{color:#8a99ad;font-size:14px;text-align:center;padding:24px}}.footer{{text-align:center;color:#7184a3;font-size:12px;margin:16px 0 4px}}
</style>
</head>
<body>
<div class='report'>
  <section class='cover'>
    <div class='cover-tag'>361°儿童 · 周度行业情报</div>
    <h1>运动品牌行业周报</h1>
    <h2>A级趋势 × B级品牌案例 × C级热点补充 × 商品尖货机会</h2>
    <div class='cover-foot'>统计周期：{esc(date_range)} ｜ 经营阶段：{esc(campaign)} ｜ 生成时间：{generated_time}</div>
    <div class='stats'>
      <div class='stat'><b>{total_count}</b><span>资讯样本</span></div>
      <div class='stat'><b>{a_count}</b><span>A级趋势</span></div>
      <div class='stat'><b>{b_count}</b><span>B级案例</span></div>
      <div class='stat'><b>{hot_count}</b><span>尖货信号</span></div>
    </div>
  </section>

  <section class='page'>
    <div class='head'><h2>P2｜本周核心结论</h2><span>WEEKLY JUDGEMENT</span></div>
    <div class='summary'>{esc(build_summary_text())}</div>
    <div class='core-grid'>{render_core_cards()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P3-P5｜本周行业事件分级</h2><span>A/B/C LEVEL NEWS</span></div>
    {render_level_section("A级｜核心经营趋势", a_items, "经营价值最高，建议必保留")}
    {render_level_section("B级｜品牌案例", b_items, "竞品动作与品牌案例")}
    {render_level_section("C级｜热点补充", c_items, "作为补充观察")}
  </section>

  <section class='page'>
    <div class='head'><h2>P6｜竞品热度与趋势地图</h2><span>BRAND / CATEGORY / KEYWORDS</span></div>
    <div class='grid-2'>
      <div class='panel'><h3>品牌热度排行</h3>{render_bars(build_brand_heat())}</div>
      <div class='panel'><h3>品类/场景热度排行</h3>{render_bars(build_category_heat(), green=True)}</div>
    </div>
    <div style='height:16px'></div>
    <div class='word-cloud'>{render_keyword_cloud()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P7｜每周运动品牌尖货 / 商品机会</h2><span>HOT PRODUCT SIGNALS</span></div>
    <div class='products'>{render_product_cards()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P8｜对361°儿童启示</h2><span>NEXT ACTION</span></div>
    <div class='plan-grid'>{render_361_actions()}</div>
  </section>

  <div class='footer'>数据来源：TrendRadar weekly_news.json / Google News RSS / latest_product_signals.json ｜ 内容随每周新闻事实自动变化</div>
</div>
</body>
</html>
"""

OUTPUT_HTML.write_text(html_text, encoding="utf-8")

print(f"weekly html generated: {OUTPUT_HTML}")
print(f"A: {len(a_items)} | B: {len(b_items)} | C: {len(c_items)} | product signals: {product_signal_count} | product cards: {len(build_product_cards())}")
