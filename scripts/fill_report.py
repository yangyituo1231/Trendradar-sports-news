from pathlib import Path

template = Path("daily-report.html").read_text(encoding="utf-8")

data = {
    "top1_title": "On昂跑亚太市场增长延续",
    "top1_desc": "高端跑步与女性消费需求仍是运动品牌增长的重要观察点。",
    "top2_title": "儿童轻户外与防晒需求升温",
    "top2_desc": "夏季临近，防晒、凉感、速干、户外休闲品类值得重点关注。",
    "trend1_title": "内容电商继续放大运动户外种草",
    "trend1_desc": "抖音、小红书对轻运动、骑行、跑步装备的消费教育作用增强。",
    "trend2_title": "奥莱与商场周末客流仍需关注",
    "trend2_desc": "亲子客流、区域天气和节假日活动会直接影响门店转化。"
}

for key, value in data.items():
    template = template.replace("{{" + key + "}}", value)

Path("daily-report-filled.html").write_text(template, encoding="utf-8")

print("daily-report-filled.html generated.")
