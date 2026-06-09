from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import json
import re

WEEKLY_DIR = Path("output/weekly")
ANALYSIS_FILE = WEEKLY_DIR / "weekly_analysis.json"
OUTPUT_FILE = WEEKLY_DIR / "weekly_topics.json"

WEEKLY_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load json error: {path} {e}")
        return default


def safe_list(v):
    return v if isinstance(v, list) else []


def raw(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ").strip())


def to_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


TOPIC_RULES = {
    "品牌重大事件": ["签约", "代言", "联名", "战略合作", "旗舰店", "开业", "实验室", "创新中心", "发布", "新品"],
    "商品趋势机会": ["防晒", "凉感", "速干", "拖鞋", "凉鞋", "跑鞋", "篮球", "户外", "冲锋衣", "童鞋"],
    "平台与内容流量": ["618", "大促", "直播", "抖音", "小红书", "种草", "店播", "达人"],
    "儿童运动专题": ["儿童", "童装", "童鞋", "青少年", "校园", "亲子", "Kids", "KIDS"],
    "区域天气影响": ["高温", "降雨", "暴雨", "强对流", "防雨", "防滑", "保暖", "低温"],
    "运动赛道变化": ["篮球", "跑步", "马拉松", "足球", "户外", "骑行", "训练", "赛事"],
}


BRAND_WORDS = [
    "安踏", "安踏儿童", "李宁", "李宁YOUNG", "361", "361度", "361儿童",
    "特步", "特步儿童", "Nike", "耐克", "Adidas", "阿迪", "阿迪达斯",
    "FILA", "FILA KIDS", "巴拉巴拉", "Puma", "彪马", "HOKA", "昂跑",
    "On", "亚瑟士", "ASICS"
]


def infer_topic(text):
    scores = Counter()

    for topic, keys in TOPIC_RULES.items():
        for k in keys:
            if k in text:
                scores[topic] += text.count(k)

    if not scores:
        return "综合行业观察"

    return scores.most_common(1)[0][0]


def infer_brand(text):
    hits = []
    for b in BRAND_WORDS:
        if b in text and b not in hits:
            hits.append(b)
    return hits[:3]


def infer_impact(topic, text):
    if topic == "品牌重大事件":
        return "品牌声量与专业心智竞争升温，需关注竞品传播打法、产品背书和渠道承接。"
    if topic == "商品趋势机会":
        return "商品机会从单一品类转向场景组合，功能卖点和终端表达重要性提升。"
    if topic == "平台与内容流量":
        return "平台大促与内容种草强化价格和爆款心智，线上热词可能外溢到线下。"
    if topic == "儿童运动专题":
        return "儿童运动消费继续向专业化、校园化和亲子场景扩展。"
    if topic == "区域天气影响":
        return "天气变化影响客流节奏和品类需求，区域陈列和主推节奏需动态调整。"
    if topic == "运动赛道变化":
        return "运动场景更加细分，篮球、跑步、户外等赛道均需要独立跟踪。"
    return "本周行业信息分散，需继续跟踪高频事件、品牌动作和商品趋势变化。"


def infer_action(topic, text):
    if topic == "品牌重大事件":
        return "下周重点沉淀竞品事件清单，拆解品牌、代言人、产品、渠道和传播打法。"
    if topic == "商品趋势机会":
        return "下周重点跟踪高热品类，将防晒凉感、恢复拖鞋、篮球跑鞋等纳入商品观察。"
    if topic == "平台与内容流量":
        return "下周关注直播同款、平台爆款、价格带和搜索热词变化。"
    if topic == "儿童运动专题":
        return "下周重点关注青少年运动、校园体育、亲子运动和儿童专业科技表达。"
    if topic == "区域天气影响":
        return "下周按区域跟踪高温、降雨和强对流变化，动态调整品类和陈列建议。"
    if topic == "运动赛道变化":
        return "下周按篮球、跑步、户外、训练等赛道拆分跟踪品牌动作和商品机会。"
    return "下周继续跟踪新闻事实、商品信号、区域天气和平台热词。"


def collect_items(data):
    items = []

    news = data.get("news", {})
    competitor_news = data.get("competitor_news", {})
    product_signals = data.get("product_signals", {})
    weather = data.get("weather", {})
    keywords = data.get("keywords", [])

    for x in safe_list(news.get("news_pool")):
        if isinstance(x, dict):
            title = raw(x.get("title"))
            if title:
                items.append({
                    "type": "news",
                    "title": title,
                    "source": raw(x.get("source")),
                    "date": raw(x.get("date")),
                    "score": 5,
                    "brand": infer_brand(title),
                    "raw": x
                })

    for x in safe_list(competitor_news.get("pool")):
        if isinstance(x, dict):
            title = raw(x.get("title"))
            if title:
                items.append({
                    "type": "competitor",
                    "title": title,
                    "source": raw(x.get("source")),
                    "date": raw(x.get("date")),
                    "score": 8,
                    "brand": infer_brand(title) or [raw(x.get("brand"))],
                    "raw": x
                })

    for x in safe_list(product_signals.get("signals")):
        if isinstance(x, dict):
            title = raw(x.get("short_title") or x.get("title"))
            if title:
                heat = to_int(x.get("heat"), 1)
                text = " ".join([
                    title,
                    raw(x.get("category")),
                    " ".join(safe_list(x.get("keyword_hits"))),
                    " ".join(safe_list(x.get("brand_hits"))),
                ])
                items.append({
                    "type": "product_signal",
                    "title": title,
                    "source": raw(x.get("source")),
                    "date": raw(product_signals.get("date")),
                    "score": max(3, heat),
                    "brand": safe_list(x.get("brand_hits")) or infer_brand(text),
                    "raw": x
                })

    for x in safe_list(keywords):
        if isinstance(x, dict):
            word = raw(x.get("word") or x.get("keyword"))
            count = to_int(x.get("count"), 1)
            if word:
                items.append({
                    "type": "keyword",
                    "title": word,
                    "source": "周度热词",
                    "date": "",
                    "score": count,
                    "brand": infer_brand(word),
                    "raw": x
                })

    if isinstance(weather, dict):
        for x in safe_list(weather.get("pool")):
            if isinstance(x, dict):
                desc = raw(x.get("desc"))
                region = raw(x.get("region"))
                if desc:
                    items.append({
                        "type": "weather",
                        "title": f"{region}｜{desc}",
                        "source": "天气信号",
                        "date": raw(x.get("date")),
                        "score": 4,
                        "brand": [],
                        "raw": x
                    })

    return items


def build_clusters(items):
    clusters = defaultdict(list)

    for item in items:
        text = " ".join([
            raw(item.get("title")),
            json.dumps(item.get("raw", {}), ensure_ascii=False)
        ])
        topic = infer_topic(text)
        item["topic"] = topic
        clusters[topic].append(item)

    result = []

    for topic, arr in clusters.items():
        total_heat = sum(to_int(x.get("score")) for x in arr)
        brand_counter = Counter()

        for x in arr:
            for b in safe_list(x.get("brand")):
                if b:
                    brand_counter[b] += 1

        sorted_items = sorted(
            arr,
            key=lambda x: to_int(x.get("score")),
            reverse=True
        )

        combined_text = " ".join([x["title"] for x in sorted_items[:10]])

        result.append({
            "topic": topic,
            "heat": total_heat,
            "item_count": len(arr),
            "top_brands": [
                {"brand": k, "count": v}
                for k, v in brand_counter.most_common(6)
            ],
            "representative_events": [
                {
                    "title": x.get("title", ""),
                    "type": x.get("type", ""),
                    "source": x.get("source", ""),
                    "date": x.get("date", ""),
                    "score": x.get("score", 0),
                    "brand": x.get("brand", [])
                }
                for x in sorted_items[:8]
            ],
            "impact": infer_impact(topic, combined_text),
            "action": infer_action(topic, combined_text)
        })

    return sorted(result, key=lambda x: x["heat"], reverse=True)


def build_overall_view(clusters):
    if not clusters:
        return {
            "core_view": "本周行业信息样本不足，建议继续积累日报历史数据。",
            "top_topics": [],
            "next_focus": "继续跟踪品牌事件、商品趋势、平台流量和区域天气。"
        }

    top_topics = [x["topic"] for x in clusters[:4]]
    top_text = "、".join(top_topics)

    return {
        "core_view": f"本周行业热点主要集中在{top_text}，内容由周度新闻、竞品动态、商品信号和天气变化共同驱动。",
        "top_topics": top_topics,
        "next_focus": "下周重点关注高热主题是否延续，并同步观察竞品动作、商品开发机会和区域承接变化。"
    }


def main():
    data = load_json(ANALYSIS_FILE, {})
    if not data:
        print(f"weekly_analysis.json not found: {ANALYSIS_FILE}")
        return

    items = collect_items(data)
    clusters = build_clusters(items)
    overall = build_overall_view(clusters)

    output = {
        "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_file": str(ANALYSIS_FILE),
        "overall": overall,
        "topics": clusters,
        "raw_item_count": len(items)
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"weekly topics saved: {OUTPUT_FILE}")
    print(f"raw items: {len(items)}")
    print(f"topics: {len(clusters)}")


if __name__ == "__main__":
    main()
