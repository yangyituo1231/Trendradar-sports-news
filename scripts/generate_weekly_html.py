from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import json
import re
import html

# =========================================================
# 文件路径
# =========================================================
HISTORY_DIR = Path("output/history")
WEEKLY_DIR = Path("output/weekly")
PRODUCT_DIR = Path("output/products")

ANALYSIS_FILE = WEEKLY_DIR / "weekly_analysis.json"
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


def short(v, n=42):
    t = raw(v)
    return esc(t if len(t) <= n else t[:n] + "...")


def norm_key(v):
    t = raw(v).lower()
    t = re.sub(r"[，。！？、；：:,.!?（）()【】\[\]《》“”\"'\s\-_/|]+", "", t)
    return t[:44]


def has_any(text, words):
    return any(w in text for w in words)


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

# =========================================================
# 读取数据
# =========================================================
analysis = load_json(ANALYSIS_FILE, {})
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
ai_judgement = parse_ai_json(analysis.get("ai_judgement") or summary.get("ai_judgement"))

# =========================================================
# 品牌 / 事件 / 过滤规则
# =========================================================
BRAND_ALIASES = {
    "安踏儿童": "安踏儿童", "安踏": "安踏", "FILA KIDS": "FILA KIDS", "FILA Kids": "FILA KIDS", "FILA": "FILA",
    "李宁YOUNG": "李宁YOUNG", "李宁": "李宁", "特步儿童": "特步儿童", "特步": "特步",
    "Nike Kids": "Nike Kids", "Nike": "Nike", "耐克": "Nike",
    "Adidas Kids": "Adidas Kids", "Adidas": "Adidas", "阿迪达斯": "Adidas", "阿迪": "Adidas",
    "Puma Kids": "Puma Kids", "Puma": "Puma", "彪马": "Puma",
    "361儿童": "361儿童", "361°儿童": "361儿童", "361度儿童": "361儿童", "361度": "361°", "361°": "361°", "361": "361°",
    "巴拉巴拉": "巴拉巴拉", "Balabala": "巴拉巴拉",
    "HOKA": "HOKA", "Hoka": "HOKA",
    "On Running": "On昂跑", "昂跑": "On昂跑",
    "亚瑟士": "Asics", "ASICS": "Asics", "Asics": "Asics",
    "Saucony": "Saucony", "索康尼": "Saucony",
    "Salomon": "Salomon", "萨洛蒙": "Salomon",
    "lululemon": "lululemon",
    "始祖鸟": "Arc'teryx", "Arc'teryx": "Arc'teryx",
    "北面": "The North Face", "The North Face": "The North Face",
    "迪桑特": "Descente", "Descente": "Descente",
    "凯乐石": "KAILAS", "KAILAS": "KAILAS",
    "伯希和": "PELLIOT", "PELLIOT": "PELLIOT",
    "蕉下": "蕉下", "Beneunder": "蕉下",
    "New Balance": "New Balance", "Skechers": "Skechers", "Crocs": "Crocs", "Vans": "Vans", "Converse": "Converse",
    "泰兰尼斯": "泰兰尼斯", "moodytiger": "moodytiger", "modytiger": "moodytiger", "GMT": "GMT",
}

EVENT_WORDS = [
    "签约", "代言", "联名", "战略合作", "合作", "新品", "新款", "发布", "推出", "上市", "首发", "亮相", "登场",
    "开店", "开业", "旗舰店", "快闪", "实验室", "创新中心", "研发", "科技", "换帅", "总裁", "CEO",
    "收购", "投资", "出圈", "爆火", "防晒", "凉感", "速干", "拖鞋", "篮球", "足球", "跑鞋", "户外",
    "618", "大促", "战报", "直播", "抖音", "天猫", "京东",
]

BAD_WORDS = [
    "涨停", "跌停", "龙虎榜", "股价", "市值", "证券", "A股", "港股", "美股", "财报", "年报", "净利润",
    "比分", "赛程", "转会", "主教练", "球员", "伤病", "世界杯版权",
    "电视", "手机", "汽车", "房产", "床垫", "博彩", "官网入口",
    "抽奖", "转发本条", "打call", "超话",
]

LOW_VALUE_WORDS = [
    "ESG报告", "可持续", "消费指南", "白皮书", "市场规模", "报告[", "榜单",
    "直降", "红包", "最低", "入手", "优惠", "特价", "券后", "凑单",
    "测评", "实测", "推荐", "排行榜", "怎么买", "哪款好",
]

A_LEVEL_WORDS = [
    "618", "大促", "战报", "京东", "天猫", "抖音", "直播",
    "运动户外", "防晒", "凉感", "速干", "户外", "露营", "骑行", "文旅", "亲子",
    "消费趋势", "品类", "客流", "奥莱", "商圈",
]

B_LEVEL_WORDS = [
    "安踏", "李宁", "Nike", "耐克", "Adidas", "阿迪", "FILA", "lululemon",
    "Asics", "亚瑟士", "Saucony", "On", "昂跑", "HOKA", "Salomon",
    "361", "巴拉巴拉", "泰兰尼斯", "签约", "代言", "联名", "新品", "发布", "推出", "上市", "实验室", "研发", "创新中心", "快闪",
]

C_LEVEL_WORDS = [
    "AI", "人工智能", "内容", "种草", "电商", "出海", "跨境",
    "天气", "雨", "高温", "水上", "漂流", "骑行", "露营", "文旅", "商场", "商圈", "门店", "奥莱",
]

# =========================================================
# 推断函数
# =========================================================
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
    if "足弓" in title:
        hits.insert(0, "足弓健康")
    if "拖鞋" in title or "恢复" in title:
        hits.insert(0, "运动恢复")
    if "防晒" in title or "凉感" in title or "速干" in title:
        hits.insert(0, "夏季功能")
    if "618" in title or "大促" in title:
        hits.insert(0, "平台大促")
    return "、".join(dict.fromkeys(hits[:3])) or "行业动态"


def infer_category(title):
    rules = {
        "平台大促": ["618", "大促", "战报", "直播", "抖音", "天猫", "京东"],
        "儿童运动": ["儿童", "童装", "童鞋", "青少年", "亲子", "校园", "足弓"],
        "防晒凉感": ["防晒", "凉感", "速干", "清凉", "冰感"],
        "跑步科技": ["跑鞋", "跑步", "缓震", "碳板", "竞速", "厚底", "回弹"],
        "篮球足球": ["篮球", "足球", "库里", "Curry"],
        "户外轻运动": ["户外", "露营", "骑行", "徒步", "冲锋衣", "户外鞋", "轻户外", "溯溪", "漂流"],
        "运动恢复": ["恢复拖鞋", "拖鞋", "运动凉鞋", "洞洞鞋", "凉鞋"],
        "品牌新品": ["新品", "上新", "发布", "首发", "上市", "联名", "推出", "登场", "快闪"],
        "AI营销": ["AI", "人工智能", "大模型", "算法", "内容种草"],
        "商圈渠道": ["商场", "商圈", "门店", "奥莱", "客流", "旗舰店"],
    }
    for name, words in rules.items():
        if has_any(title, words):
            return name
    return "行业动态"


def event_impact(title, brand, event):
    text = title + event
    if "库里" in text or "篮球" in text or "足球" in text:
        return "专业运动心智升温，明星资产、赛事场景和训练装备值得跟踪。"
    if "拖鞋" in text or "恢复" in text:
        return "运动恢复、舒适脚感和夏季出行品类关注提升。"
    if "创新中心" in text or "实验室" in text or "科技" in text or "足弓" in text:
        return "科技研发投入加速，产品专业背书和功能表达重要性提升。"
    if "防晒" in text or "凉感" in text or "速干" in text:
        return "夏季功能品类进入主推窗口，防晒凉感竞争加剧。"
    if "618" in text or "大促" in text or "直播" in text or "抖音" in text:
        return "平台流量和价格心智强化，线上热词可能外溢到线下。"
    if "开店" in text or "旗舰店" in text or "开业" in text or "奥莱" in text:
        return "渠道形象和核心商圈曝光提升，终端体验竞争增强。"
    if "AI" in text or "人工智能" in text:
        return "内容生产和投放效率变化，品牌营销从流量采买转向内容效率竞争。"
    if "户外" in text or "露营" in text or "骑行" in text or "漂流" in text:
        return "户外生活方式继续扩散，可联动轻户外、防晒、防雨和亲子出行产品。"
    return "品牌声量、品类认知和终端转化均需跟踪。"


def event_level(title, brand, source_key):
    score_a = sum(1 for w in A_LEVEL_WORDS if w in title)
    score_b = sum(1 for w in B_LEVEL_WORDS if w in title)
    score_c = sum(1 for w in C_LEVEL_WORDS if w in title)

    if source_key == "competitor_news":
        score_b += 2
    if brand != "行业":
        score_b += 1
    if has_any(title, ["618", "大促", "运动户外", "品类", "消费趋势"]):
        score_a += 2
    if has_any(title, ["AI", "人工智能", "天气", "文旅", "骑行", "漂流"]):
        score_c += 1

    if score_a >= score_b and score_a >= score_c and score_a > 0:
        return "A"
    if score_b >= score_a and score_b >= score_c and score_b > 0:
        return "B"
    return "C"


def keep_news_title(title):
    if not title or len(title) < 8:
        return False
    if has_any(title, BAD_WORDS):
        return False
    if has_any(title, LOW_VALUE_WORDS):
        if not has_any(title, ["新品", "发布", "联名", "实验室", "足弓", "库里", "运动户外", "618"]):
            return False
    return True


def collect_news_events():
    pool = []
    for day in history_days:
        date = day.get("date", "")
        for source_key in ["top_news", "competitor_news"]:
            for item in safe_list(day.get(source_key)):
                if not isinstance(item, dict):
                    continue
                title = raw(item.get("title"))
                if not keep_news_title(title):
                    continue
                brand = raw(item.get("brand")) or infer_brand(title)
                event = infer_event(title)
                level = event_level(title, brand, source_key)
                base = 1
                if source_key == "competitor_news":
                    base += 2
                if any(w in title for w in EVENT_WORDS):
                    base += 3
                if brand != "行业":
                    base += 2
                if level == "A":
                    base += 3
                elif level == "B":
                    base += 2
                pool.append({
                    "date": date,
                    "title": title,
                    "brand": brand,
                    "event": event,
                    "category": infer_category(title),
                    "level": level,
                    "source": raw(item.get("source")),
                    "impact": event_impact(title, brand, event),
                    "score": base + int(item.get("score") or 0) // 10,
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


def dedupe_pick(items, limit=5, min_limit=3, used_keys=None, max_per_brand=2):
    used_keys = used_keys or set()
    picked = []
    brand_counter = Counter()
    for x in items:
        key = norm_key(x.get("title"))
        if not key or key in used_keys:
            continue
        brand = x.get("brand") or "行业"
        if brand_counter[brand] >= max_per_brand and len(picked) >= min_limit:
            continue
        picked.append(x)
        used_keys.add(key)
        brand_counter[brand] += 1
        if len(picked) >= limit:
            break
    return picked, used_keys


def build_abc_sections():
    used = set()
    level_map = {
        "A": [x for x in news_events if x.get("level") == "A"],
        "B": [x for x in news_events if x.get("level") == "B"],
        "C": [x for x in news_events if x.get("level") == "C"],
    }
    a, used = dedupe_pick(level_map["A"], 5, 3, used, 2)
    b, used = dedupe_pick(level_map["B"], 5, 3, used, 2)
    c, used = dedupe_pick(level_map["C"], 5, 3, used, 2)

    for current in [a, b, c]:
        if len(current) >= 3:
            continue
        remain = [x for x in news_events if norm_key(x.get("title")) not in used]
        extra, used = dedupe_pick(remain, 3 - len(current), 0, used, 2)
        current.extend(extra)
    return a[:5], b[:5], c[:5]


a_events, b_events, c_events = build_abc_sections()

# =========================================================
# 热词 / 品牌 / 商品 / 区域
# =========================================================
def collect_keywords():
    c = Counter()
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
    for bad in ["行业", "发布", "推出", "上市", "系列"]:
        if bad in c and c[bad] <= 2:
            del c[bad]
    return c.most_common(28)


def collect_brand_heat():
    c = Counter()
    for x in news_events:
        if x["brand"] and x["brand"] != "行业":
            c[x["brand"]] += x.get("count", 1) + x.get("score", 0)
    for row in pair_rows(product_signals.get("top_brands", []), "brand"):
        name = count_row_name(row, ["brand", "name"])
        if name and name != "行业":
            c[name] += int(row.get("count") or 1)
    return c.most_common(10)


def collect_category_heat():
    c = Counter()
    for x in news_events:
        c[x.get("category") or infer_category(x.get("title", ""))] += x.get("score", 1)
    for row in pair_rows(product_signals.get("top_categories", []), "category"):
        name = count_row_name(row, ["category", "name"])
        if name:
            c[name] += int(row.get("count") or 1) * 8
    return [{"category": k, "count": v} for k, v in c.most_common(10)]


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
                        region_counter[name].append("；".join([raw(r.get(k)) for k in ["hot", "flow", "focus", "action"] if raw(r.get(k))]))
    for name, texts in region_counter.items():
        out.append({"name": name, "summary": "；".join(texts[:2]), "suggestion": "结合天气、商圈和主推品类做区域差异化承接。"})
    return out[:6]


def product_card_is_good(s):
    title = raw(s.get("title"))
    if not title:
        return False
    if has_any(title, ["直降", "红包", "最低", "入手", "优惠", "特价", "实测", "测评", "排行榜", "怎么买"]):
        return False
    if has_any(title, ["AI", "白皮书", "ESG", "财报", "市值", "股价"]):
        return False
    return True


def build_product_cards():
    signals = safe_list(product_signals.get("signals"))
    cards = []
    seen = set()
    for s in sorted([x for x in signals if isinstance(x, dict) and product_card_is_good(x)], key=lambda x: int(x.get("heat") or 0), reverse=True):
        title = raw(s.get("short_title") or s.get("title"))
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
        elif any(k in text for k in ["篮球", "足球", "库里"]):
            icon = "🏀"
        elif any(k in text for k in ["户外", "冲锋衣", "露营", "越野"]):
            icon = "⛰️"
        elif any(k in text for k in ["拖鞋", "凉鞋", "恢复"]):
            icon = "🩴"
        elif any(k in text for k in ["校园", "开学", "书包"]):
            icon = "🎒"
        insight = "关注商品卖点、竞品表达和终端陈列承接。"
        if "篮球" in text or "足球" in text or "库里" in text:
            insight = "专业运动心智升温，可跟踪青少年球鞋与训练装备。"
        if "防晒" in text or "凉感" in text:
            insight = "夏季功能品类升温，建议关注防晒凉感组合。"
        if "拖鞋" in text or "恢复" in text:
            insight = "运动恢复与舒适出行场景值得重点跟踪。"
        if "跑鞋" in text or "碳板" in text or "缓震" in text:
            insight = "跑鞋科技表达升温，可迁移到青少年成人化产品卖点。"
        cards.append({
            "title": title,
            "brand": "、".join([raw(b) for b in brands]) or infer_brand(title),
            "category": category,
            "heat": s.get("heat", ""),
            "tags": keys,
            "source": raw(s.get("source")),
            "icon": icon,
            "insight": insight,
            "link": raw(s.get("link", "")),
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

# =========================================================
# 周报判断
# =========================================================
def auto_core_points():
    points = []
    titles = " ".join([x["title"] for x in news_events])
    if "库里" in titles or "篮球" in titles or "足球" in titles:
        points.append("专业运动成为本周明确的品牌竞争线索，明星资产与青少年运动心智同步升温。")
    if "拖鞋" in titles or "恢复" in titles:
        points.append("运动恢复与舒适出行场景热度提升，夏季鞋类机会不只集中在跑鞋和凉鞋。")
    if "创新中心" in titles or "实验室" in titles or "足弓" in titles:
        points.append("品牌继续加码本土研发和专业科技表达，产品背书竞争进一步前置。")
    if any(k in titles for k in ["防晒", "凉感", "速干"]):
        points.append("防晒、凉感、速干仍是夏季最大确定性品类，需关注功能表达和组合销售。")
    if any(k in titles for k in ["618", "大促", "直播", "抖音"]):
        points.append("618与直播内容持续影响消费者价格心智，线上爆款与线下陈列需联动观察。")
    if not points:
        points = ["本周行业热点主要围绕品牌动作、商品功能、平台流量和区域客流展开，需持续跟踪新闻事实变化。"]
    return points[:5]


def summary_text():
    if summary.get("core_judgement"):
        return raw(summary.get("core_judgement"))
    return " ".join(auto_core_points()[:3])

# =========================================================
# HTML渲染
# =========================================================
def render_core_cards():
    html_text = ""
    icons = ["①", "②", "③", "④", "⑤"]
    for i, p in enumerate(auto_core_points()):
        html_text += f"<div class='core-card'><b>{icons[i]}</b><span>{esc(p)}</span></div>"
    return html_text


def render_level_table(title, items, subtitle):

    if not items:
        return f"""
        <div class='level-block'>
          <div class='level-title'>{esc(title)}<span>{esc(subtitle)}</span></div>
          <div class='empty'>暂无数据</div>
        </div>
        """

    rows = ""

    for i, x in enumerate(items[:5], start=1):

        link = raw(x.get("link", ""))
        title_html = short(x["title"], 42)

        if link:
            title_html = f"<a href='{esc(link)}' target='_blank'>{title_html}</a>"

        rows += f"""
        <tr>
          <td><span class='rank'>{i}</span></td>

          <td class='event-title'>
            {title_html}
            <em>{esc(x.get('source',''))}</em>
          </td>

          <td>{esc(x.get('brand'))}</td>
          <td>{esc(x.get('event'))}</td>
          <td>{esc(x.get('impact'))}</td>
        </tr>
        """

    return f"""
    <div class='level-block'>
      <div class='level-title'>{esc(title)}<span>{esc(subtitle)}</span></div>

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

        <tbody>
          {rows}
        </tbody>

      </table>
    </div>
    """


def render_abc_tables():
    return (
        render_level_table("A级｜核心经营趋势", a_events, "经营价值最高，建议必看")
        + render_level_table("B级｜品牌案例", b_events, "竞品动作与品牌案例")
        + render_level_table("C级｜热点补充", c_events, "作为补充观察")
    )


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
        
        title_html = short(p.get("title"), 36)
        link = raw(p.get("link", "")) 
        if link:
            title_html = f"<a href='{esc(link)}' target='_blank'>{title_html}</a>"

        html_text += f"""
        <div class='product-card'>
          <div class='product-cover'><span>TOP {i}</span><i>{p.get('icon')}</i><strong>{esc(p.get('category'))}</strong></div>
          <h4>{title_html}</h4>
          <p class='brand'>{esc(p.get('brand'))} | {esc(p.get('source'))}</p>
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
    blocks = [("核心判断", "core_judgement"), ("机会判断", "opportunity"), ("风险判断", "risk"), ("下周动作", "action")]
    inner = ""
    for title, key in blocks:
        if ai_judgement.get(key):
            inner += f"<div><b>{title}</b><p>{esc(ai_judgement.get(key))}</p></div>"
    return f"<div class='ai-box'><h3>AI经营判断</h3>{inner}</div>" if inner else ""


def render_planning():
    suggestions = analysis.get("product_suggestions") if isinstance(analysis.get("product_suggestions"), list) else []
    if not suggestions:
        suggestions = [
            "围绕篮球/足球专业化，跟踪青少年球鞋、训练服和校园运动装备。",
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


date_range = summary.get("date_range") or (f"{history_days[0].get('date')} 至 {history_days[-1].get('date')}" if history_days else "最近7天")

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
.ai-box{{margin-top:16px;border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:18px}}.ai-box h3{{color:#0b4db3;margin-bottom:12px}}.ai-box div{{background:#f5f9ff;border-radius:14px;padding:12px;margin-top:10px}}.ai-box b{{color:#0b4db3}}.ai-box p{{font-size:14px;line-height:1.7;font-weight:760;margin-top:5px}}
.level-block{{margin-bottom:22px}}.level-title{{font-size:20px;color:#062b78;font-weight:950;margin:4px 0 12px}}.level-title span{{font-size:12px;color:#0b63d8;margin-left:8px}}
.event-table{{width:100%;border-collapse:collapse}}.event-table th{{text-align:left;background:#f3f8ff;color:#0b4db3;font-size:13px;padding:12px;border-bottom:1px solid #dbe6f6}}.event-table td{{font-size:14px;line-height:1.45;font-weight:760;color:#233e68;padding:12px;border-bottom:1px solid #edf2fa;vertical-align:top}}
.rank{{display:inline-flex;width:28px;height:28px;align-items:center;justify-content:center;background:#0b63d8;color:#fff;border-radius:9px;font-weight:950}}.event-title{{font-weight:950;color:#0d2d68}}.event-title em{{display:block;font-size:11px;color:#7b8ca8;font-style:normal;margin-top:4px}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.panel{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:18px}}.panel h3{{font-size:18px;color:#0b4db3;margin-bottom:14px}}
.bar-row{{display:grid;grid-template-columns:118px 1fr 42px;gap:10px;align-items:center;margin-bottom:12px}}.bar-row label{{font-size:13px;font-weight:900;color:#183a76;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.bar-row b{{font-size:13px;color:#0b63d8;text-align:right}}.bar{{height:10px;background:#edf5ff;border-radius:999px;overflow:hidden}}.bar i{{display:block;height:100%;background:linear-gradient(90deg,#0b63d8,#18a2ff);border-radius:999px}}.bar.green i{{background:linear-gradient(90deg,#0f766e,#34d399)}}
.word-cloud{{min-height:260px;border:1px solid #dbe6f6;border-radius:20px;background:linear-gradient(135deg,#f8fbff,#eef6ff);display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:14px 18px;padding:22px}}.kw{{background:#fff;border:1px solid #dbe6f6;border-radius:999px;padding:7px 14px;font-size:14px;font-weight:950;color:#0b63d8;box-shadow:0 6px 14px rgba(20,60,110,.06)}}.kw.mid{{font-size:17px;background:#ecfdf5;color:#0f766e}}.kw.big{{font-size:25px;background:#dcecff;color:#062b78}}
.region-card{{border:1px solid #dbe6f6;border-radius:20px;background:linear-gradient(135deg,#f7fbff,#fff);padding:17px;min-height:170px}}.region-card h3{{font-size:21px;color:#0b4db3;margin-bottom:10px}}.region-card p{{font-size:14px;line-height:1.55;font-weight:760;color:#315174}}.region-card b{{display:block;margin-top:10px;font-size:13px;line-height:1.5;color:#0f766e}}
.products{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.product-card{{border:1px solid #dbe6f6;border-radius:20px;background:#fbfdff;padding:13px;box-shadow:0 8px 18px rgba(20,60,110,.06)}}.product-cover{{height:150px;border-radius:16px;background:radial-gradient(circle at 80% 20%,rgba(25,163,255,.22),transparent 30%),linear-gradient(135deg,#edf5ff,#f8fbff);display:flex;align-items:center;justify-content:center;flex-direction:column;position:relative;margin-bottom:11px}}.product-cover span{{position:absolute;top:8px;left:8px;background:#062b78;color:#fff;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:950}}.product-cover i{{font-style:normal;font-size:46px}}.product-cover strong{{font-size:21px;color:#0b4db3;margin-top:8px}}.product-cover em{{font-style:normal;color:#0f766e;background:#ecfdf5;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:900;margin-top:8px}}.product-card h4{{font-size:15.5px;line-height:1.35;color:#0d2d68;min-height:42px}}.brand{{font-size:12px;color:#0b63d8;font-weight:900;margin-top:6px}}.tags{{font-size:12px;color:#1d8c54;font-weight:850;margin-top:7px}}.insight{{margin-top:9px;background:#f0fdf4;color:#166534;border-radius:12px;padding:9px;font-size:12.5px;line-height:1.45;font-weight:850}}
.plan-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.plan-card{{border-radius:18px;background:linear-gradient(135deg,#fff7ed,#fff);border:1px solid #fed7aa;color:#7c2d12;font-size:15px;line-height:1.6;font-weight:850;padding:17px;min-height:132px}}
.empty{{color:#8a99ad;font-size:14px;text-align:center;padding:24px}}.footer{{text-align:center;color:#7184a3;font-size:12px;margin:16px 0 4px}}
.event-title a,
.product-card h4 a {{
  color:#0b63d8;
  text-decoration:none;
}}

.event-title a:hover,
.product-card h4 a:hover {{
  text-decoration:underline;
}}
</style>
</head>
<body>
<div class='report'>
  <section class='cover'>
    <div class='cover-tag'>361°儿童 · 周度行业情报</div>
    <h1>运动品牌行业周报</h1>
    <h2>新闻事实驱动｜A/B/C分级 × 品牌动作 × 商品趋势 × 区域机会</h2>
    <div class='cover-foot'>统计周期：{esc(date_range)} ｜ 生成时间：{generated_time}</div>
    <div class='stats'>
      <div class='stat'><b>{len(history_days)}</b><span>日报样本</span></div>
      <div class='stat'><b>{len(a_events)+len(b_events)+len(c_events)}</b><span>ABC事件</span></div>
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
    <div class='head'><h2>P3-P5｜本周行业事件分级</h2><span>A/B/C LEVEL NEWS</span></div>
    {render_abc_tables()}
  </section>

  <section class='page'>
    <div class='head'><h2>P6-P7｜竞品热度与趋势地图</h2><span>BRAND / CATEGORY / KEYWORDS</span></div>
    <div class='grid-2'>
      <div class='panel'><h3>品牌热度排行</h3>{render_brand_bars()}</div>
      <div class='panel'><h3>品类/场景热度排行</h3>{render_category_bars()}</div>
    </div>
    <div style='height:16px'></div>
    <div class='word-cloud'>{render_keyword_cloud()}</div>
  </section>

  <section class='page'>
    <div class='head'><h2>P8｜每周尖货 / 商品机会信号</h2><span>PRODUCT SIGNALS</span></div>
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
print(f"A: {len(a_events)} | B: {len(b_events)} | C: {len(c_events)} | keywords: {len(keywords)} | product signals: {signal_count}")
