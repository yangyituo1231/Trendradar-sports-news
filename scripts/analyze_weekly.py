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

    top_titles = counter.most_common(10)

    return {
        "top_titles": [
            {"title": title, "count": count}
            for title, count in top_titles
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

    if not latest.exists():
        return {
            "date": "",
            "brands": [],
            "top_products": [],
            "top_categories": [],
            "top_tags": []
        }

    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load products error: {e}")
        return {
            "date": "",
            "brands": [],
            "top_products": [],
            "top_categories": [],
            "top_tags": []
        }

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

def infer_weekly_opportunities(text, keywords, products):
    text_all = text

    rules = [
        {
            "name": "防晒凉感",
            "keys": ["防晒", "凉感", "速干", "高温", "夏季"],
            "suggestion": "防晒衣、凉感T、速干短裤、透气童鞋可作为夏季主推组合。"
        },
        {
            "name": "儿童运动鞋",
            "keys": ["儿童运动鞋", "童鞋", "跑鞋", "校园", "青少年"],
            "suggestion": "儿童跑鞋、校园运动鞋、青少年训练鞋应强化成长型和成人化设计表达。"
        },
        {
            "name": "户外轻运动",
            "keys": ["户外", "轻户外", "露营", "骑行", "文旅", "出行"],
            "suggestion": "轻户外鞋服、防晒帽包、溯溪鞋和舒适出行鞋具备组合机会。"
        },
        {
            "name": "直播电商",
            "keys": ["直播", "抖音", "小红书", "618", "大促", "店播"],
            "suggestion": "直播同款、爆款价格带、平台热词款式应同步沉淀到周报商品观察。"
        },
        {
            "name": "运动成人化",
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

        if count > 0:
            opportunities.append({
                "theme": rule["name"],
                "heat": count,
                "suggestion": rule["suggestion"]
            })

    opportunities = sorted(opportunities, key=lambda x: x["heat"], reverse=True)

    return opportunities[:8]

def infer_risks(text):
    risks = []

    if any(k in text for k in ["降雨", "暴雨", "强对流", "雷阵雨"]):
        risks.append("降雨和强对流天气会影响户外客流，需关注商场内场承接和防滑防雨品类。")

    if any(k in text for k in ["大促", "618", "低价", "价格带"]):
        risks.append("平台大促会强化价格心智，线下门店需防止只引流不成交。")

    if any(k in text for k in ["消费分层", "理性消费", "客单", "折扣"]):
        risks.append("理性消费和客单压力仍在，商品结构需兼顾功能刚需和价格带效率。")

    if not risks:
        risks.append("本周风险整体可控，重点关注天气、平台流量和区域客流差异。")

    return risks[:5]

def build_summary(days, news, keywords, regions, products, opportunities, risks):
    dates = [d.get("date", "") for d in days if d.get("date")]
    date_range = f"{dates[0]} 至 {dates[-1]}" if dates else ""

    summary = {
        "date_range": date_range,
        "core_judgement": "",
        "product_direction": "",
        "regional_direction": "",
        "next_action": ""
    }

    top_words = "、".join([x["word"] for x in keywords[:6]])
    top_product_cats = "、".join([x["category"] for x in products.get("top_categories", [])[:5]])
    top_opps = "、".join([x["theme"] for x in opportunities[:3]])

    summary["core_judgement"] = f"本周行业关注集中在{top_words}，运动消费继续围绕平台流量、天气功能品类和户外场景展开。"
    summary["product_direction"] = f"商品方向建议重点关注{top_product_cats}，同时强化青少年成人化、功能科技和场景组合。"
    summary["regional_direction"] = "区域经营需结合天气、商圈活动和平台热点，重点提升门店陈列、会员触达和导购转化。"
    summary["next_action"] = f"下周建议围绕{top_opps}建立商品组合、内容种草和终端陈列联动。"

    return summary

def main():
    days = load_json_files(HISTORY_DIR, limit=7)
    products = load_products()

    text = collect_text_from_history(days)
    news = collect_top_news(days)
    keywords = collect_keywords(days)
    regions = collect_regions(days)
    opportunities = infer_weekly_opportunities(text, keywords, products)
    risks = infer_risks(text)

    summary = build_summary(
        days=days,
        news=news,
        keywords=keywords,
        regions=regions,
        products=products,
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
        "opportunities": opportunities,
        "risks": risks
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"weekly analysis saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
