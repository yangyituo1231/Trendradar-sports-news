from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re


# =========================================================
# 基础配置
# =========================================================

TEMPLATE_FILE = Path("daily-report.html")
OUTPUT_HTML = Path("daily-report-filled.html")

NEWS_FILE = Path("output/news/latest.json")

HISTORY_DIR = Path("output/history")


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



# =========================================================
# 基础函数
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = text.replace("\n"," ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()



def short(text, length=60):

    text = clean_text(text)

    if len(text)<=length:
        return text

    return text[:length]+"..."




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

        dt = parsedate_to_datetime(value)

        return dt.timestamp()

    except:

        return 0




# =========================================================
# 读取新闻
# =========================================================

def load_news():

    if not NEWS_FILE.exists():

        print(
            "news file not found"
        )

        return []


    try:

        data = json.loads(
            NEWS_FILE.read_text(
                encoding="utf-8"
            )
        )


        if isinstance(data,dict):

            if "items" in data:

                return data["items"]

            if "news" in data:

                return data["news"]


        if isinstance(data,list):

            return data


    except Exception as e:

        print(
            "load news error:",
            e
        )


    return []




news_items = load_news()



# =========================================================
# 新闻基础清洗
# =========================================================

def clean_news(items):

    result=[]

    seen=set()


    for item in items:


        if not isinstance(item,dict):

            continue


        title = clean_text(
            item.get("title","")
        )


        if not title:

            continue



        if title in seen:

            continue



        item["title"]=title


        result.append(item)


        seen.add(title)



    return result




news_items = clean_news(news_items)



# =========================================================
# 时间排序
# =========================================================

news_items.sort(
    key=parse_time,
    reverse=True
)



print(
    "news count:",
    len(news_items)
)

# =========================================================
# DeepSeek
# =========================================================

def deepseek_client():

    api_key = os.getenv(
        "DEEPSEEK_API_KEY"
    )


    if not api_key:

        return None



    try:

        from openai import OpenAI


        return OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )


    except Exception as e:

        print(
            "DeepSeek init error:",
            e
        )

        return None




def extract_json(text):

    if not text:

        return None


    text=text.strip()


    text=re.sub(
        r"^```json",
        "",
        text
    )


    text=re.sub(
        r"```$",
        "",
        text
    )


    try:

        return json.loads(text)


    except:


        pass


    match=re.search(
        r"\[.*\]",
        text,
        re.S
    )


    if match:

        try:

            return json.loads(
                match.group()
            )

        except:

            pass


    return None





def ask_deepseek(prompt,max_tokens=2000):

    client=deepseek_client()


    if client is None:

        return None


    try:


        response=client.chat.completions.create(

            model="deepseek-chat",

            messages=[

                {
                    "role":"system",
                    "content":
                    """
你是一名专业商业资讯编辑，服务运动鞋服企业管理层。

你的任务：
每天整理全球及中国运动鞋服、消费零售、电商、品牌、科技、宏观领域的重要新闻。

核心原则：

1. 新闻优先，不做儿童行业解读。
2. 不要强行关联361度。
3. 不要输出“对儿童市场启发”“对公司经营建议”等内容。
4. 只回答：
   - 今天发生了什么？
   - 为什么值得关注？
   - 行业影响是什么？

重点关注：

品牌：
Nike、Adidas、安踏、李宁、特步、361、HOKA、On昂跑、lululemon、ASICS等。

渠道：
天猫、京东、抖音、小红书、唯品会、得物。

行业：
运动鞋服趋势、零售变化、消费趋势、供应链、企业战略、财报、人事变化。

宏观：
消费数据、政策、居民消费变化。

过滤：
- 体育比赛比分
- 娱乐新闻
- 明星新闻
- 单纯营销软文
- 618促销堆砌（除非有平台策略变化）

输出要求：
客观、简洁、商业化。
不要制造观点。
"""
                },


                {
                    "role":"user",
                    "content":prompt
                }

            ],


            temperature=0.25,


            max_tokens=max_tokens

        )


        return extract_json(
            response.choices[0].message.content
        )


    except Exception as e:

        print(
            "DeepSeek error:",
            e
        )

        return None






# =========================================================
# TOP8新闻编辑
# =========================================================

def build_top_news():



    news_text=""


    for i,item in enumerate(news_items[:100]):

        news_text += (

            f"{i+1}."
            + clean_text(item.get("title",""))
            + "｜"
            + clean_text(item.get("source",""))
            + "\n"

        )




    prompt=f"""

请从以下运动鞋服、消费、电商、宏观新闻中，
筛选今日最值得企业管理层阅读的8条资讯。


筛选原则：

1. 优先重大行业变化：
- 品牌战略
- 财报
- 管理层变化
- 新品发布
- 渠道调整
- 平台规则变化
- 行业研究报告
- 消费趋势变化


2. 保留范围：

运动鞋服：
安踏、李宁、特步、361、Nike、Adidas、
Puma、On、HOKA、lululemon等


消费：

社零、消费趋势、居民收入、
年轻消费、品质消费、健康消费


电商：
天猫、京东、抖音、
小红书、唯品会


3. 不需要每天出现618，
除非当天确实有重要信息。


4. 过滤：

- 体育比赛结果
- 娱乐新闻
- 无商业价值热点


5. 输出JSON数组：

[
{{
"title":"",
"category":"",
"source":"",
"time":"",
"summary":"",
"level":"★★★★★"
}}
]


category只能使用：

品牌竞争
电商平台
行业报告
宏观消费
户外运动
消费趋势
科技趋势


新闻：

{news_text}

"""


    result=ask_deepseek(
        prompt,
        max_tokens=2500
    )



    if not isinstance(result,list):

        return fallback_top_news()



    final=[]


    for row in result[:8]:


        if not isinstance(row,dict):

            continue


        final.append({

            "title":
            short(row.get("title",""),60),

            "category":
            row.get(
                "category",
                "行业观察"
            ),

            "source":
            row.get(
                "source",
                "公开资讯"
            ),

            "time":
            row.get(
                "time",
                ""
            ),

            "summary":
            short(
                row.get(
                    "summary",
                    ""
                ),
                100
            ),

            "level":
            row.get(
                "level",
                "★★★"
            )

        })


    return final






def fallback_top_news():

    result=[]


    for item in news_items[:8]:

        result.append({

            "title":
            short(
                item.get("title",""),
                60
            ),

            "category":
            "行业资讯",

            "source":
            item.get(
                "source",
                "公开资讯"
            ),

            "time":
            "",

            "summary":
            "",

            "level":
            "★★★"

        })


    return result




top_news=build_top_news()

# =========================================================
# 电商平台动态
# =========================================================

def build_ec_news():


    platform_words = [
        "天猫",
        "淘宝",
        "京东",
        "抖音",
        "快手",
        "小红书",
        "唯品会",
        "得物",
        "拼多多"
    ]


    candidates=[]


    for item in news_items:


        title=clean_text(
            item.get("title","")
        )


        if any(
            p in title
            for p in platform_words
        ):

            candidates.append(item)



    if not candidates:

        return fallback_ec()



    prompt=f"""

你是运动鞋服行业电商观察编辑。

请从以下新闻中筛选5条电商平台相关动态。


关注：

- 平台战略变化
- 流量机制变化
- 内容生态变化
- 直播电商趋势
- 品类增长变化
- 商家运营模式变化


不要强行输出618，
除非新闻确实涉及。


输出JSON：

[
{{
"platform":"",
"title":"",
"summary":""
}}
]


新闻：

{
chr(10).join(
x.get("title","")
for x in candidates[:50]
)

}

"""


    result=ask_deepseek(
        prompt,
        max_tokens=1200
    )


    if not isinstance(result,list):

        return fallback_ec()



    return result[:5]





def fallback_ec():

    return [

        {
        "platform":"",
        "title":"",
        "summary":""
        }

        for _ in range(5)

    ]






ec_news=build_ec_news()






# =========================================================
# 竞品动态
# =========================================================


def build_competitor_news():


    brands=[

        "安踏",
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
        "lululemon",
        "始祖鸟"
        "New Balance",
        "锐步",
        "Under Armour",
         "Salomon",

    ]


    candidates=[]



    for item in news_items:


        title=clean_text(
            item.get(
                "title",
                ""
            )
        )


        if any(
            b in title
            for b in brands
        ):

            candidates.append(item)



    if not candidates:

        return [

        {
        "brand":"",
        "title":"",
        "summary":""
        }

        for _ in range(6)

        ]



    prompt=f"""

你是运动鞋服行业竞争情报编辑。

请整理以下品牌新闻。

关注：

- 战略变化
- 新品发布
- 营销动作
- 渠道变化
- 财报变化
- 管理层调整


输出：

[
{{
"brand":"",
"title":"",
"summary":""
}}
]

只报道品牌动作，不评价对361度的影响。
不要输出：

- 娱乐内容


新闻：

{
chr(10).join(
x.get("title","")
for x in candidates[:60]
)

}

"""


    result=ask_deepseek(
        prompt,
        max_tokens=1500
    )


    if not isinstance(result,list):

        return []



    return result[:6]




competitor_news=build_competitor_news()







# =========================================================
# 行业研究报告
# =========================================================


def build_reports():



    report_words=[

        "报告",
        "白皮书",
        "研究",
        "趋势",
        "调查",
        "数据",
        "市场规模",
        "消费洞察"

    ]


    candidates=[]


    for item in news_items:


        title=clean_text(
            item.get(
                "title",
                ""
            )
        )


        if any(
            w in title
            for w in report_words
        ):

            candidates.append(item)




    if not candidates:

        return [

        {
        "category":"",
        "title":"",
        "summary":""
        }

        for _ in range(3)

        ]



    prompt=f"""

你是消费行业研究编辑。


请筛选与运动鞋服、大众消费趋势、
零售、电商相关的研究报告。


输出：

[
{{
"category":"",
"title":"",
"summary":""
}}
]


新闻：

{
chr(10).join(
x.get("title","")
for x in candidates[:50]
)

}

"""


    result=ask_deepseek(
        prompt,
        max_tokens=1000
    )



    if not isinstance(result,list):

        return []



    return result[:3]



report_news=build_reports()








# =========================================================
# 异常提醒
# =========================================================


def build_alert():


    prompt=f"""

你是企业行业风险提醒助手。


请判断以下新闻是否存在：

1. 极端天气
2. 区域重大事件
3. 消费政策变化
4. 品牌重大风险事件
5. 行业突发事件


如果没有重要事件，
输出：

暂无重大异常事件


如果有：

输出一段50字以内提醒。


新闻：

{
chr(10).join(
x.get("title","")
for x in news_items[:80]
)

}

"""


    result=ask_deepseek(
        prompt,
        max_tokens=200
    )


    if result:

        return str(result)


    return "暂无重大异常事件"




alert_content=build_alert()

# =========================================================
# 今日一句话观察
# =========================================================


def build_today_summary():


    prompt=f"""

你是一名商业资讯编辑。


请根据今日重点资讯，
总结一句行业观察。


要求：

- 40字以内
- 不写空泛判断
- 不写经营动作
- 体现当天行业变化
不要结合儿童市场。
不要给企业经营建议。
不要出现“361度应该……”。


新闻：

{
chr(10).join(
x.get("title","")
for x in top_news[:8]
)

}

"""


    result=ask_deepseek(
        prompt,
        max_tokens=200
    )


    if result:

        return str(result)



    return "运动鞋服行业信息持续变化，品牌竞争、电商渠道与消费趋势值得关注。"




today_summary=build_today_summary()





# =========================================================
# HTML变量填充
# =========================================================


def set_default(value):

    if value is None:

        return ""

    return str(value)





data={

"date":
today.strftime("%Y-%m-%d"),


"weekday":
weekday_map[today.weekday()],


"update_time":
today.strftime("%H:%M"),


"today_summary":
today_summary,


"alert_content":
alert_content

}





# =========================================================
# TOP新闻变量
# =========================================================


for i in range(1,9):


    item = (
        top_news[i-1]
        if i<=len(top_news)
        else {}
    )


    data[f"top{i}_title"] = item.get(
        "title",
        ""
    )
    
    data[f"top{i}_url"] = item.get(
        "url",
        ""
     )


    data[f"top{i}_category"] = item.get(
        "category",
        ""
    )


    data[f"top{i}_source"] = item.get(
        "source",
        ""
    )


    data[f"top{i}_time"] = item.get(
        "time",
        ""
    )


    data[f"top{i}_summary"] = item.get(
        "summary",
        ""
    )


    data[f"top{i}_level"] = item.get(
        "level",
        ""
    )







# =========================================================
# 电商动态变量
# =========================================================


for i in range(1,6):


    item=(

        ec_news[i-1]
        if i<=len(ec_news)
        else {}

    )


    data[f"ec{i}_platform"]=item.get(
        "platform",
        ""
    )


    data[f"ec{i}_title"]=item.get(
        "title",
        ""
    )


    data[f"ec{i}_summary"]=item.get(
        "summary",
        ""
    )








# =========================================================
# 竞品变量
# =========================================================


for i in range(1,7):


    item=(

        competitor_news[i-1]
        if i<=len(competitor_news)
        else {}

    )


    data[f"comp{i}_brand"]=item.get(
        "brand",
        ""
    )


    data[f"comp{i}_title"]=item.get(
        "title",
        ""
    )


    data[f"comp{i}_summary"]=item.get(
        "summary",
        ""
    )







# =========================================================
# 行业报告变量
# =========================================================


for i in range(1,4):


    item=(

        report_news[i-1]
        if i<=len(report_news)
        else {}

    )


    data[f"report{i}_category"]=item.get(
        "category",
        ""
    )


    data[f"report{i}_title"]=item.get(
        "title",
        ""
    )


    data[f"report{i}_summary"]=item.get(
        "summary",
        ""
    )







# =========================================================
# 今日关注
# =========================================================


warnings=[

"关注国际及国内运动品牌竞争格局变化。",

"关注电商渠道、零售终端及消费趋势变化。",

"关注宏观环境对体育消费行业的影响。"

]

]



for i in range(1,4):

    data[f"warning{i}"]=warnings[i-1]








# =========================================================
# 读取HTML模板
# =========================================================


if not TEMPLATE_FILE.exists():

    raise FileNotFoundError(
        "daily-report.html不存在"
    )



html=TEMPLATE_FILE.read_text(
    encoding="utf-8"
)




for key,value in data.items():

    html=html.replace(
        "{{"+key+"}}",
        set_default(value)
    )






# =========================================================
# 输出HTML
# =========================================================


OUTPUT_HTML.write_text(
    html,
    encoding="utf-8"
)



print(
    "daily-report-filled.html generated"
)







# =========================================================
# 保存历史
# =========================================================


HISTORY_DIR.mkdir(
    parents=True,
    exist_ok=True
)



history={

"date":
today.strftime("%Y-%m-%d"),


"summary":
today_summary,


"top_news":
top_news,


"competitor":
competitor_news,


"ecommerce":
ec_news,


"reports":
report_news,


"alert":
alert_content

}



history_file = (
    HISTORY_DIR
    /
    f"{today.strftime('%Y-%m-%d')}.json"
)



history_file.write_text(

    json.dumps(
        history,
        ensure_ascii=False,
        indent=2
    ),

    encoding="utf-8"

)



print(
    "history saved:",
    history_file
)
