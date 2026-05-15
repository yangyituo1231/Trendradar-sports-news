from pathlib import Path

template = Path("daily-report.html").read_text(encoding="utf-8")

data = {
    "title": "361°儿童行业热点日报",
    "subtitle": "2026年5月15日｜运动童装行业观察",

    "top1_title": "On品牌一季度增长超预期",
    "top1_desc": "亚太市场增长明显，女性跑步需求持续提升。",

    "top2_title": "儿童户外消费持续升温",
    "top2_desc": "防晒、轻户外、骑行类商品热度明显提升。",

    "trend1_title": "电商平台增长明显",
    "trend1_desc": "内容电商带动运动童装成交持续增长。",

    "trend2_title": "线下客流逐步恢复",
    "trend2_desc": "五一后购物中心家庭消费逐步恢复。"
}

for key, value in data.items():
    template = template.replace("{{" + key + "}}", value)

Path("daily-report-filled.html").write_text(
    template,
    encoding="utf-8"
)

print("daily-report-filled.html generated.")
