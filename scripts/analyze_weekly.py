from pathlib import Path
from datetime import datetime
import json
import os
import requests
from collections import Counter, defaultdict

HISTORY_DIR = Path("output/history")
PRODUCT_DIR = Path("output/products")
WEEKLY_DIR = Path("output/weekly")
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = WEEKLY_DIR / "weekly_analysis.json"


# =========================================================
# 基础工具
# =========================================================
def safe_list(value):
    return value if isinstance(value, list) else []


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load json error: {path} {e}")
        return default


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


def text_has(text, keys):
    return any(k in text for k in keys)


def pair_list_to_dict_list(items, key_name):
    result = []

    for item in safe_list(items):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            result.append({
                key_name: item[0],
                "count": item[1]
            })
        elif isinstance(item, dict):
            result.append(item)

    return result


def call_deepseek(prompt, max_tokens=2200):
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        print("DEEPSEEK_API_KEY not found")
        return ""

    url = "https://api.deepseek.com/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "你是361°儿童事业部经营管理部高级行业分析师，擅长运动品牌、儿童运动、商品趋势、竞品动态、区域天气和平台流量分析。只输出严格JSON。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.32,
        "max_tokens": max_tokens
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("deepseek error:", e)
        return ""


def extract_json_text(text):
    if not text:
        return None

    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return None


# =========================================================
# 数据采集
# =========================================================
def collect_text_from_history(days):
    texts = []

    for day in days:
        for key in ["today_insight", "ai_summary"]:
            if day.get(key):
                texts.append(str(day.get(key)))

        for item in safe_list(day.get("top_news")):
            if isinstance(item, dict):
                texts.extend([
                    str(item.get("title", "")),
                    str(item.get("desc", "")),
                    str(item.get("tag", ""))
                ])

        for item in safe_list(day.get("competitor_news")):
            if isinstance(item, dict):
                texts.extend([
                    str(item.get("brand", "")),
                    str(item.get("title", "")),
                    str(item.get("source", ""))
                ])

        for item in safe_list(day.get("trend_items")):
            if isinstance(item, dict):
                texts.extend([
                    str(item.get("title", "")),
                    str(item.get("desc", "")),
                    str(item.get("tag", ""))
                ])

        for item in safe_list(day.get("warnings")):
            texts.append(str(item))

        if isinstance(day.get("region_reports"), dict):
            for region in day.get("region_reports", {}).values():
                if isinstance(region, dict):
                    for key in ["name", "city", "hot", "flow", "focus", "action", "star"]:
                        if region.get(key):
                            texts.append(str(region.get(key)))

        for word in safe_list(day.get("words")):
            texts.append(str(word))

        if isinstance(day.get("weather"), dict):
            for v in day.get("weather", {}).values():
                texts.append(str(v))

    return " ".join(texts)


def collect_top_news(days):
    counter = Counter()
    tag_counter = Counter()
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
            if tag:
                tag_counter[tag] += 1
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
        "top_titles": [{"title": k, "count": v} for k, v in counter.most_common(15)],
        "top_tags": [{"tag": k, "count": v} for k, v in tag_counter.most_common(10)],
        "top_sources": [{"source": k, "count": v} for k, v in source_counter.most_common(10)],
        "news_pool": news_pool[-50:]
    }


def collect_competitor_news(days):
    counter = Counter()
    brand_counter = Counter()
    pool = []

    for day in days:
        date = day.get("date", "")

        for item in safe_list(day.get("competitor_news")):
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            brand = str(item.get("brand", "")).strip()

            if not title:
                continue

            key = f"{brand}|{title}"
            counter[key] += 1

            if brand:
                brand_counter[brand] += 1

            pool.append({
                "date": date,
                "brand": brand,
                "title": title,
                "source": item.get("source", ""),
                "time": item.get("published_at") or item.get("time") or "",
                "link": item.get("link", "")
            })

    top_items = []

    for key, count in counter.most_common(20):
        brand, title = key.split("|", 1)
        matched = next((x for x in pool if x["brand"] == brand and x["title"] == title), {})
        top_items.append({
            "brand": brand,
            "title": title,
            "count": count,
            "source": matched.get("source", ""),
            "date": matched.get("date", "")
        })

    return {
        "top_brands": [{"brand": k, "count": v} for k, v in brand_counter.most_common(12)],
        "top_items": top_items,
        "pool": pool[-50:]
    }


def collect_keywords(days):
    counter = Counter()

    for day in days:
        for word in safe_list(day.get("words")):
            word = str(word).strip()
            if word:
                counter[word] += 1

    return [{"word": k, "count": v} for k, v in counter.most_common(40)]


def collect_weather(days):
    weather_counter = Counter()
    pool = []

    for day in days:
        date = day.get("date", "")
        weather = day.get("weather", {})

        if not isinstance(weather, dict):
            continue

        for region, desc in weather.items():
            desc = str(desc)
            pool.append({
                "date": date,
                "region": region,
                "desc": desc
            })

            for key in ["高温", "防晒", "凉感", "速干", "降雨", "暴雨", "强对流", "防雨", "防滑", "低温", "保暖"]:
                if key in desc:
                    weather_counter[key] += 1

    return {
        "top_weather_keywords": [{"word": k, "count": v} for k, v in weather_counter.most_common(10)],
        "pool": pool
    }


def collect_regions(days):
    region_counter = defaultdict(Counter)
    action_counter = defaultdict(Counter)
    star_counter = defaultdict(Counter)
    raw_counter = defaultdict(list)

    for day in days:
        date = day.get("date", "")

        if not isinstance(day.get("region_reports"), dict):
            continue

        for region in day.get("region_reports", {}).values():
            if not isinstance(region, dict):
                continue

            name = str(region.get("name") or region.get("region") or "").strip()
            if not name:
                continue

            parts = []

            for key in ["city", "hot", "flow", "focus"]:
                value = str(region.get(key, "")).strip()
                if value:
                    region_counter[name][value] += 1
                    parts.append(value)

            action = str(region.get("action", "")).strip()
            if action:
                action_counter[name][action] += 1
                parts.append(action)

            star = str(region.get("star", "")).strip()
            if star:
                star_counter[name][star] += 1

            if parts:
                raw_counter[name].append({
                    "date": date,
                    "text": "；".join(parts)
                })

    result = []

    for region, focuses in region_counter.items():
        combined_text = " ".join([x["text"] for x in raw_counter[region]])

        top_focus = [{"focus": k, "count": v} for k, v in focuses.most_common(6)]
        top_actions = [{"action": k, "count": v} for k, v in action_counter[region].most_common(5)]
        top_star = star_counter[region].most_common(1)
        star = top_star[0][0] if top_star else ""

        summary = build_region_summary(region, combined_text, top_focus)

        result.append({
            "region": region,
            "star": star,
            "top_focus": top_focus,
            "top_actions": top_actions,
            "summary": summary
        })

    return sorted(result, key=lambda x: x.get("star", ""), reverse=True)


def build_region_summary(region, text, top_focus):
    focus_words = "、".join([x["focus"] for x in top_focus[:2]]) or "天气、客流和商品机会"

    if text_has(text, ["降雨", "暴雨", "强对流", "雷阵雨"]):
        return f"{region}本周天气扰动较明显，雨天客流、防滑防雨和室内运动场景是主要关注点。"

    if text_has(text, ["高温", "防晒", "凉感", "速干"]):
        return f"{region}本周夏季功能需求较突出，防晒、凉感、速干和透气商品关注度较高。"

    if text_has(text, ["文旅", "出行", "户外", "露营", "轻户外"]):
        return f"{region}本周出行和轻户外场景信号较强，亲子出游和舒适鞋服存在机会。"

    if text_has(text, ["商圈", "客流", "活动", "购物节"]):
        return f"{region}本周商圈活动和客流信号较活跃，需关注重点门店承接效率。"

    return f"{region}本周主要关注{focus_words}，整体机会以区域客流和商品承接为主。"


# =========================================================
# 商品数据
# =========================================================
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
        if not isinstance(brand_item, dict):
            continue

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

    products = sorted(products, key=lambda x: int(x.get("sales_heat") or 0), reverse=True)

    return {
        "date": data.get("date", ""),
        "brands": [x.get("brand", "") for x in safe_list(data.get("brands")) if isinstance(x, dict)],
        "top_products": products[:30],
        "top_categories": [{"category": k, "count": v} for k, v in category_counter.most_common(20)],
        "top_tags": [{"tag": k, "count": v} for k, v in tag_counter.most_common(20)]
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
        "signals": data.get("signals", [])[:100]
    }


# =========================================================
# 机会 / 风险
# =========================================================
def infer_weekly_opportunities(text, keywords, product_signals):
    rules = [
        {
            "theme": "防晒凉感",
            "keys": ["防晒", "凉感", "速干", "高温", "夏季", "防晒衣"],
            "suggestion": "防晒衣、凉感T、速干短裤、透气童鞋可作为夏季主推组合。"
        },
        {
            "theme": "儿童运动",
            "keys": ["儿童", "童装", "童鞋", "儿童运动", "校园", "青少年"],
            "suggestion": "儿童运动鞋、校园运动鞋、青少年训练鞋需强化成长型和专业运动表达。"
        },
        {
            "theme": "户外轻运动",
            "keys": ["户外", "轻户外", "露营", "骑行", "文旅", "出行"],
            "suggestion": "轻户外鞋服、防晒帽包、溯溪鞋和舒适出行鞋具备组合机会。"
        },
        {
            "theme": "品牌事件",
            "keys": ["签约", "代言", "联名", "实验室", "旗舰店", "开业", "发布"],
            "suggestion": "品牌重大动作影响消费者心智，需关注竞品声量、产品卖点和传播打法。"
        },
        {
            "theme": "直播电商",
            "keys": ["直播", "抖音", "小红书", "618", "大促", "店播"],
            "suggestion": "直播同款、爆款价格带和平台热词款式应沉淀到商品观察。"
        },
        {
            "theme": "跑鞋科技",
            "keys": ["碳板", "厚底", "缓震", "竞速", "跑鞋", "马拉松", "超临界"],
            "suggestion": "跑鞋需区分竞速、厚底缓震、校园跑步和日常慢跑场景。"
        }
    ]

    signal_text = json.dumps(product_signals, ensure_ascii=False)
    full_text = text + " " + signal_text

    result = []

    for rule in rules:
        count = sum(full_text.count(k) for k in rule["keys"])

        for item in keywords:
            word = item.get("word", "")
            if any(k in word for k in rule["keys"]):
                count += item.get("count", 0)

        if count > 0:
            result.append({
                "theme": rule["theme"],
                "heat": count,
                "suggestion": rule["suggestion"]
            })

    return sorted(result, key=lambda x: x["heat"], reverse=True)[:10]


def infer_risks(text, product_signals):
    risks = []

    if text_has(text, ["降雨", "暴雨", "强对流", "雷阵雨"]):
        risks.append("天气扰动会影响户外客流，需关注商场内场承接和防滑防雨商品表现。")

    if text_has(text, ["大促", "618", "双11", "低价", "价格带"]):
        risks.append("平台大促强化价格心智，线下需关注比价、折扣效率和核心SKU转化。")

    if text_has(text, ["消费分层", "理性消费", "客单", "折扣"]):
        risks.append("理性消费和客单压力仍在，商品结构需兼顾功能刚需和价格带效率。")

    categories = str(product_signals.get("top_categories", ""))

    if "跑鞋" in categories or "跑步科技" in categories:
        risks.append("跑鞋科技信息密集，终端若卖点表达不足，容易出现消费者无感知。")

    if "儿童" in categories or "童鞋" in categories:
        risks.append("儿童运动商品竞争加剧，需避免仅做成人款缩小版。")

    if not risks:
        risks.append("本周风险整体可控，重点关注天气、平台流量、商品同质化和区域客流差异。")

    return risks[:6]


def build_actions(opportunities, regions):
    actions = []

    for opp in opportunities[:5]:
        theme = opp.get("theme", "")

        if "儿童" in theme:
            actions.append("儿童运动方向重点沉淀校园运动、青少年训练、亲子运动和成长型科技卖点。")
        elif "品牌" in theme:
            actions.append("竞品重大事件需沉淀品牌、产品、代言人、渠道动作和可借鉴打法。")
        elif "户外" in theme:
            actions.append("轻户外方向跟踪防晒、溯溪、户外鞋服、帽包配件和亲子出行组合。")
        elif "防晒" in theme:
            actions.append("防晒凉感方向继续跟踪防晒衣、凉感T、速干短裤、运动凉鞋和帽包。")
        elif "直播" in theme:
            actions.append("平台内容方向关注直播同款、达人种草、价格带和爆款货盘变化。")
        elif "跑鞋" in theme:
            actions.append("跑鞋方向区分竞速、缓震、训练、校园跑和日常通勤场景。")

    if regions:
        actions.append("区域部分按周更新，不使用固定区域结论，重点看天气、客流和区域机会变化。")

    actions.append("每周复盘高频新闻、竞品动作、商品信号和热词，形成下周汇报输入。")

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
    text = themes + categories + keywords

    if text_has(text, ["儿童", "青少年", "校园"]):
        suggestions.append("青少年跑鞋、篮球鞋、训练鞋可强化成人化设计表达和科技感。")

    if text_has(text, ["防晒", "凉感", "速干"]):
        suggestions.append("防晒衣、凉感T恤、速干短裤、运动凉鞋、防晒帽包仍是夏季重点。")

    if text_has(text, ["户外", "冲锋衣", "防水", "山系"]):
        suggestions.append("轻户外鞋服、冲锋衣、防水外套、溯溪鞋和户外鞋值得持续跟踪。")

    if text_has(text, ["碳板", "厚底", "跑鞋", "缓震"]):
        suggestions.append("跑鞋矩阵需区分碳板竞速、厚底缓震、轻量训练和校园跑步。")

    if not suggestions:
        suggestions = [
            "增加青少年跑鞋、篮球鞋、训练服的成人化设计表达。",
            "强化防晒衣、凉感T恤、速干短裤、运动凉鞋组合。",
            "补充轻户外鞋服、帽包配件、亲子同款和校园运动套装。"
        ]

    return suggestions[:6]


# =========================================================
# 汇总判断
# =========================================================
def build_summary(days, news, competitor_news, keywords, regions, weather, product_signals, opportunities):
    dates = [d.get("date", "") for d in days if d.get("date")]
    date_range = f"{dates[0]} 至 {dates[-1]}" if dates else ""

    top_words = "、".join([x["word"] for x in keywords[:6]]) or "品牌事件、平台流量、商品趋势"
    top_news_tags = "、".join([x["tag"] for x in news.get("top_tags", [])[:4]]) or "品牌竞争、平台流量、天气消费"
    top_brands = "、".join([x["brand"] for x in competitor_news.get("top_brands", [])[:5]]) or "安踏、李宁、Nike、Adidas"
    top_opps = "、".join([x["theme"] for x in opportunities[:3]]) or "儿童运动、防晒凉感、品牌事件"
    region_names = "、".join([x.get("region", "") for x in regions[:4]]) or "重点区域"
    weather_words = "、".join([x["word"] for x in weather.get("top_weather_keywords", [])[:4]]) or "天气扰动"

    return {
        "date_range": date_range,
        "core_judgement": f"本周行业信息集中在{top_news_tags}，高频热词为{top_words}，竞品动态主要围绕{top_brands}展开。",
        "news_direction": f"新闻侧重点关注品牌签约、联名、新品、平台大促和内容声量变化，特别是重大品牌事件对消费者心智的影响。",
        "product_direction": f"商品侧建议关注{top_opps}，并结合商品信号判断儿童运动、夏季功能和轻户外方向。",
        "regional_direction": f"区域侧重点关注{region_names}，天气关键词集中在{weather_words}，需结合区域客流变化理解机会。",
        "next_action": f"下周建议围绕{top_opps}持续跟踪竞品事件、商品信号、天气变化和平台热词，形成汇报页输入。"
    }


# =========================================================
# 主程序
# =========================================================
def main():
    days = load_json_files(HISTORY_DIR, limit=7)
    products = load_products()
    product_signals = load_product_signals()

    text = collect_text_from_history(days)

    news = collect_top_news(days)
    competitor = collect_competitor_news(days)
    keywords = collect_keywords(days)
    regions = collect_regions(days)
    weather = collect_weather(days)

    opportunities = infer_weekly_opportunities(
        text=text,
        keywords=keywords,
        product_signals=product_signals
    )

    risks = infer_risks(text, product_signals)
    actions = build_actions(opportunities, regions)
    product_suggestions = build_product_suggestions(opportunities, product_signals)

    summary = build_summary(
        days=days,
        news=news,
        competitor_news=competitor,
        keywords=keywords,
        regions=regions,
        weather=weather,
        product_signals=product_signals,
        opportunities=opportunities
    )

    ai_prompt = f"""
请基于以下周报数据，生成适合361°儿童事业部经营管理部对总经理汇报的周度行业判断。

要求：
1. 输出严格JSON，不要markdown。
2. 不要写成周总汇报，不要出现周总。
3. 重点是行业事实、竞品动态、商品趋势、区域天气和下周关注。
4. 经营动作可以有，但不要太重。
5. 语言要像正式经营周报，不要口号。

输出格式：
{{
  "weekly_core_view": "本周核心观点，80字以内",
  "news_summary": "本周新闻变化，100字以内",
  "competitor_summary": "竞品动态总结，100字以内",
  "product_summary": "商品趋势总结，100字以内",
  "region_weather_summary": "区域与天气总结，100字以内",
  "next_week_focus": "下周重点关注，100字以内"
}}

本周TOP新闻：
{news.get("news_pool", [])[-20:]}

竞品动态：
{competitor.get("pool", [])[-20:]}

热词：
{keywords[:20]}

区域：
{regions[:6]}

天气：
{weather}

商品信号：
{{
  "top_categories": {product_signals.get("top_categories", [])[:10]},
  "top_brands": {product_signals.get("top_brands", [])[:10]},
  "top_keywords": {product_signals.get("top_keywords", [])[:10]}
}}

机会方向：
{opportunities[:8]}

风险：
{risks}
"""

    ai_raw = call_deepseek(ai_prompt, max_tokens=2200)
    ai_judgement = extract_json_text(ai_raw)

    if not isinstance(ai_judgement, dict):
        ai_judgement = {
            "weekly_core_view": summary.get("core_judgement", ""),
            "news_summary": summary.get("news_direction", ""),
            "competitor_summary": "",
            "product_summary": summary.get("product_direction", ""),
            "region_weather_summary": summary.get("regional_direction", ""),
            "next_week_focus": summary.get("next_action", "")
        }

    output = {
        "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "ai_judgement": ai_judgement,
        "news": news,
        "competitor_news": competitor,
        "keywords": keywords,
        "regions": regions,
        "weather": weather,
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
    print(f"days loaded: {len(days)}")
    print(f"news count: {len(news.get('news_pool', []))}")
    print(f"competitor count: {len(competitor.get('pool', []))}")
    print(f"regions generated: {len(regions)}")


if __name__ == "__main__":
    main()
