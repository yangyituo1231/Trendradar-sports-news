from pathlib import Path
from datetime import datetime
import json
from collections import Counter, defaultdict

HISTORY_DIR = Path("output/history")
PRODUCT_DIR = Path("output/products")
WEEKLY_DIR = Path("output/weekly")
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = WEEKLY_DIR / "weekly_analysis.json"


def load_json_files(folder, limit=7):
    if not folder.exists():
        return []

    files = sorted(folder.glob("*.json"))[-limit:]
    data = []

    for file in files:
        try:
            item = json.loads(file.read_text(encoding="utf-8"))
            item["_file"] = str(file)
            data.append(item)
        except Exception as e:
            print(f"load error: {file} {e}")

    return data


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load json error: {path} {e}")
        return default


def safe_list(value):
    return value if isinstance(value, list) else []


def collect_text_from_history(days):
    texts = []

    for day in days:
        for key in ["today_insight", "ai_summary"]:
            if day.get(key):
                texts.append(str(day.get(key)))

        for item in safe_list(day.get("top_news")):
            if isinstance(item, dict):
                texts.append(str(item.get("title", "")))
                texts.append(str(item.get("desc", "")))
                texts.append(str(item.get("tag", "")))

        for item in safe_list(day.get("trend_items")):
            if isinstance(item, dict):
                texts.append(str(item.get("title", "")))
                texts.append(str(item.get("desc", "")))
                texts.append(str(item.get("tag", "")))

        for item in safe_list(day.get("warnings")):
            texts.append(str(item))

        for region in safe_list(day.get("regions")):
            if isinstance(region, dict):
                texts.append(str(region.get("hot", "")))
                texts.append(str(region.get("flow", "")))
                texts.append(str(region.get("focus", "")))
                texts.append(str(region.get("action", "")))

        for word in safe_list(day.get("words")):
            texts.append(str(word))

    return " ".join(texts)


def collect_top_news(days):
    counter = Counter()
    source_counter = Counter()
    news_pool = []

    for day in days:
        date = day.get("date", "")

        for item in safe_list(day.get("top_news")):
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            if not title:
                continue

            tag = str(item.get("tag", ""))
            source = str(item.get("source", ""))

            counter[title] += 1
            if source:
                source_counter[source] += 1

            news_pool.append({
                "date": date,
                "title": title,
                "tag": tag,
                "source": source,
                "desc": str(item.get("desc", "")),
                "link": str(item.get("link", ""))
            })

    return {
        "top_titles": [
            {"title": title, "count": count}
            for title, count in counter.most_common(10)
        ],
        "top_sources": [
            {"source": source, "count": count}
            for source, count in source_counter.most_common(8)
        ],
        "news_pool": news_pool[-30:]
    }


def collect_keywords(days):
    counter = Counter()

    for day in days:
        for word in safe_list(day.get("words")):
            word = str(word).strip()
            if word:
                counter[word] += 1

    return [
        {"word": word, "count": count}
        for word, count in counter.most_common(30)
    ]


def collect_regions(days):
    region_counter = defaultdict(Counter)
    action_counter = defaultdict(Counter)

    for day in days:
        for region in safe_list(day.get("regions")):
            if not isinstance(region, dict):
                continue

            name = str(region.get("name") or region.get("region") or "").strip()
            if not name:
                continue

            focus = str(region.get("focus", "")).strip()
            action = str(region.get("action", "")).strip()

            if focus:
                region_counter[name][focus] += 1

            if action:
                action_counter[name][action] += 1

    result = []

    for region, focuses in region_counter.items():
        result.append({
            "region": region,
            "top_focus": [
                {"focus": k, "count": v}
                for k, v in focuses.most_common(5)
            ],
            "top_actions": [
                {"action": k, "count": v}
                for k, v in action_counter[region].most_common(5)
            ]
        })

    return result


def load_products():
    latest = PRODUCT_DIR / "latest_products.json"

    empty = {
        "date": "",
        "brands": [],
        "top_products": [],
        "top_categories": [],
        "top_tags": []
    }

    data = load_json(latest, {})
    if not data:
        return empty

    products = []
    category_counter = Counter()
    tag_counter = Counter()

    for brand_item in safe_list(data.get("brands")):
        brand = brand_item.get("brand", "")

        for p in safe_list(brand_item.get("products")):
            if not isinstance(p, dict):
                continue

            item = {
                "brand": brand,
                "name": p.get("name", ""),
                "category": p.get("category", ""),
                "price": p.get("price", ""),
                "trend": p.get("trend", ""),
                "sales_heat": p.get("sales_heat", 0),
                "tags": p.get("tags", []),
                "image": p.get("image", ""),
                "reason": p.get("reason", "")
            }

            products.append(item)

            if item["category"]:
                category_counter[item["category"]] += 1

            for tag in safe_list(item["tags"]):
                tag_counter[str(tag)] += 1

    products = sorted(
        products,
        key=lambda x: int(x.get("sales_heat") or 0),
        reverse=True
    )

    return {
        "date": data.get("date", ""),
        "brands": [x.get("brand", "") for x in safe_list(data.get("brands"))],
        "top_products": products[:30],
        "top_categories": [
            {"category": k, "count": v}
            for k, v in category_counter.most_common(20)
        ],
        "top_tags": [
            {"tag": k, "count": v}
            for k, v in tag_counter.most_common(20)
        ]
    }


def load_product_signals():
    latest = PRODUCT_DIR / "latest_product_signals.json"

    empty = {
        "date": "",
        "signal_count": 0,
        "top_brands": [],
        "top_keywords": [],
        "top_categories": [],
        "top_seasons": [],
        "signals": []
    }

    data = load_json(latest, {})
    if not data:
        return empty

    return {
        "date": data.get("date", ""),
        "signal_count": data.get("signal_count", 0),
        "top_brands": data.get("top_brands", []),
        "top_keywords": data.get("top_keywords", []),
        "top_categories": data.get("top_categories", []),
        "top_seasons": data.get("top_seasons", []),
        "signals": data.get("signals", [])[:80]
    }


def pair_list_to_dict_list(items, key_name):
    result = []

    for item in safe_list(items):
        if isinstance(item, list) and len(item) >= 2:
            result.append({
                key_name: item[0],
                "count": item[1]
            })
        elif isinstance(item, tuple) and len(item) >= 2:
            result.append({
                key_name: item[0],
                "count": item[1]
            })
        elif isinstance(item, dict):
            result.append(item)

    return result


def infer_signal_themes(product_signals):
    signals = safe_list(product_signals.get("signals"))
    text = " ".join([
        str(s.get("title", "")) + " " +
        str(s.get("query", "")) + " " +
        " ".join(safe_list(s.get("keyword_hits")))
        for s in signals
        if isinstance(s, dict)
    ])

    themes = [
        {
            "theme": "儿童趋势",
            "keys": ["儿童", "童装", "童鞋", "儿童运动鞋", "Kids", "大童", "小童"],
            "suggestion": "重点观察儿童运动鞋、童装运动化、校园体育和亲子同款的新品变化。"
        },
        {
            "theme": "青少年成人化趋势",
            "keys": ["青少年", "成人化", "校园", "中大童", "训练鞋", "篮球鞋"],
            "suggestion": "青少年产品应继续借鉴成人跑鞋、篮球鞋、训练鞋的科技语言和外观表达。"
        },
        {
            "theme": "跑鞋科技趋势",
            "keys": ["碳板", "厚底", "竞速", "缓震", "跑鞋", "马拉松", "超临界", "氮科技"],
            "suggestion": "跑鞋开发需区分竞速、缓震、训练、校园跑等场景，并强化中底科技表达。"
        },
        {
            "theme": "户外轻运动趋势",
            "keys": ["户外", "轻户外", "冲锋衣", "山系", "露营", "徒步", "越野", "溯溪"],
            "suggestion": "轻户外鞋服、冲锋衣、防水外套、户外鞋和溯溪鞋值得持续跟踪。"
        },
        {
            "theme": "防晒凉感趋势",
            "keys": ["防晒", "凉感", "速干", "冰感", "防晒衣", "凉感T恤"],
            "suggestion": "春夏季应持续关注防晒衣、凉感T、速干短裤、运动凉鞋和防晒帽包。"
        },
        {
            "theme": "秋冬保暖趋势",
            "keys": ["羽绒服", "棉服", "保暖", "加绒", "抓绒", "防滑", "雪地靴"],
            "suggestion": "秋冬需前置关注羽绒服、棉服、抓绒、加绒裤、防滑鞋和防水防寒外套。"
        },
        {
            "theme": "大促节点趋势",
            "keys": ["618", "双11", "双12", "99大促", "开学季", "年货节", "六一"],
            "suggestion": "围绕618、双11、99大促、开学季、六一等节点，建立商品、内容和价格带联动。"
        },
        {
            "theme": "运动场景细分",
            "keys": ["篮球", "足球", "网球", "羽毛球", "乒乓球", "跳绳", "瑜伽", "训练"],
            "suggestion": "商品开发和监测需按跑步、篮球、足球、乒羽、跳绳、训练、通勤等场景拆分。"
        }
    ]

    result = []

    for rule in themes:
        heat = sum(text.count(k) for k in rule["keys"])

        for cat in safe_list(product_signals.get("top_categories")):
            name = cat[0] if isinstance(cat, list) and len(cat) >= 2 else cat.get("category", "") if isinstance(cat, dict) else ""
            count = cat[1] if isinstance(cat, list) and len(cat) >= 2 else cat.get("count", 0) if isinstance(cat, dict) else 0
            if any(k in str(name) for k in rule["keys"]):
                heat += int(count)

        if heat > 0:
            result.append({
                "theme": rule["theme"],
                "heat": heat,
                "suggestion": rule["suggestion"]
            })

    return sorted(result, key=lambda x: x["heat"], reverse=True)


def infer_weekly_opportunities(text, keywords, products, product_signals):
    text_all = text
    signal_themes = infer_signal_themes(product_signals)

    rules = [
        {
            "theme": "防晒凉感",
            "keys": ["防晒", "凉感", "速干", "高温", "夏季"],
            "suggestion": "防晒衣、凉感T、速干短裤、透气童鞋可作为夏季主推组合。"
        },
        {
            "theme": "儿童运动鞋",
            "keys": ["儿童运动鞋", "童鞋", "跑鞋", "校园", "青少年"],
            "suggestion": "儿童跑鞋、校园运动鞋、青少年训练鞋应强化成长型和成人化设计表达。"
        },
        {
            "theme": "户外轻运动",
            "keys": ["户外", "轻户外", "露营", "骑行", "文旅", "出行"],
            "suggestion": "轻户外鞋服、防晒帽包、溯溪鞋和舒适出行鞋具备组合机会。"
        },
        {
            "theme": "直播电商",
            "keys": ["直播", "抖音", "小红书", "618", "双11", "双12", "99大促", "大促", "店播"],
            "suggestion": "直播同款、爆款价格带、平台热词款式应同步沉淀到周报商品观察。"
        },
        {
            "theme": "秋冬保暖",
            "keys": ["保暖", "羽绒服", "棉服", "加绒", "防滑", "抓绒", "雪地靴"],
            "suggestion": "秋冬商品需重点关注保暖、防滑、防水、防风、抓绒和棉羽品类。"
        },
        {
            "theme": "跑鞋科技",
            "keys": ["碳板", "厚底", "缓震", "竞速", "跑鞋", "马拉松", "超临界"],
            "suggestion": "跑鞋应区分碳板竞速、厚底缓震、日常慢跑和校园训练等不同需求。"
        },
        {
            "theme": "运动成人化",
            "keys": ["成人", "青少年", "成人化", "趋势", "通勤", "训练"],
            "suggestion": "青少年产品可借鉴成人跑鞋、训练鞋、户外鞋的科技感和专业感。"
        }
    ]

    opportunities = []

    for rule in rules:
        count = sum(text_all.count(k) for k in rule["keys"])

        for item in keywords:
            word = item.get("word", "")
            if any(k in word for k in rule["keys"]):
                count += item.get("count", 0)

        for sig in signal_themes:
            if sig.get("theme") == rule["theme"] or any(k in sig.get("theme", "") for k in rule["keys"]):
                count += int(sig.get("heat", 0))

        if count > 0:
            opportunities.append({
                "theme": rule["theme"],
                "heat": count,
                "suggestion": rule["suggestion"]
            })

    for sig in signal_themes:
        if sig.get("theme") not in [x.get("theme") for x in opportunities]:
            opportunities.append(sig)

    return sorted(opportunities, key=lambda x: x["heat"], reverse=True)[:10]


def infer_risks(text, product_signals):
    risks = []

    if any(k in text for k in ["降雨", "暴雨", "强对流", "雷阵雨"]):
        risks.append("降雨和强对流天气会影响户外客流，需关注商场内场承接和防滑防雨品类。")

    if any(k in text for k in ["大促", "618", "双11", "双12", "99大促", "低价", "价格带"]):
        risks.append("平台大促会强化价格心智，线下门店需防止只引流不成交。")

    if any(k in text for k in ["消费分层", "理性消费", "客单", "折扣"]):
        risks.append("理性消费和客单压力仍在，商品结构需兼顾功能刚需和价格带效率。")

    categories = str(product_signals.get("top_categories", ""))
    if "跑步科技" in categories or "跑鞋" in categories:
        risks.append("跑鞋科技信息密集，若终端卖点表达不足，容易出现产品有配置但消费者无感知的问题。")

    if "儿童服装" in categories or "儿童鞋" in categories:
        risks.append("儿童运动商品竞争加剧，需避免仅做成人款缩小版，应强化足弓、成长、校园和安全防护卖点。")

    if not risks:
        risks.append("本周风险整体可控，重点关注天气、平台流量、商品同质化和区域客流差异。")

    return risks[:6]


def build_actions(opportunities, product_signals):
    actions = []

    for opp in opportunities[:6]:
        theme = opp.get("theme", "")
        if "儿童" in theme or "青少年" in theme:
            actions.append("建立儿童/青少年商品趋势清单，重点跟踪跑鞋、篮球鞋、校园运动鞋和成人化设计语言。")
        elif "跑鞋" in theme:
            actions.append("跑鞋监测需拆分碳板竞速、厚底缓震、慢跑训练、校园体育等不同场景。")
        elif "户外" in theme:
            actions.append("轻户外方向重点跟踪冲锋衣、防水外套、户外鞋、溯溪鞋和山系穿搭。")
        elif "防晒" in theme:
            actions.append("防晒凉感方向重点跟踪防晒衣、凉感T、速干短裤、遮阳帽和运动凉鞋。")
        elif "秋冬" in theme:
            actions.append("秋冬方向提前跟踪羽绒服、棉服、抓绒、加绒裤、防滑鞋和雪地靴。")
        elif "大促" in theme or "直播" in theme:
            actions.append("大促节点需建立商品价格带、直播同款、平台爆款和会员触达联动机制。")

    actions.append("每周复盘商品趋势信号中反复出现的品牌、品类和场景，形成开发输入清单。")

    result = []
    for x in actions:
        if x not in result:
            result.append(x)

    return result[:6]


def build_product_suggestions(opportunities, product_signals):
    suggestions = []

    themes = " ".join([x.get("theme", "") for x in opportunities])
    categories = str(product_signals.get("top_categories", ""))
    keywords = str(product_signals.get("top_keywords", ""))

    if any(k in themes + categories + keywords for k in ["儿童", "青少年", "成人化"]):
        suggestions.append("增加青少年跑鞋、篮球鞋、训练鞋的成人化设计表达，强化科技感和专业运动心智。")

    if any(k in themes + categories + keywords for k in ["防晒", "凉感", "速干"]):
        suggestions.append("强化防晒衣、凉感T恤、速干短裤、运动凉鞋、防晒帽包的组合开发。")

    if any(k in themes + categories + keywords for k in ["户外", "冲锋衣", "防水", "山系"]):
        suggestions.append("补充轻户外鞋服、冲锋衣、防水外套、溯溪鞋、户外鞋和亲子户外组合。")

    if any(k in themes + categories + keywords for k in ["保暖", "羽绒服", "棉服", "抓绒", "防滑"]):
        suggestions.append("秋冬开发需前置羽绒服、棉服、抓绒、加绒裤、防滑鞋、防水防风外套。")

    if any(k in themes + categories + keywords for k in ["碳板", "厚底", "跑鞋", "缓震"]):
        suggestions.append("跑鞋矩阵需区分碳板竞速、厚底缓震、轻量训练、校园跑步和日常通勤。")

    if not suggestions:
        suggestions = [
            "增加青少年跑鞋、篮球鞋、训练服的成人化设计表达。",
            "强化防晒衣、凉感T恤、速干短裤、运动凉鞋组合开发。",
            "补充轻户外鞋服、帽包配件、亲子同款和校园运动套装。"
        ]

    return suggestions[:6]


def build_summary(days, news, keywords, regions, products, product_signals, opportunities, risks):
    dates = [d.get("date", "") for d in days if d.get("date")]
    date_range = f"{dates[0]} 至 {dates[-1]}" if dates else ""

    top_words = "、".join([x["word"] for x in keywords[:6]]) or "平台流量、商品趋势、区域机会"
    top_product_cats = "、".join([x["category"] for x in products.get("top_categories", [])[:5]]) or "儿童跑鞋、防晒凉感、轻户外"
    top_opps = "、".join([x["theme"] for x in opportunities[:3]]) or "儿童趋势、跑鞋科技、户外轻运动"

    signal_brands = pair_list_to_dict_list(product_signals.get("top_brands"), "brand")
    signal_categories = pair_list_to_dict_list(product_signals.get("top_categories"), "category")

    top_signal_brands = "、".join([x.get("brand", "") for x in signal_brands[:5]]) or "安踏、Nike、Adidas、361儿童"
    top_signal_categories = "、".join([x.get("category", "") for x in signal_categories[:5]]) or "儿童鞋、跑步科技、户外轻运动"

    summary = {
        "date_range": date_range,
        "core_judgement": f"本周行业关注集中在{top_words}；真实商品趋势信号显示，{top_signal_brands}等品牌出现频次较高，{top_signal_categories}是重点方向。",
        "product_direction": f"商品方向建议重点关注{top_product_cats}，并结合{top_opps}强化青少年成人化、功能科技和场景组合。",
        "regional_direction": "区域经营需结合天气、商圈活动和平台热点，重点提升门店陈列、会员触达和导购转化。",
        "next_action": f"下周建议围绕{top_opps}建立商品组合、内容种草和终端陈列联动，并持续沉淀真实商品趋势信号。"
    }

    return summary


def main():
    days = load_json_files(HISTORY_DIR, limit=7)
    products = load_products()
    product_signals = load_product_signals()

    text = collect_text_from_history(days)
    news = collect_top_news(days)
    keywords = collect_keywords(days)
    regions = collect_regions(days)

    opportunities = infer_weekly_opportunities(
        text=text,
        keywords=keywords,
        products=products,
        product_signals=product_signals
    )

    risks = infer_risks(text, product_signals)
    actions = build_actions(opportunities, product_signals)
    product_suggestions = build_product_suggestions(opportunities, product_signals)

    summary = build_summary(
        days=days,
        news=news,
        keywords=keywords,
        regions=regions,
        products=products,
        product_signals=product_signals,
        opportunities=opportunities,
        risks=risks
    )

    output = {
        "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "news": news,
        "keywords": keywords,
        "regions": regions,
        "products": products,
        "product_signals": product_signals,
        "opportunities": opportunities,
        "risks": risks,
        "actions": actions,
        "product_suggestions": product_suggestions
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"weekly analysis saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
