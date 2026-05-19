from pathlib import Path
from datetime import datetime
import random

template = Path("daily-report.html").read_text(encoding="utf-8")

# 关键词池：后续可以继续增加行业热词
hot_words_pool = [
    "On 昂跑", "暴雨预警", "童装生活方式", "防晒", "轻户外", "凉感",
    "对流", "夜经济", "奥莱", "lululemon", "彪马", "骑行经济",
    "儿童经济", "短裤", "轻外套", "户外休闲", "亲子消费", "校园运动",
    "跑步热", "运动童装", "折扣零售", "会员运营", "商场客流", "奥特莱斯",
    "暑期消费", "防晒衣", "速干", "露营", "文旅消费", "内容电商",
    "小红书种草", "抖音电商", "618", "品牌联名", "女性运动", "高端跑鞋"
]

selected_words = random.sample(hot_words_pool, 12)

data = {
    "title": "运动品牌行业资讯日报",
    "subtitle": "每日精选 · 洞察趋势 · 辅助决策",
    "date": "2026-05-15",
    "weekday": "星期五",
    "update_time": "08:30",
    "monitor_count": "215",
    "rss_count": "40",
    "focus_count": "5",

    "top1_title": "On品牌高增长延续，亚太市场表现强劲",
    "top1_tag": "运动品牌动态",
    "top1_time": "05-15 08:10",
    "top1_source": "公开资讯",
    "top1_desc": "高端跑步与女性运动需求持续释放，品牌增长动能仍具观察价值。",

    "top2_title": "运动品牌加码中国市场，本土化布局提速",
    "top2_tag": "经营信号",
    "top2_time": "05-15 09:20",
    "top2_source": "行业媒体",
    "top2_desc": "中国市场仍是全球运动品牌重点投入方向，渠道、产品与营销本土化重要性提升。",

    "top3_title": "童装生活方式化趋势增强",
    "top3_tag": "童装/儿童运动",
    "top3_time": "05-15 10:05",
    "top3_source": "消费观察",
    "top3_desc": "童装消费从单一服饰需求转向场景经营，亲子、户外、校园运动价值提升。",

    "top4_title": "折扣与会员运营持续升温",
    "top4_tag": "线下零售经营",
    "top4_time": "05-15 11:30",
    "top4_source": "平台资讯",
    "top4_desc": "折扣场景与会员运营成为提升转化的重要抓手，奥莱及购物中心活动值得关注。",

    "top5_title": "局部降雨影响周末客流节奏",
    "top5_tag": "天气影响消费",
    "top5_time": "05-15 07:40",
    "top5_source": "公开气象信息",
    "top5_desc": "华东、华中、华南部分区域存在降雨影响，门店需关注周末客流波动与商品陈列切换。",

    "weather_range": "05-15 ~ 05-17",
    "weather_north": "北方多地天气转晴，周末空气转好，户外及商场客流具备恢复基础。",
    "weather_east": "华东局部降雨延续，短途出行与商圈客流可能出现波动。",
    "weather_southwest": "华南、西南局部降雨增强，防晒与轻户外需求需结合天气灵活调整。",
    "weather_northwest": "西北多地晴到多云，户外露营、亲子活动关注度有望提升。",

    "day1": "05-15",
    "day2": "05-16",
    "day3": "05-17",
    "north_day1": "晴到多云",
    "north_day2": "多云",
    "north_day3": "晴",
    "east_day1": "局部降雨",
    "east_day2": "阵雨",
    "east_day3": "多云",
    "south_day1": "阵雨/雷阵雨",
    "south_day2": "中到大雨",
    "south_day3": "降雨减弱",
    "southwest_day1": "阵雨",
    "southwest_day2": "多云",
    "southwest_day3": "多云",
    "northwest_day1": "晴到多云",
    "northwest_day2": "多云",
    "northwest_day3": "晴",

    "east_city": "上海/江苏/浙江",
    "east_hot": "北京试点自行车“坐”地铁，骑行经济热度提升",
    "east_flow": "商圈客流回暖但雨天扰动仍在，周末波动较大",
    "east_signal": "防晒、轻外套、运动场景及室内体验需求提升",
    "east_action": "可关注骑行周边、轻户外、运动场景及室内承接",
    "east_star": "★★★",

    "central_city": "湖北/湖南/江西",
    "central_hot": "雨天影响客流，周末波动明显",
    "central_flow": "商圈客流存在波动，活动转化需更精细",
    "central_signal": "短袖启动偏慢，轻防护需求提升",
    "central_action": "结合天气节奏主推薄外套、防雨、防晒及轻运动单品",
    "central_star": "★★",

    "south_city": "广东/广西",
    "south_hot": "广州文旅与夜经济活跃，消费场景增加",
    "south_flow": "夜间客流增加，夜经济活跃",
    "south_signal": "凉感、短裤、短袖及防晒品类需求上升",
    "south_action": "可关注夜场活动、防晒陈列及户外场景搭配",
    "south_star": "★★★",

    "southwest_city": "四川/重庆/贵州",
    "southwest_hot": "文旅活动带动亲子出行",
    "southwest_flow": "文旅客流活跃，亲子客群增长",
    "southwest_signal": "亲子休闲、户外轻运动增长",
    "southwest_action": "可围绕亲子体验、户外品类与场景化陈列展开",
    "southwest_star": "★★",

    "northwest_city": "陕西/甘肃/宁夏",
    "northwest_hot": "天气干燥多风，户外活动活跃",
    "northwest_flow": "户外客流活跃，周末出行增加",
    "northwest_signal": "防护用品、帽子等轻防护需求提升",
    "northwest_action": "加强防晒、防风装备陈列，强化出行场景关联",
    "northwest_star": "★",

    "trend1_title": "运动品牌增长分化",
    "trend1_desc": "高端跑步、专业运动与女性运动仍是品牌增长的重要结构性机会。",
    "trend1_tag": "品牌趋势",

    "trend2_title": "童装生活方式化",
    "trend2_desc": "童装消费从单品售卖转向亲子、校园、户外与运动场景经营。",
    "trend2_tag": "儿童消费趋势",

    "trend3_title": "奥莱与折扣零售升温",
    "trend3_desc": "折扣场景与会员运营价值提升，终端需要更重视价格带和连带转化。",
    "trend3_tag": "渠道趋势",

    "trend4_title": "骑行/露营/文旅联动",
    "trend4_desc": "骑行经济、文旅消费与亲子户外共同带动运动场景与周边需求。",
    "trend4_tag": "消费趋势",

    "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
}

# 动态关键词填入
for i, word in enumerate(selected_words, start=1):
    data[f"word{i}"] = word

for key, value in data.items():
    template = template.replace("{{" + key + "}}", str(value))

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
