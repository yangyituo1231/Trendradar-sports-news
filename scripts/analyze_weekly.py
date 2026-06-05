from pathlib import Path
from datetime import datetime
import json
import os
import re
import requests
from collections import Counter, defaultdict

# =========================================================
# 文件路径
# =========================================================
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


def clean_text(value):
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def to_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


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
    text = clean_text(text)
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


def dedupe_by_key(items, key_name, limit=None):
    result = []
    used = set()

    for item in safe_list(items):
        if not isinstance(item, dict):
            continue

        key = clean_text(item.get(key_name, ""))
        if not key or key in used:
            continue

        result.append(item)
        used.add(key)

        if limit and len(result) >= limit:
            break

    return result


def extract_json_text(text):
    if not text:
        return None

    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # 先尝试对象
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    # 再尝试数组
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return None


def call_deepseek(prompt, max_tokens=2600):
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
                "content": (
                    "你是361°儿童事业部经营管理部高级行业分析师，擅长运动品牌、儿童运动、"
                    "商品趋势、竞品动态、区域天气和平台流量分析。必须基于输入数据生成判断，"
                    "不能套用固定模板，不能编造输入中不存在的新闻事实。只输出严格JSON。"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.28,
        "max_tokens": max_tokens
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=75)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("deepseek error:", e)
        return ""


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
                    str(item.get("tag", "")),
                    str(item.get("source", ""))
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

            title = clean_text(item.get("title", ""))
            if not title:
                continue

            tag = clean_text(item.get("tag", ""))
            source = clean_text(item.get("source", ""))

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
                "desc": clean_text(item.get("desc", "")),
                "link": clean_text(item.get("link", "")),
                "published_at": clean_text(item.get("published_at") or item.get("pubDate") or item.get("date") or item.get("time") or "")
            })

    return {
        "top_titles": [{"title": k, "count": v} for k, v in counter.most_common(20)],
        "top_tags": [{"tag": k, "count": v} for k, v in tag_counter.most_common(12)],
        "top_sources": [{"source": k, "count": v} for k, v in source_counter.most_common(12)],
        "news_pool": news_pool[-80:]
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

            title = clean_text(item.get("title", ""))
            brand = clean_text(item.get("brand", ""))

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
                "source": clean_text(item.get("source", "")),
                "time": clean_text(item.get("published_at") or item.get("time") or ""),
                "link": clean_text(item.get("link", ""))
            })

    top_items = []

    for key, count in counter.most_common(30):
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
        "top_brands": [{"brand": k, "count": v} for k, v in brand_counter.most_common(15)],
        "top_items": top_items,
        "pool": pool[-80:]
    }


def collect_keywords(days):
    counter = Counter()

    for day in days:
        for word in safe_list(day.get("words")):
            word = clean_text(word)
            if word:
                counter[word] += 1

    return [{"word": k, "count": v} for k, v in counter.most_common(50)]


def collect_weather(days):
    weather_counter = Counter()
    pool = []

    for day in days:
        date = day.get("date", "")
        weather = day.get("weather", {})

        if not isinstance(weather, dict):
            continue

        for region, desc in weather.items():
            desc = clean_text(desc)
            pool.append({
                "date": date,
                "region": region,
                "desc": desc
            })

            for key in [
                "高温", "防晒", "凉感", "速干", "降雨", "暴雨", "强对流", "雷阵雨",
                "防雨", "防滑", "低温", "保暖", "雨雪", "结冰", "阵风"
            ]:
                if key in desc:
                    weather_counter[key] += 1

    return {
        "top_weather_keywords": [{"word": k, "count": v} for k, v in weather_counter.most_common(12)],
        "pool": pool
    }


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

            name = clean_text(region.get("name") or region.get("region") or "")
            if not name:
                continue

            parts = []

            for key in ["city", "hot", "flow", "focus"]:
                value = clean_text(region.get(key, ""))
                if value:
                    region_counter[name][value] += 1
                    parts.append(value)

            action = clean_text(region.get("action", ""))
            if action:
                action_counter[name][action] += 1
                parts.append(action)

            star = clean_text(region.get("star", ""))
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

    products = sorted(products, key=lambda x: to_int(x.get("sales_heat") or 0), reverse=True)

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
        "signals": data.get("signals", [])[:120]
    }


# =========================================================
# 动态事件 / 动态赛道 / 竞品动作
# =========================================================
EVENT_TYPE_RULES = {
    "代言签约": ["签约", "代言", "合作伙伴", "运动员", "球星", "明星"],
    "联名合作": ["联名", "合作", "IP", "限定", "共创"],
    "新品发布": ["新品", "发布", "首发", "上新", "系列"],
    "研发科技": ["实验室", "科技", "创新中心", "研发", "材料", "中底", "科技平台"],
    "渠道门店": ["旗舰店", "开店", "开业", "门店", "快闪", "线下"],
    "平台大促": ["618", "双11", "双12", "大促", "直播", "店播", "抖音", "天猫", "京东"],
    "组织管理": ["换帅", "CEO", "总裁", "高管", "管理层", "任命"],
    "资本战略": ["投资", "收购", "战略", "出海", "国际化"]
}

ACTION_TYPE_RULES = {
    "品牌营销": ["签约", "代言", "联名", "IP", "明星", "球星", "出圈", "爆火"],
    "商品上新": ["新品", "发布", "首发", "上新", "系列", "配色", "拖鞋", "跑鞋", "篮球鞋"],
    "研发科技": ["实验室", "科技", "创新中心", "研发", "碳板", "中底", "缓震", "材料"],
    "渠道零售": ["旗舰店", "开店", "开业", "商场", "奥莱", "快闪", "门店"],
    "平台流量": ["618", "双11", "大促", "直播", "店播", "抖音", "小红书", "天猫", "京东"],
    "组织战略": ["换帅", "CEO", "总裁", "董事长", "收购", "投资", "出海", "战略"]
}

TRACK_RULES = {
    "儿童篮球": ["篮球", "库里", "Curry", "欧文", "东契奇", "校园篮球", "篮球鞋"],
    "儿童跑步": ["跑步", "跑鞋", "马拉松", "竞速", "缓震", "厚底", "碳板", "校园跑"],
    "防晒凉感": ["防晒", "凉感", "速干", "冰感", "高温", "防晒衣", "短裤"],
    "轻户外": ["户外", "轻户外", "露营", "徒步", "山系", "冲锋衣", "溯溪", "文旅"],
    "运动凉鞋": ["凉鞋", "拖鞋", "洞洞鞋", "沙滩", "恢复拖鞋", "运动凉鞋"],
    "校园运动": ["校园", "开学", "书包", "训练", "体育课", "校服", "青少年"],
    "直播电商": ["直播", "店播", "抖音", "小红书", "达人", "种草", "大促"],
    "亲子出行": ["亲子", "家庭", "出行", "儿童", "文旅", "周末", "度假"],
    "AI科技消费": ["AI", "人工智能", "智能", "机器人", "大模型", "智能硬件"],
    "秋冬保暖": ["保暖", "羽绒服", "棉服", "抓绒", "加绒", "防滑", "雪地靴"]
}


def infer_event_type(title):
    for event_type, keys in EVENT_TYPE_RULES.items():
        if text_has(title, keys):
            return event_type
    return "行业事件"


def infer_action_type(title):
    for action_type, keys in ACTION_TYPE_RULES.items():
        if text_has(title, keys):
            return action_type
    return "综合动作"


def infer_track_from_text(title):
    matched = []
    for track, keys in TRACK_RULES.items():
        score = sum(clean_text(title).count(k) for k in keys)
        if score > 0:
            matched.append((track, score))

    if not matched:
        return "综合趋势"

    matched.sort(key=lambda x: x[1], reverse=True)
    return matched[0][0]


def infer_brand(title, known_brands):
    title = clean_text(title)
    for brand in known_brands:
        if brand and brand in title:
            return brand
    return ""


def build_major_events_rule(news, competitor, product_signals, keywords):
    known_brands = []
    known_brands.extend([x.get("brand", "") for x in competitor.get("top_brands", []) if isinstance(x, dict)])
    known_brands.extend([x[0] if isinstance(x, list) and x else x.get("brand", "") for x in safe_list(product_signals.get("top_brands")) if isinstance(x, (list, dict))])
    known_brands = [clean_text(x) for x in known_brands if clean_text(x)]

    candidates = []

    def add_candidate(title, source="", date="", brand="", base_heat=0, desc=""):
        title = clean_text(title)
        if not title:
            return

        event_type = infer_event_type(title)
        track = infer_track_from_text(title)
        inferred_brand = brand or infer_brand(title, known_brands)

        heat = base_heat
        heat += 22 if event_type != "行业事件" else 0
        heat += 14 if inferred_brand else 0
        heat += 10 if track != "综合趋势" else 0
        heat += sum(title.count(k) * 6 for keys in EVENT_TYPE_RULES.values() for k in keys if k in title)

        candidates.append({
            "title": title,
            "brand": inferred_brand or "行业",
            "event_type": event_type,
            "track": track,
            "heat": clamp(heat, 1, 100),
            "source": source,
            "date": date,
            "impact": desc or build_dynamic_impact(title, event_type, track)
        })

    for item in safe_list(news.get("news_pool")):
        if not isinstance(item, dict):
            continue
        title = item.get("title", "")
        if text_has(title, sum(EVENT_TYPE_RULES.values(), [])):
            add_candidate(
                title=title,
                source=item.get("source", ""),
                date=item.get("date", ""),
                base_heat=45,
                desc=item.get("desc", "")
            )

    for item in safe_list(competitor.get("pool")):
        if not isinstance(item, dict):
            continue
        title = item.get("title", "")
        if text_has(title, sum(EVENT_TYPE_RULES.values(), [])):
            add_candidate(
                title=title,
                brand=item.get("brand", ""),
                source=item.get("source", ""),
                date=item.get("date", ""),
                base_heat=55
            )

    for sig in safe_list(product_signals.get("signals")):
        if not isinstance(sig, dict):
            continue
        title = sig.get("title", "") or sig.get("short_title", "")
        if text_has(title, sum(EVENT_TYPE_RULES.values(), [])):
            brands = safe_list(sig.get("brand_hits"))
            add_candidate(
                title=title,
                brand="、".join(brands[:2]) if brands else "",
                source=sig.get("source", ""),
                date=product_signals.get("date", ""),
                base_heat=to_int(sig.get("heat"), 0)
            )

    candidates = sorted(candidates, key=lambda x: x["heat"], reverse=True)
    return dedupe_by_key(candidates, "title", limit=12)


def build_dynamic_impact(title, event_type, track):
    if event_type == "代言签约":
        return f"提升{track}方向品牌声量与专业心智。"
    if event_type == "联名合作":
        return f"强化话题传播和年轻家庭内容种草。"
    if event_type == "新品发布":
        return f"反映{track}方向商品更新和价格带竞争。"
    if event_type == "研发科技":
        return f"强化产品科技表达，对儿童专业运动卖点有参考。"
    if event_type == "渠道门店":
        return f"体现线下体验和商圈触达继续被品牌重视。"
    if event_type == "平台大促":
        return f"影响平台流量、价格心智和爆款货盘节奏。"
    return "需关注该事件对品牌声量、商品卖点和终端传播的影响。"


def build_weekly_tracks_rule(text, keywords, product_signals, news, competitor):
    track_counter = Counter()
    source_counter = defaultdict(list)

    all_text_chunks = []

    for item in safe_list(news.get("news_pool")):
        if isinstance(item, dict):
            all_text_chunks.append(("news", item.get("title", ""), item))

    for item in safe_list(competitor.get("pool")):
        if isinstance(item, dict):
            all_text_chunks.append(("competitor", item.get("title", ""), item))

    for sig in safe_list(product_signals.get("signals")):
        if isinstance(sig, dict):
            all_text_chunks.append(("product", f"{sig.get('title','')} {' '.join(safe_list(sig.get('keyword_hits')))} {sig.get('category','')}", sig))

    for kw in safe_list(keywords):
        if isinstance(kw, dict):
            all_text_chunks.append(("keyword", kw.get("word", ""), kw))

    for source_type, chunk, item in all_text_chunks:
        chunk = clean_text(chunk)
        for track, keys in TRACK_RULES.items():
            hit = sum(chunk.count(k) for k in keys)
            if hit > 0:
                weight = 12 if source_type == "product" else 10 if source_type == "competitor" else 8 if source_type == "news" else 4
                heat_add = hit * weight + to_int(item.get("count", 0), 0) + int(to_int(item.get("heat", 0), 0) * 0.15)
                track_counter[track] += heat_add
                if len(source_counter[track]) < 5:
                    title = item.get("title") or item.get("word") or chunk
                    source_counter[track].append(clean_text(title))

    # 允许AI/新闻中出现规则外的新趋势：用商品信号品类补充
    for cat in pair_list_to_dict_list(product_signals.get("top_categories", []), "category"):
        category = clean_text(cat.get("category", ""))
        count = to_int(cat.get("count", 0))
        if category and category not in track_counter:
            track_counter[category] += count * 3
            source_counter[category].append(category)

    result = []
    max_heat = max(track_counter.values()) if track_counter else 1

    for track, count in track_counter.most_common(12):
        result.append({
            "track": track,
            "heat": clamp(round(count / max_heat * 100), 1, 100),
            "raw_score": count,
            "signals": source_counter[track][:5],
            "summary": build_track_summary(track, source_counter[track])
        })

    return result[:10]


def build_track_summary(track, signals):
    signal_text = "、".join([s for s in signals[:2] if s])
    if signal_text:
        return f"{track}受到{signal_text}等信号推动，需关注商品、内容和终端表达联动。"
    return f"{track}热度提升，需继续观察相关商品、竞品动作和平台内容变化。"


def build_competitor_actions_rule(competitor, news):
    items = []

    for item in safe_list(competitor.get("pool")) + safe_list(news.get("news_pool")):
        if not isinstance(item, dict):
            continue

        title = clean_text(item.get("title", ""))
        if not title:
            continue

        action_type = infer_action_type(title)
        if action_type == "综合动作" and not item.get("brand"):
            continue

        brand = clean_text(item.get("brand", "")) or ""
        heat = 35 + (15 if brand else 0) + (20 if action_type != "综合动作" else 0)
        heat += sum(title.count(k) * 5 for keys in ACTION_TYPE_RULES.values() for k in keys if k in title)

        items.append({
            "brand": brand or "行业",
            "title": title,
            "action_type": action_type,
            "track": infer_track_from_text(title),
            "heat": clamp(heat, 1, 100),
            "source": item.get("source", ""),
            "date": item.get("date", ""),
            "insight": build_competitor_action_insight(action_type, infer_track_from_text(title))
        })

    items = sorted(items, key=lambda x: x["heat"], reverse=True)
    return dedupe_by_key(items, "title", limit=20)


def build_competitor_action_insight(action_type, track):
    mapping = {
        "品牌营销": f"关注其对{track}用户心智和内容传播的带动。",
        "商品上新": f"关注其在{track}品类上的功能、价格带和设计语言。",
        "研发科技": "关注其科技话术、研发背书和终端卖点表达方式。",
        "渠道零售": "关注其线下体验、商圈选择和门店陈列打法。",
        "平台流量": "关注其直播货盘、平台流量和内容种草打法。",
        "组织战略": "关注其战略重心和组织调整对后续市场动作的影响。"
    }
    return mapping.get(action_type, "关注其对品牌声量、商品趋势和渠道节奏的影响。")


def build_industry_focus_rule(major_events, weekly_tracks, competitor_actions, keywords, weather):
    focus_counter = Counter()

    for item in safe_list(major_events):
        focus_counter[item.get("event_type", "行业事件")] += to_int(item.get("heat"), 0)

    for item in safe_list(weekly_tracks):
        focus_counter[item.get("track", "综合趋势")] += to_int(item.get("heat"), 0)

    for item in safe_list(competitor_actions):
        focus_counter[item.get("action_type", "综合动作")] += to_int(item.get("heat"), 0)

    for item in safe_list(keywords):
        focus_counter[item.get("word", "")] += to_int(item.get("count", 0)) * 3

    for item in safe_list(weather.get("top_weather_keywords")):
        focus_counter[item.get("word", "")] += to_int(item.get("count", 0)) * 6

    max_score = max(focus_counter.values()) if focus_counter else 1
    result = []

    for name, score in focus_counter.most_common(12):
        if not name:
            continue
        result.append({
            "focus": name,
            "heat": clamp(round(score / max_score * 100), 1, 100),
            "summary": f"{name}是本周较高频关注方向，需结合新闻事实、商品信号和区域变化持续观察。"
        })

    return result[:10]


def build_ai_dynamic_analysis(news, competitor, keywords, regions, weather, product_signals, major_events, weekly_tracks, competitor_actions, industry_focus):
    prompt = f"""
请基于以下真实输入数据，生成361°儿童事业部经营管理部周度行业洞察。
要求：
1. 只输出严格JSON，不要markdown，不要解释。
2. 所有新闻事件必须来自输入数据，不得编造。
3. 不要固定模板，不要固定品牌、人物、品类；本周有什么就总结什么。
4. 如果本周出现具体品牌重大事件，必须在major_events中保留，并写清品牌、事件、类型和影响。
5. 如果某周没有重大品牌事件，就不要硬编，改为提炼商品趋势、天气或平台信号。
6. 语言适合对总经理汇报，不要出现“周总”。

输出JSON结构：
{{
  "weekly_core_view": "80字以内，本周核心观点",
  "news_summary": "100字以内，本周新闻变化",
  "competitor_summary": "100字以内，竞品动作总结",
  "product_summary": "100字以内，商品趋势总结",
  "region_weather_summary": "100字以内，区域和天气总结",
  "next_week_focus": "100字以内，下周重点关注",
  "major_events": [
    {{
      "title": "事件标题，必须来自输入",
      "brand": "品牌或行业",
      "event_type": "代言签约/联名合作/新品发布/研发科技/渠道门店/平台大促/组织管理/资本战略/行业事件",
      "track": "该事件关联的赛道或趋势",
      "heat": 1,
      "impact": "对品牌心智、商品趋势、渠道或内容的影响"
    }}
  ],
  "weekly_tracks": [
    {{
      "track": "本周动态赛道名称",
      "heat": 1,
      "summary": "为什么本周这个赛道值得关注"
    }}
  ],
  "competitor_actions": [
    {{
      "brand": "品牌或行业",
      "title": "动作标题，必须来自输入",
      "action_type": "品牌营销/商品上新/研发科技/渠道零售/平台流量/组织战略/综合动作",
      "track": "关联赛道",
      "heat": 1,
      "insight": "启示"
    }}
  ],
  "industry_focus": [
    {{
      "focus": "本周关注方向",
      "heat": 1,
      "summary": "关注原因"
    }}
  ]
}}

本周TOP新闻：
{json.dumps(news.get("news_pool", [])[-30:], ensure_ascii=False)}

竞品动态：
{json.dumps(competitor.get("pool", [])[-30:], ensure_ascii=False)}

热词：
{json.dumps(keywords[:30], ensure_ascii=False)}

区域：
{json.dumps(regions[:8], ensure_ascii=False)}

天气：
{json.dumps(weather, ensure_ascii=False)}

商品信号：
{json.dumps({
  "top_categories": product_signals.get("top_categories", [])[:12],
  "top_brands": product_signals.get("top_brands", [])[:12],
  "top_keywords": product_signals.get("top_keywords", [])[:12],
  "signals": product_signals.get("signals", [])[:35]
}, ensure_ascii=False)}

规则初筛重大事件：
{json.dumps(major_events[:12], ensure_ascii=False)}

规则初筛动态赛道：
{json.dumps(weekly_tracks[:10], ensure_ascii=False)}

规则初筛竞品动作：
{json.dumps(competitor_actions[:15], ensure_ascii=False)}

规则初筛行业焦点：
{json.dumps(industry_focus[:10], ensure_ascii=False)}
"""

    ai_raw = call_deepseek(prompt, max_tokens=3600)
    obj = extract_json_text(ai_raw)

    if not isinstance(obj, dict):
        return {}

    return obj


def merge_ai_and_rule_lists(ai_list, rule_list, key_name, limit):
    merged = []
    used = set()

    for source in [safe_list(ai_list), safe_list(rule_list)]:
        for item in source:
            if not isinstance(item, dict):
                continue

            key = clean_text(item.get(key_name, ""))
            if not key or key in used:
                continue

            # 统一热度
            item["heat"] = clamp(to_int(item.get("heat", item.get("raw_score", 50)), 50), 1, 100)
            merged.append(item)
            used.add(key)

            if len(merged) >= limit:
                return merged

    return merged


# =========================================================
# 机会 / 风险 / 动作
# =========================================================
def infer_weekly_opportunities(text, keywords, product_signals, weekly_tracks, major_events, industry_focus):
    result = []
    used = set()

    # 优先使用动态赛道
    for track in safe_list(weekly_tracks):
        if not isinstance(track, dict):
            continue

        name = clean_text(track.get("track", ""))
        if not name or name in used:
            continue

        result.append({
            "theme": name,
            "heat": to_int(track.get("heat", 50)),
            "suggestion": track.get("summary") or f"{name}本周热度提升，需关注商品、内容和终端表达。"
        })
        used.add(name)

    # 补充重大事件对应机会
    for event in safe_list(major_events):
        if not isinstance(event, dict):
            continue

        name = clean_text(event.get("track") or event.get("event_type"))
        if not name or name in used or name == "综合趋势":
            continue

        result.append({
            "theme": name,
            "heat": to_int(event.get("heat", 50)),
            "suggestion": event.get("impact") or f"{name}受品牌事件带动，需关注消费者心智变化。"
        })
        used.add(name)

    # 补充行业焦点
    for focus in safe_list(industry_focus):
        if not isinstance(focus, dict):
            continue

        name = clean_text(focus.get("focus", ""))
        if not name or name in used:
            continue

        result.append({
            "theme": name,
            "heat": to_int(focus.get("heat", 50)),
            "suggestion": focus.get("summary") or f"{name}是本周高频关注方向。"
        })
        used.add(name)

    # 没有足够动态内容时，基于商品信号和热词补充
    if len(result) < 4:
        signal_text = json.dumps(product_signals, ensure_ascii=False)
        full_text = text + " " + signal_text + " " + json.dumps(keywords, ensure_ascii=False)

        fallback_rules = [
            ("防晒凉感", ["防晒", "凉感", "速干", "高温", "夏季", "防晒衣"], "防晒衣、凉感T、速干短裤、透气童鞋可作为夏季主推组合。"),
            ("儿童运动", ["儿童", "童装", "童鞋", "儿童运动", "校园", "青少年"], "儿童运动鞋、校园运动鞋、青少年训练鞋需强化成长型和专业运动表达。"),
            ("户外轻运动", ["户外", "轻户外", "露营", "骑行", "文旅", "出行"], "轻户外鞋服、防晒帽包、溯溪鞋和舒适出行鞋具备组合机会。"),
            ("品牌事件", ["签约", "代言", "联名", "实验室", "旗舰店", "开业", "发布"], "品牌重大动作影响消费者心智，需关注竞品声量、产品卖点和传播打法。"),
            ("直播电商", ["直播", "抖音", "小红书", "618", "大促", "店播"], "直播同款、爆款价格带和平台热词款式应沉淀到商品观察。"),
            ("跑鞋科技", ["碳板", "厚底", "缓震", "竞速", "跑鞋", "马拉松", "超临界"], "跑鞋需区分竞速、厚底缓震、校园跑步和日常慢跑场景。")
        ]

        for theme, keys, suggestion in fallback_rules:
            if theme in used:
                continue
            heat = sum(full_text.count(k) for k in keys)
            if heat > 0:
                result.append({"theme": theme, "heat": heat, "suggestion": suggestion})
                used.add(theme)

    result = sorted(result, key=lambda x: to_int(x.get("heat", 0)), reverse=True)
    return result[:10]


def infer_risks(text, product_signals, weekly_tracks, competitor_actions):
    risks = []
    dynamic_text = text + " " + json.dumps(product_signals, ensure_ascii=False)
    dynamic_text += " " + json.dumps(weekly_tracks, ensure_ascii=False)
    dynamic_text += " " + json.dumps(competitor_actions, ensure_ascii=False)

    if text_has(dynamic_text, ["降雨", "暴雨", "强对流", "雷阵雨"]):
        risks.append("天气扰动会影响户外客流，需关注商场内场承接和防滑防雨商品表现。")

    if text_has(dynamic_text, ["大促", "618", "双11", "低价", "价格带"]):
        risks.append("平台大促强化价格心智，线下需关注比价、折扣效率和核心SKU转化。")

    if text_has(dynamic_text, ["消费分层", "理性消费", "客单", "折扣"]):
        risks.append("理性消费和客单压力仍在，商品结构需兼顾功能刚需和价格带效率。")

    if text_has(dynamic_text, ["跑鞋", "跑步科技", "碳板", "厚底"]):
        risks.append("跑鞋科技信息密集，终端若卖点表达不足，容易出现消费者无感知。")

    if text_has(dynamic_text, ["儿童", "童鞋", "校园", "青少年"]):
        risks.append("儿童运动商品竞争加剧，需避免仅做成人款缩小版，应强化成长、校园和安全防护卖点。")

    if len(competitor_actions) >= 6:
        risks.append("竞品动作较密集，需关注热点品类声量被对手抢占的风险。")

    if not risks:
        risks.append("本周风险整体可控，重点关注天气、平台流量、商品同质化和区域客流差异。")

    result = []
    for x in risks:
        if x not in result:
            result.append(x)

    return result[:6]


def build_actions(opportunities, regions, major_events, competitor_actions):
    actions = []
    dynamic_pool = json.dumps(opportunities + major_events + competitor_actions, ensure_ascii=False)

    for opp in opportunities[:6]:
        theme = clean_text(opp.get("theme", ""))

        if text_has(theme, ["儿童", "青少年", "校园"]):
            actions.append("儿童运动方向重点沉淀校园运动、青少年训练、亲子运动和成长型科技卖点。")
        elif text_has(theme, ["品牌", "代言", "签约", "联名"]):
            actions.append("竞品重大事件需沉淀品牌、产品、代言人、渠道动作和可借鉴打法。")
        elif text_has(theme, ["户外", "文旅", "出行"]):
            actions.append("轻户外方向跟踪防晒、溯溪、户外鞋服、帽包配件和亲子出行组合。")
        elif text_has(theme, ["防晒", "凉感", "速干"]):
            actions.append("防晒凉感方向继续跟踪防晒衣、凉感T、速干短裤、运动凉鞋和帽包。")
        elif text_has(theme, ["直播", "大促", "平台"]):
            actions.append("平台内容方向关注直播同款、达人种草、价格带和爆款货盘变化。")
        elif text_has(theme, ["跑鞋", "跑步", "碳板", "缓震"]):
            actions.append("跑鞋方向区分竞速、缓震、训练、校园跑和日常通勤场景。")
        else:
            actions.append(f"{theme}方向需继续跟踪新闻事实、竞品动作和商品信号，沉淀周报输入。")

    if text_has(dynamic_pool, ["研发科技", "实验室", "创新中心", "科技"]):
        actions.append("科技研发类事件需同步拆解竞品卖点话术，转化为儿童商品可表达的功能语言。")

    if regions:
        actions.append("区域部分按周更新，不使用固定区域结论，重点看天气、客流和区域机会变化。")

    actions.append("每周复盘高频新闻、竞品动作、商品信号和热词，形成下周汇报输入。")

    result = []
    for x in actions:
        if x not in result:
            result.append(x)

    return result[:7]


def build_product_suggestions(opportunities, product_signals, weekly_tracks):
    suggestions = []

    text = (
        json.dumps(opportunities, ensure_ascii=False)
        + json.dumps(product_signals, ensure_ascii=False)
        + json.dumps(weekly_tracks, ensure_ascii=False)
    )

    if text_has(text, ["儿童", "青少年", "校园"]):
        suggestions.append("青少年跑鞋、篮球鞋、训练鞋可强化成人化设计表达和科技感。")

    if text_has(text, ["防晒", "凉感", "速干"]):
        suggestions.append("防晒衣、凉感T恤、速干短裤、运动凉鞋、防晒帽包仍是夏季重点。")

    if text_has(text, ["户外", "冲锋衣", "防水", "山系", "溯溪"]):
        suggestions.append("轻户外鞋服、冲锋衣、防水外套、溯溪鞋和户外鞋值得持续跟踪。")

    if text_has(text, ["碳板", "厚底", "跑鞋", "缓震"]):
        suggestions.append("跑鞋矩阵需区分碳板竞速、厚底缓震、轻量训练和校园跑步。")

    if text_has(text, ["篮球", "篮球鞋"]):
        suggestions.append("篮球方向需关注校园篮球、中大童训练和专业篮球鞋科技表达。")

    if text_has(text, ["凉鞋", "拖鞋", "恢复拖鞋"]):
        suggestions.append("夏季鞋类可关注运动凉鞋、恢复拖鞋、轻便洞洞鞋和亲子出行场景。")

    if not suggestions:
        suggestions = [
            "增加青少年跑鞋、篮球鞋、训练服的成人化设计表达。",
            "强化防晒衣、凉感T恤、速干短裤、运动凉鞋组合。",
            "补充轻户外鞋服、帽包配件、亲子同款和校园运动套装。"
        ]

    result = []
    for x in suggestions:
        if x not in result:
            result.append(x)

    return result[:6]


# =========================================================
# 汇总判断
# =========================================================
def build_summary(days, news, competitor_news, keywords, regions, weather, product_signals, opportunities, major_events, weekly_tracks):
    dates = [d.get("date", "") for d in days if d.get("date")]
    date_range = f"{dates[0]} 至 {dates[-1]}" if dates else ""

    top_words = "、".join([x["word"] for x in keywords[:6]]) or "品牌事件、平台流量、商品趋势"
    top_news_tags = "、".join([x["tag"] for x in news.get("top_tags", [])[:4]]) or "品牌竞争、平台流量、天气消费"
    top_brands = "、".join([x["brand"] for x in competitor_news.get("top_brands", [])[:5]]) or "重点品牌"
    top_opps = "、".join([x["theme"] for x in opportunities[:3]]) or "儿童运动、防晒凉感、品牌事件"
    top_tracks = "、".join([x["track"] for x in weekly_tracks[:3]]) or top_opps
    top_events = "、".join([x["title"] for x in major_events[:3]]) or "无明显单一重大事件"
    region_names = "、".join([x.get("region", "") for x in regions[:4]]) or "重点区域"
    weather_words = "、".join([x["word"] for x in weather.get("top_weather_keywords", [])[:4]]) or "天气扰动"

    return {
        "date_range": date_range,
        "core_judgement": f"本周行业信息集中在{top_news_tags}，高频热词为{top_words}，动态赛道主要为{top_tracks}。",
        "news_direction": f"本周重点事件包括{top_events}，新闻侧需关注其对品牌心智、商品卖点和内容声量的影响。",
        "competitor_direction": f"竞品动态主要围绕{top_brands}展开，需关注品牌营销、商品上新、研发科技和平台流量动作。",
        "product_direction": f"商品侧建议关注{top_opps}，并结合商品信号判断儿童运动、季节功能和场景化方向。",
        "regional_direction": f"区域侧重点关注{region_names}，天气关键词集中在{weather_words}，需结合区域客流变化理解机会。",
        "next_action": f"下周建议围绕{top_tracks}持续跟踪竞品事件、商品信号、天气变化和平台热词，形成汇报页输入。"
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

    # 规则层：先完全基于本周数据抽取，不写死具体事件
    major_events_rule = build_major_events_rule(news, competitor, product_signals, keywords)
    weekly_tracks_rule = build_weekly_tracks_rule(text, keywords, product_signals, news, competitor)
    competitor_actions_rule = build_competitor_actions_rule(competitor, news)
    industry_focus_rule = build_industry_focus_rule(major_events_rule, weekly_tracks_rule, competitor_actions_rule, keywords, weather)

    # AI层：让AI基于本周事实二次归纳，仍然要求不得编造
    ai_dynamic = build_ai_dynamic_analysis(
        news=news,
        competitor=competitor,
        keywords=keywords,
        regions=regions,
        weather=weather,
        product_signals=product_signals,
        major_events=major_events_rule,
        weekly_tracks=weekly_tracks_rule,
        competitor_actions=competitor_actions_rule,
        industry_focus=industry_focus_rule
    )

    major_events = merge_ai_and_rule_lists(
        ai_dynamic.get("major_events", []),
        major_events_rule,
        key_name="title",
        limit=12
    )

    weekly_tracks = merge_ai_and_rule_lists(
        ai_dynamic.get("weekly_tracks", []),
        weekly_tracks_rule,
        key_name="track",
        limit=10
    )

    competitor_actions = merge_ai_and_rule_lists(
        ai_dynamic.get("competitor_actions", []),
        competitor_actions_rule,
        key_name="title",
        limit=18
    )

    industry_focus = merge_ai_and_rule_lists(
        ai_dynamic.get("industry_focus", []),
        industry_focus_rule,
        key_name="focus",
        limit=12
    )

    opportunities = infer_weekly_opportunities(
        text=text,
        keywords=keywords,
        product_signals=product_signals,
        weekly_tracks=weekly_tracks,
        major_events=major_events,
        industry_focus=industry_focus
    )

    risks = infer_risks(text, product_signals, weekly_tracks, competitor_actions)
    actions = build_actions(opportunities, regions, major_events, competitor_actions)
    product_suggestions = build_product_suggestions(opportunities, product_signals, weekly_tracks)

    summary = build_summary(
        days=days,
        news=news,
        competitor_news=competitor,
        keywords=keywords,
        regions=regions,
        weather=weather,
        product_signals=product_signals,
        opportunities=opportunities,
        major_events=major_events,
        weekly_tracks=weekly_tracks
    )

    ai_judgement = {
        "weekly_core_view": ai_dynamic.get("weekly_core_view") or summary.get("core_judgement", ""),
        "news_summary": ai_dynamic.get("news_summary") or summary.get("news_direction", ""),
        "competitor_summary": ai_dynamic.get("competitor_summary") or summary.get("competitor_direction", ""),
        "product_summary": ai_dynamic.get("product_summary") or summary.get("product_direction", ""),
        "region_weather_summary": ai_dynamic.get("region_weather_summary") or summary.get("regional_direction", ""),
        "next_week_focus": ai_dynamic.get("next_week_focus") or summary.get("next_action", "")
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

        # 新增动态分析层
        "major_events": major_events,
        "weekly_tracks": weekly_tracks,
        "competitor_actions": competitor_actions,
        "industry_focus": industry_focus,

        # 兼容原HTML字段
        "opportunities": opportunities,
        "risks": risks,
        "actions": actions,
        "product_suggestions": product_suggestions,

        # 调试用，便于看AI有没有生效
        "debug": {
            "days_loaded": len(days),
            "news_count": len(news.get("news_pool", [])),
            "competitor_count": len(competitor.get("pool", [])),
            "major_events_rule_count": len(major_events_rule),
            "weekly_tracks_rule_count": len(weekly_tracks_rule),
            "competitor_actions_rule_count": len(competitor_actions_rule),
            "ai_dynamic_used": bool(ai_dynamic)
        }
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"weekly analysis saved: {OUTPUT_FILE}")
    print(f"days loaded: {len(days)}")
    print(f"news count: {len(news.get('news_pool', []))}")
    print(f"competitor count: {len(competitor.get('pool', []))}")
    print(f"major events: {len(major_events)}")
    print(f"weekly tracks: {len(weekly_tracks)}")
    print(f"competitor actions: {len(competitor_actions)}")
    print(f"ai dynamic used: {bool(ai_dynamic)}")


if __name__ == "__main__":
    main()
