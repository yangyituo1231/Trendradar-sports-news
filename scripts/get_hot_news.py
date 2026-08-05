import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from collections import defaultdict, Counter


# =========================================================
# 0. 基础配置
# =========================================================

MAX_ITEMS = 200

RSS_PER_QUERY_LIMIT = 10

RECENT_DAYS = 7


WEEKLY_DIR = Path("output/weekly")
WEEKLY_FILE = WEEKLY_DIR / "weekly_news.json"


DAILY_DIR = Path("output/news")
DAILY_FILE = DAILY_DIR / "latest.json"


NOW = datetime.now()

NOW_UTC = datetime.now(timezone.utc)



# =========================================================
# 1. 新闻分类体系
# =========================================================

CATEGORY = {

    "industry":
        "鞋服行业",

    "ecommerce":
        "电商平台",

    "brand":
        "品牌动态",

    "kids":
        "儿童市场",

    "report":
        "行业报告",

    "macro":
        "宏观消费",

    "sport":
        "运动场景",

    "technology":
        "科技趋势"

}



# =========================================================
# 2. 新闻搜索关键词
# =========================================================


QUERY_GROUPS = {


"brand":[

    "Nike 品牌战略",

    "Adidas 品牌战略",

    "安踏 集团 战略",

    "李宁 品牌战略",

    "特步 集团 动态",

    "361度 品牌动态",

    "lululemon 中国",

    "HOKA 品牌动态",

    "On昂跑 中国",

    "Salomon 户外品牌",

    "迪卡侬 中国"

],


"retail":[

    "运动品牌 门店 调整",

    "购物中心 运动品牌",

    "奥莱 运动品牌",

    "零售业态 创新",

    "体验式零售",

    "会员零售",

    "品牌旗舰店",

    "新零售 模式"

],


"product":[

    "跑鞋 科技 趋势",

    "户外鞋服 趋势",

    "越野跑 市场",

    "运动装备 新品",

    "功能服饰 趋势",

    "运动科技 材料",

    "智能穿戴 运动"

],


"consumer":[

    "运动消费 趋势",

    "年轻消费者 消费趋势",

    "户外消费 增长",

    "体育消费 市场",

    "儿童运动 消费",

    "亲子消费 趋势",

    "健康消费 趋势"

],


"ecommerce":[

    "天猫 运动行业",

    "京东运动 消费",

    "抖音电商 运动",

    "小红书 运动消费",

    "得物 球鞋市场",

    "直播电商 运动品牌"

],


"marketing":[

    "运动品牌 联名",

    "体育赛事 营销",

    "世界杯 品牌营销",

    "奥运 品牌营销",

    "明星代言 运动品牌",

    "IP合作 运动品牌"
    "运动品牌 财报",
    "运动品牌 毛利率",
    "运动品牌 渠道",
    "运动品牌 门店",
    "运动品牌 库存",
    "运动品牌 出海",
    "运动品牌 中国市场"
    

],


"report":[

    "运动行业 报告",

    "体育消费 白皮书",

    "鞋服行业 数据",

    "零售行业 报告",

    "消费者洞察"

],


"technology":[

    "AI 零售",

    "人工智能 品牌",

    "数字化 门店",

    "智能制造 鞋服",

    "运动科技"

]


}



KEYWORDS = []

for group in QUERY_GROUPS.values():

    KEYWORDS.extend(group)



# =========================================================
# 3. 品牌词库
# =========================================================

BRANDS = [

    "安踏",
    "安踏儿童",

    "李宁",
    "李宁YOUNG",

    "361",
    "361度",
    "361儿童",

    "特步",
    "特步儿童",

    "Nike",
    "耐克",

    "Adidas",
    "阿迪达斯",

    "Puma",
    "彪马",

    "FILA",
    "FILA KIDS",

    "HOKA",

    "On",
    "昂跑",

    "ASICS",
    "亚瑟士",

    "lululemon",

    "New Balance",

    "巴拉巴拉",

]



# =========================================================
# 4. 行业关键词
# =========================================================


REPORT_WORDS = [

    "报告",

    "白皮书",

    "调研",

    "调查",

    "指数",

    "洞察",

    "市场规模",

    "消费者",

    "研究"

]



ECOMMERCE_WORDS = [

    "天猫",

    "淘宝",

    "京东",

    "抖音",

    "小红书",

    "唯品会",

    "得物",

    "直播",

    "店播",

]



BRAND_EVENT_WORDS = [

    "战略合作",

    "签约",

    "代言",

    "联名",

    "新品",

    "发布",

    "旗舰店",

    "开业",

    "实验室",

    "科技",

    "收购",

]



CONSUMPTION_WORDS = [

    "消费",

    "零售",

    "客流",

    "增长",

    "下滑",

    "市场",

    "渠道",

    "趋势",

]



BAD_WORDS = [

    "彩票",

    "博彩",

    "下注",

    "赌球",

    "成人用品",

    "股票",

    "涨停",

    "跌停",

    "龙虎榜",

    "优惠券",

    "折扣",

    "满减",

    "促销",

    "怎么买",

    "推荐购买",

    "哪个品牌好",

    "排行榜",

    "测评",

    "招商加盟",

    "加盟代理",

    "招聘",

    "直播间",

    "优惠活动"

]



SPORT_EVENT_WORDS = [

    "比分",

    "赛程",

    "冠军",

    "夺冠",

    "转会",

    "球员",

    "球队",

]



# =========================================================
# 5. 来源权重
# =========================================================


SOURCE_SCORE = {


    "国家统计局":20,

    "商务部":20,

    "新华网":12,

    "人民网":12,

    "央视":12,


    "第一财经":10,

    "界面新闻":10,

    "36氪":10,

    "赢商网":10,

    "联商网":10,

    "亿邦动力":10,

    "电商报":8,

    "品牌星球":8,


    "搜狐":-5,

    "百家号":-10,

    "财富号":-10,

}
# =========================================================
# 6. 文本处理
# =========================================================


def clean_text(text):

    text = re.sub(
        r"<[^>]+>",
        "",
        text or ""
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()



def normalize_title(title):

    title = clean_text(title)

    title = re.sub(
        r"\s*-\s*.*?$",
        "",
        title
    )

    title = re.sub(
        r"\|.*?$",
        "",
        title
    )

    return title.strip()



def contain_any(text, words):

    return any(
        w in text
        for w in words
    )



# =========================================================
# 7. 时间处理
# =========================================================


def parse_time(value):

    if not value:
        return None

    try:

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except:

        return None



def age_hours(item):

    dt = parse_time(
        item.get(
            "published_at",
            ""
        )
    )

    if not dt:

        return 9999


    return (
        NOW_UTC - dt
    ).total_seconds()/3600



def freshness_score(item):

    h = age_hours(item)


    if h <= 12:
        return 40

    if h <= 24:
        return 30

    if h <= 72:
        return 20

    if h <= 120:
        return 10

    return 0



# =========================================================
# 8. 新闻过滤
# =========================================================


def is_bad_news(title):


    if len(title)<8:

        return True


    LOW_VALUE_WORDS=[

        "加盟代理",
        "招商加盟",
        "优惠券",
        "怎么买",
        "推荐",
        "测评",
        "排行榜",
        "哪个好",
        "值得买"

    ]


    if contain_any(
        title,
        LOW_VALUE_WORDS
    ):

        return True



    if contain_any(
        title,
        BAD_WORDS
    ):

        return True



    return False



# =========================================================
# 9. RSS抓取
# =========================================================


def fetch_news(keyword):


    query = urllib.parse.quote(

        f"{keyword} when:{RECENT_DAYS}d"

    )


    url = (

        "https://news.google.com/rss/search?q="

        + query

        +
        "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

    )


    request = urllib.request.Request(

        url,

        headers={

            "User-Agent":

            "Mozilla/5.0"

        }

    )



    try:


        with urllib.request.urlopen(

            request,

            timeout=15

        ) as response:


            xml = response.read()



        root = ET.fromstring(xml)



    except Exception:


        return []



    result=[]


    for node in root.findall(".//item"):


        title = normalize_title(

            node.findtext("title")

        )


        if is_bad_news(title):

            continue



        source="Google"



        source_node=node.find("source")


        if source_node is not None:

            source = clean_text(

                source_node.text

            )



        row={


            "title":title,


            "source":source,


            "url":
                clean_text(
                    node.findtext("link")
                ),


            "published_at":
                clean_text(
                    node.findtext("pubDate")
                ),

        }



        if age_hours(row)>RECENT_DAYS*24:

            continue



        result.append(row)



        if len(result)>=RSS_PER_QUERY_LIMIT:

            break



    return result





# =========================================================
# 10. 分类判断
# =========================================================


def detect_category(title):


    if contain_any(
        title,
        REPORT_WORDS
    ):

        return "report"



    if contain_any(
        title,
        ECOMMERCE_WORDS
    ):

        return "ecommerce"



    if contain_any(
        title,
        BRAND_EVENT_WORDS
    ) and contain_any(
        title,
        BRANDS
    ):

        return "brand"



    if contain_any(
        title,
        [
            "儿童",
            "童装",
            "亲子",
            "青少年"
        ]
    ):

        return "kids"



    if contain_any(
        title,
        [
            "政策",
            "社零",
            "收入",
            "消费信心",
            "内需"
        ]
    ):

        return "macro"



    if contain_any(
        title,
        [
            "AI",
            "人工智能",
            "科技",
            "智能"
        ]
    ):

        return "technology"



    if contain_any(
        title,
        [
            "跑步",
            "户外",
            "骑行",
            "露营"
        ]
    ):

        return "sport"



    return "industry"





# =========================================================
# 11. 新闻评分
# =========================================================


def score_news(item):


    title=item["title"]


    score=0



    # 新鲜度

    score += freshness_score(item)



    # 来源

    for k,v in SOURCE_SCORE.items():

        if k in item["source"]:

            score += v



    category=detect_category(title)


    item["category"]=category



    # 行业价值

    if category=="industry":

        score += 20



    if category=="report":

        score += 35



    if category=="macro":

        score += 30



    if category=="ecommerce":

        score += 25



    if category=="brand":

        score += 25



    if category=="kids":

        score += 15



    # 品牌事件

    if contain_any(
        title,
        [
            "战略合作",
            "联名",
            "新品",
            "实验室",
            "发布"
        ]
    ):

        score += 20
    if contain_any(
        title,
        [
            "财报",
            "营收",
            "增长",
            "战略",
            "渠道",
            "门店",
            "供应链",
            "管理层"
        ]
    ):

        score +=25



    # 数据型新闻

    if contain_any(
        title,
        [
            "增长",
            "规模",
            "市场",
            "报告",
            "数据",
            "调研"
        ]
    ):

        score += 20



    # 降低营销软文

    if contain_any(
        title,
        [
            "推荐",
            "测评",
            "哪个牌子",
            "排行榜"
        ]
    ):

        score -= 40



    item["score"]=score



    return item




# =========================================================
# 12. 去重
# =========================================================


def topic_key(title):


    title=normalize_title(title)


    words=[]


    for w in [

        "安踏",
        "李宁",
        "Nike",
        "阿迪",
        "361",
        "特步",

        "618",

        "抖音",

        "天猫",

        "儿童",

        "童装",

        "消费",

        "报告",

        "AI",

        "户外",

        "跑步"

    ]:

        if w in title:

            words.append(w)



    if words:

        return "_".join(words[:3])


    return title[:20]




def deduplicate(items):

    best={}

    for item in items:

        key=item.get("title","")

        if not key:
            continue


        old=best.get(key)


        if old is None:

            best[key]=item

        else:

            if item.get("score",0) > old.get("score",0):

                best[key]=item


    return list(best.values())

# =========================================================
# 13. 输出结构
# =========================================================

# =========================================================
# TOP新闻筛选
# 防止单一品牌/单一事件霸屏
# =========================================================

def select_top_news(items, limit=10):


    result=[]

    brand_count=defaultdict(int)

    category_count=defaultdict(int)


    for item in items:


        title=item.get(
            "title",
            ""
        )


        category=item.get(
            "category",
            "industry"
        )


        brand=""

        for b in BRANDS:

            if b in title:

                brand=b

                break



        # 同品牌最多3条

        if brand:

            if brand_count[brand]>=3:

                continue



        # 同类别最多4条

        if category_count[category]>=4:

            continue



        result.append(item)



        if brand:

            brand_count[brand]+=1


        category_count[category]+=1



        if len(result)>=limit:

            break



    return result
    
def build_output(items):


    items = sorted(

        items,

        key=lambda x:

            x.get(
                "score",
                0
            ),

        reverse=True

    )


    top_news = select_top_news(
        items,
        10
    )



    result={

        "generated_at":

            NOW.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),


        "total":

            len(items),


        "news":

            items[:120]

    }



    # -------------------------
    # 分类
    # -------------------------

    categories={

        "industry":[],

        "brand":[],

        "ecommerce":[],

        "report":[],

        "macro":[],

        "kids":[],

        "technology":[],

        "sport":[],

    }



    for item in items:


        cat=item.get(
            "category",
            "industry"
        )


        if cat in categories:

            categories[cat].append(item)



    result["categories"]=categories



    # -------------------------
    # TOP资讯
    # -------------------------

    result["top_news"]=top_news



    # -------------------------
    # 品牌动态
    # -------------------------

    result["brand_news"]=categories["brand"][:8]



    # -------------------------
    # 电商动态
    # -------------------------

    result["ecommerce_news"]=categories["ecommerce"][:8]



    # -------------------------
    # 行业报告
    # -------------------------

    result["report_news"]=categories["report"][:8]



    # -------------------------
    # 宏观消费
    # -------------------------

    result["macro_news"]=categories["macro"][:8]



    # -------------------------
    # 儿童运动
    # -------------------------

    result["kids_news"]=categories["kids"][:8]



    return result





# =========================================================
# 14. 热词
# =========================================================


def build_keywords(items):


    counter=Counter()


    for item in items:


        title=item.get(
            "title",
            ""
        )


        for word in [

            "运动消费",

            "儿童运动",

            "童装",

            "跑鞋",

            "户外",

            "露营",

            "骑行",

            "防晒",

            "凉感",

            "速干",

            "AI",

            "人工智能",

            "消费趋势",

            "社零",

            "消费信心",

            "年轻人",

            "文旅",

            "商圈",

            "会员",

            "直播",

            "抖音",

            "小红书",

            "新品",

            "联名",

            "科技",

            "可持续",

            "出海",

            "渠道",

        ]:


            if word in title:

                counter[word]+=1



    return [

        x[0]

        for x in counter.most_common(18)

    ]






# =========================================================
# 15. 主程序
# =========================================================


def main():


    all_items=[]


    print(
        "开始抓取行业资讯..."
    )



    for idx,keyword in enumerate(
        KEYWORDS,
        start=1
    ):


        try:


            rows=fetch_news(
                keyword
            )


            all_items.extend(
                rows
            )


            print(

                f"{idx}/{len(KEYWORDS)} "

                f"{keyword}"

                f" -> {len(rows)}"

            )


            time.sleep(
                0.3
            )



        except Exception as e:


            print(

                "error:",
                keyword,
                e

            )



    print(

        "raw:",
        len(all_items)

    )



    # 去重

    items=deduplicate(
        all_items
    )



    # 评分

    items=[

        score_news(x)

        for x in items

    ]



    items=sorted(

        items,

        key=lambda x:

            x["score"],

        reverse=True

    )



    # 输出

    payload=build_output(
        items
    )


    payload["keywords"]=build_keywords(
        items
    )




    WEEKLY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    DAILY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2
    )


    WEEKLY_FILE.write_text(
        content,
        encoding="utf-8" 
    )


    DAILY_FILE.write_text(
        content,
        encoding="utf-8"
    )


    print(
        "saved:",
        OUT_FILE
    )



    print(
        "\nTOP NEWS:"
    )


    for i,x in enumerate(

        payload["top_news"][:10],

        start=1

    ):

        print(

            i,

            x["score"],

            x["title"]

        )




if __name__=="__main__":

    main()
