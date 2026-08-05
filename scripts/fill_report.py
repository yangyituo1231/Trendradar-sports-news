from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from collections import Counter
import json
import os
import re


# ======================================================
# 文件路径
# ======================================================

TEMPLATE_FILE = Path("daily-report.html")

OUTPUT_HTML = Path(
    "daily-report-filled.html"
)

NEWS_FILE = Path(
    "output/news/latest.json"
)

WEEKLY_NEWS_FILE = Path(
    "output/weekly/weekly_news.json"
)

TOP_NEWS_FILE = Path(
    "output/news/top_news.json"
)

COMPETITOR_FILE = Path(
    "output/news/competitor_news.json"
)


today = datetime.now()

weekday_map = {
    0:"星期一",
    1:"星期二",
    2:"星期三",
    3:"星期四",
    4:"星期五",
    5:"星期六",
    6:"星期日"
}


# ======================================================
# 基础函数
# ======================================================


def clean_title(text):

    text = str(text or "")

    text = text.replace("\n"," ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = re.sub(
        r"[-|].*$",
        "",
        text
    )

    return text.strip()



def short(text, length=45):

    text = clean_title(text)

    if len(text) > length:
        return text[:length]+"..."

    return text



def parse_time(item):

    value = (
        item.get("published_at")
        or item.get("pubDate")
        or item.get("date")
        or item.get("time")
        or ""
    )

    if not value:
        return 0

    try:
        return parsedate_to_datetime(
            value
        ).timestamp()

    except:

        return 0



# ======================================================
# 新闻读取
# ======================================================


def load_news():

    file = (
        WEEKLY_NEWS_FILE
        if WEEKLY_NEWS_FILE.exists()
        else NEWS_FILE
    )


    if not file.exists():

        return []


    try:

        raw = json.loads(
            file.read_text(
                encoding="utf-8"
            )
        )


    except Exception as e:

        print(
            "load news error",
            e
        )

        return []



    if isinstance(raw,dict):

        if "levels" in raw:

            result=[]

            for level in [
                "A",
                "B",
                "C"
            ]:

                result.extend(
                    raw.get(
                        "levels",
                        {}
                    )
                    .get(
                        level,
                        {}
                    )
                    .get(
                        "items",
                        []
                    )
                )

            return result


        return raw.get(
            "items",
            []
        )


    return raw



news_items = load_news()



# 去除过旧新闻

filtered=[]


for item in news_items:


    if not isinstance(item,dict):

        continue


    ts=parse_time(item)


    if ts:

        days=(
            today.timestamp()
            -
            ts
        )/86400


        if days>45:

            continue



    filtered.append(item)



news_items=filtered



titles=[
    clean_title(
        x.get("title","")
    )

    for x in news_items
    if x.get("title")
]


joined_news=" ".join(
    titles
)



print(
    "news count:",
    len(news_items)
)



# ======================================================
# DeepSeek
# ======================================================


def get_client():

    key=os.getenv(
        "DEEPSEEK_API_KEY"
    )


    if not key:

        return None


    try:

        from openai import OpenAI

        return OpenAI(
            api_key=key,
            base_url=
            "https://api.deepseek.com"
        )

    except:

        return None




def extract_json(text):

    if not text:

        return None


    text=text.strip()


    text=text.replace(
        "```json",
        ""
    )

    text=text.replace(
        "```",
        ""
    )


    try:

        return json.loads(text)

    except:

        pass


    m=re.search(
        r"(\[.*\]|\{.*\})",
        text,
        re.S
    )


    if m:

        try:

            return json.loads(
                m.group(1)
            )

        except:

            pass


    return None




def ask_json(prompt):

    client=get_client()


    if not client:

        return None


    try:

        res=client.chat.completions.create(

            model="deepseek-chat",

            messages=[

                {
                "role":"system",
                "content":
                """
                你是运动鞋服行业研究分析师。
                输出严格JSON。
                不解释。
                """
                },

                {
                "role":"user",
                "content":prompt
                }

            ],

            temperature=0.2,

            max_tokens=2000

        )


        return extract_json(
            res.choices[0]
            .message
            .content
        )


    except Exception as e:

        print(
            "deepseek error",
            e
        )

        return None

# ======================================================
# 新闻分类体系
# ======================================================


CATEGORY_RULES = {

    "品牌竞争":
    [
        "安踏",
        "李宁",
        "特步",
        "361",
        "耐克",
        "Nike",
        "阿迪",
        "Adidas",
        "Puma",
        "HOKA",
        "昂跑",
        "亚瑟士",
        "On",
        "lululemon",
        "始祖鸟",
        "联名",
        "代言",
        "签约",
        "战略合作",
        "新品",
        "旗舰店",
        "换帅",
        "收购"
    ],


    "电商平台":
    [
        "618",
        "双11",
        "双十一",
        "天猫",
        "淘宝",
        "京东",
        "抖音",
        "直播",
        "店播",
        "小红书",
        "唯品会",
        "拼多多",
        "GMV",
        "销售额",
        "战报"
    ],


    "行业报告":
    [
        "报告",
        "调查",
        "白皮书",
        "研究",
        "数据",
        "市场规模",
        "增长率",
        "趋势"
    ],


    "宏观消费":

    [
        "GDP",
        "社零",
        "消费",
        "就业",
        "收入",
        "政策",
        "补贴",
        "内需",
        "经济",
        "统计局"
    ],


    "儿童运动":

    [
        "儿童",
        "童装",
        "童鞋",
        "亲子",
        "校园",
        "青少年",
        "Kids"
    ],


    "户外趋势":

    [
        "户外",
        "露营",
        "骑行",
        "徒步",
        "跑步",
        "马拉松",
        "越野",
        "文旅"
    ],


    "科技创新":

    [
        "AI",
        "人工智能",
        "机器人",
        "智能",
        "科技",
        "实验室",
        "材料"
    ]

}



def classify_news(title):

    result=[]


    for cat,words in CATEGORY_RULES.items():

        for w in words:

            if w in title:

                result.append(cat)

                break



    if not result:

        result.append(
            "行业动态"
        )


    return result



# ======================================================
# 新闻基础评分
# ======================================================


def news_score(item):

    title=clean_title(
        item.get("title","")
    )


    score=0


    # 时间权重

    ts=parse_time(item)


    if ts:

        hours=(
            today.timestamp()
            -
            ts
        )/3600


        if hours<12:

            score+=30

        elif hours<24:

            score+=20

        elif hours<72:

            score+=10



    # 重大事件

    important_words=[

        "战略合作",
        "收购",
        "联名",
        "代言",
        "签约",
        "新品发布",
        "财报",
        "市场份额",
        "中国战略",
        "换帅"

    ]


    for w in important_words:

        if w in title:

            score+=15



    # 经营关键词

    business_words=[

        "销售",
        "增长",
        "渠道",
        "门店",
        "会员",
        "消费者",
        "消费",
        "品牌",
        "电商",
        "直播"

    ]


    for w in business_words:

        if w in title:

            score+=5



    # 体育新闻降权

    bad=[

        "比赛",
        "比分",
        "赛程",
        "球员",
        "转会",
        "夺冠"

    ]


    for w in bad:

        if w in title:

            score-=20



    return score



# ======================================================
# TOP资讯选择
# ======================================================


def build_top_news():


    # 先排序

    ranked=sorted(

        news_items,

        key=news_score,

        reverse=True

    )


    news_text="\n".join(

        [

            f"{i+1}.{clean_title(x.get('title',''))}"

            for i,x in enumerate(ranked[:80])

        ]

    )


    prompt=f"""

你是361度儿童事业部经营分析负责人。

请从以下行业新闻中筛选8条每日重点资讯。


选择原则：

1. 优先重大行业事件

2. 品牌动作优先

3. 电商平台变化优先

4. 行业调查报告、消费数据优先

5. 国家宏观政策、经济数据如果影响消费必须关注

6. 儿童运动、户外趋势、消费者变化可入选

7. 不要选择体育比赛新闻

8. 不要为了覆盖分类强行选择低价值新闻


输出JSON数组：

[
{{
"title":"",
"category":"",
"reason":"",
"importance":"高/中"
}}
]


新闻：

{news_text}

"""


    result=ask_json(
        prompt
    )


    final=[]


    if isinstance(result,list):


        for row in result[:8]:


            if not isinstance(row,dict):

                continue


            title=short(
                row.get("title",""),
                50
            )


            if not title:

                continue



            final.append({

                "title":title,

                "category":
                row.get(
                    "category",
                    "行业动态"
                ),

                "reason":
                row.get(
                    "reason",
                    ""
                ),

                "importance":
                row.get(
                    "importance",
                    "中"
                )

            })



    # DeepSeek失败备用

    if len(final)<5:


        for item in ranked[:8]:

            final.append({

                "title":
                short(
                    item.get("title","")
                ),

                "category":
                ",".join(
                    classify_news(
                        item.get(
                            "title",
                            ""
                        )
                    )
                ),

                "reason":
                "行业信息跟踪",

                "importance":
                "中"

            })



    TOP_NEWS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    TOP_NEWS_FILE.write_text(

        json.dumps(

            {
                "items":final
            },

            ensure_ascii=False,

            indent=2

        ),

        encoding="utf-8"

    )


    return final[:8]



top_news=build_top_news()



# ======================================================
# 竞品动态
# ======================================================


COMPETITOR_BRANDS=[

    "安踏",
    "FILA",
    "李宁",
    "特步",
    "361",
    "耐克",
    "Nike",
    "阿迪达斯",
    "Adidas",
    "Puma",
    "HOKA",
    "昂跑",
    "On",
    "亚瑟士",
    "lululemon",
    "始祖鸟",
    "巴拉巴拉"

]



def build_competitor_news():


    result=[]


    for item in news_items:


        title=clean_title(
            item.get(
                "title",
                ""
            )
        )


        brand=None


        for b in COMPETITOR_BRANDS:

            if b in title:

                brand=b

                break



        if not brand:

            continue



        if any(
            x in title
            for x in [
                "比分",
                "比赛",
                "球员",
                "转会"
            ]
        ):

            continue



        result.append({

            "brand":brand,

            "title":
            short(
                title,
                35
            ),

            "source":
            item.get(
                "source",
                ""
            )

        })



    result=result[:10]



    COMPETITOR_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    COMPETITOR_FILE.write_text(

        json.dumps(

            {
                "items":result
            },

            ensure_ascii=False,

            indent=2

        ),

        encoding="utf-8"

    )


    return result



competitor_news=build_competitor_news()



# ======================================================
# 行业趋势观察
# ======================================================


def build_trends():


    prompt=f"""

你是运动鞋服行业研究员。

根据以下资讯，生成4条行业趋势观察。


要求：

- 关注未来1-3个月经营影响
- 不写新闻复述
- 要有判断
- 每条30-50字


输出JSON：

[
{{
"title":"",
"desc":""
}}
]


资讯：

{chr(10).join(titles[:60])}

"""


    result=ask_json(
        prompt
    )


    if isinstance(result,list):

        return result[:4]



    return [

        {

        "title":
        "品牌竞争持续升级",

        "desc":
        "头部品牌围绕产品科技、渠道效率和用户心智展开竞争。"

        },


        {

        "title":
        "运动消费场景扩展",

        "desc":
        "户外、亲子、跑步等细分场景继续带动新品机会。"

        }


    ]



trend_items=build_trends()

# ======================================================
# 今日行业摘要
# ======================================================


def build_summary():

    prompt=f"""

你是361°儿童事业部经营管理部负责人。

请根据今天行业资讯生成一句日报摘要。


要求：

- 50字以内
- 高管阅读口径
- 有判断，不罗列
- 体现最重要行业变化


资讯：

{chr(10).join(titles[:40])}

"""


    result=ask_json(prompt)


    if isinstance(result,dict):

        return result.get(
            "summary",
            ""
        )


    return (
        "运动鞋服行业信息持续变化，"
        "品牌竞争、电商渠道、消费趋势和宏观环境"
        "共同影响经营节奏。"
    )



today_summary=build_summary()



# ======================================================
# 经营预警
# ======================================================


def build_warning():


    prompt=f"""

你是运动鞋服行业经营负责人。

请根据以下新闻生成3条经营关注提醒。


要求：

1. 必须是当天信息触发
2. 不写空泛观点
3. 关注：
   - 品牌竞争
   - 电商平台
   - 宏观消费
   - 儿童消费
   - 渠道变化
   - 商品机会


输出：

JSON数组

[
"xxx",
"xxx",
"xxx"
]


新闻：

{chr(10).join(titles[:50])}

"""


    result=ask_json(prompt)


    if isinstance(result,list):

        return [
            str(x)
            for x in result[:3]
        ]


    return [

        "关注头部运动品牌动作变化及产品心智竞争。",

        "关注平台流量变化和线上消费趋势。",

        "关注消费环境变化对终端销售节奏影响。"

    ]



warnings=build_warning()



# ======================================================
# 天气异常提醒
# ======================================================


def load_weather_warning():


    file=Path(
        "output/weather/latest.json"
    )


    if not file.exists():

        return ""


    try:

        data=json.loads(
            file.read_text(
                encoding="utf-8"
            )
        )


    except:

        return ""



    warnings=[]


    regions=data.get(
        "regions",
        {}
    )


    for name,value in regions.items():


        days=value.get(
            "days",
            []
        )


        for day in days:


            weather=str(
                day.get(
                    "weather",
                    ""
                )
            )


            temp=float(
                day.get(
                    "temp_min",
                    20
                )
            )


            rain=float(
                day.get(
                    "precipitation",
                    0
                )
            )


            if (
                "暴雨" in weather
                or
                "台风" in weather
                or
                "强降雨" in weather
            ):

                warnings.append(
                    f"{name}出现强降雨天气，关注区域客流影响"
                )



            if temp<=5:

                warnings.append(
                    f"{name}气温明显下降，关注保暖品类需求"
                )



    return (
        "；".join(
            warnings[:2]
        )
    )



weather_warning=load_weather_warning()



# ======================================================
# HTML替换
# ======================================================


template=TEMPLATE_FILE.read_text(
    encoding="utf-8"
)



data={

    "date":
    today.strftime(
        "%Y-%m-%d"
    ),


    "weekday":
    weekday_map[
        today.weekday()
    ],


    "update_time":
    today.strftime(
        "%H:%M"
    ),


    "today_summary":
    today_summary,


    "warning1":
    warnings[0],


    "warning2":
    warnings[1],


    "warning3":
    warnings[2],


    "weather_warning":
    weather_warning,


    "news_count":
    len(news_items)

}



# TOP资讯

for i,item in enumerate(
    top_news,
    start=1
):

    data[
        f"top{i}_title"
    ] = item.get(
        "title",
        ""
    )


    data[
        f"top{i}_category"
    ] = item.get(
        "category",
        ""
    )


    data[
        f"top{i}_reason"
    ] = item.get(
        "reason",
        ""
    )


    data[
        f"top{i}_importance"
    ] = item.get(
        "importance",
        ""
    )



# 竞品

for i,item in enumerate(
    competitor_news,
    start=1
):

    data[
        f"comp{i}_brand"
    ] = item.get(
        "brand",
        ""
    )


    data[
        f"comp{i}_title"
    ] = item.get(
        "title",
        ""
    )


    data[
        f"comp{i}_source"
    ] = item.get(
        "source",
        ""
    )



# 趋势

for i,item in enumerate(
    trend_items,
    start=1
):

    data[
        f"trend{i}_title"
    ] = item.get(
        "title",
        ""
    )


    data[
        f"trend{i}_desc"
    ] = item.get(
        "desc",
        ""
    )



for key,value in data.items():

    template=template.replace(

        "{{"+key+"}}",

        str(value)

    )



OUTPUT_HTML.write_text(

    template,

    encoding="utf-8"

)



# ======================================================
# 历史保存
# ======================================================


history_dir=Path(
    "output/history"
)


history_dir.mkdir(
    parents=True,
    exist_ok=True
)



history={

    "date":
    today.strftime(
        "%Y-%m-%d"
    ),


    "summary":
    today_summary,


    "top_news":
    top_news,


    "competitor_news":
    competitor_news,


    "warnings":
    warnings,


    "trends":
    trend_items

}



history_file=history_dir / (

    today.strftime(
        "%Y-%m-%d"
    )
    +
    ".json"

)



history_file.write_text(

    json.dumps(

        history,

        ensure_ascii=False,

        indent=2

    ),

    encoding="utf-8"

)



print("======================")

print(
    "日报生成完成"
)

print(
    "新闻数量:",
    len(news_items)
)

print(
    "TOP资讯:",
    len(top_news)
)

print(
    "竞品:",
    len(competitor_news)
)

print(
    "输出:",
    OUTPUT_HTML
)

print("======================")
