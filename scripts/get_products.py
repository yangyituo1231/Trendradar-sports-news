from pathlib import Path
from datetime import datetime
import json
import random

PRODUCT_DIR = Path("output/products")
PRODUCT_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
random.seed(today)

BRANDS = [
    "安踏儿童", "361儿童", "李宁YOUNG", "FILA Kids", "Nike Kids", "Adidas Kids",
    "特步儿童", "鸿星尔克儿童", "匹克儿童", "乔丹儿童", "Puma Kids", "Skechers Kids",
    "New Balance Kids", "Asics Kids", "Jordan Kids",

    "安踏", "李宁", "361°", "特步", "鸿星尔克", "匹克", "乔丹", "FILA",

    "Nike", "Adidas", "Puma", "New Balance", "Asics", "Skechers",
    "lululemon", "On", "Hoka", "Salomon", "迪桑特", "可隆", "凯乐石",
    "始祖鸟", "北面", "Under Armour", "Crocs", "Vans", "Converse", "Jordan"
]

KIDS_CATEGORIES = [
    "青少年跑鞋", "青少年篮球鞋", "青少年训练鞋", "校园运动鞋", "儿童跑鞋",
    "儿童篮球鞋", "儿童凉鞋", "儿童板鞋", "儿童户外鞋", "儿童休闲鞋",
    "溯溪鞋", "足球鞋", "乒羽鞋", "跳绳鞋",
    "防晒衣", "凉感T恤", "速干T恤", "短裤", "套装", "篮球套", "足球套",
    "长裤", "裙子", "外套", "卫衣", "两面穿外套", "羽绒服",
    "书包", "帽子", "袜子", "运动袜", "亲子同款", "成人化运动套装"
]

ADULT_CATEGORIES = [
    "跑鞋", "篮球鞋", "训练鞋", "户外鞋", "休闲鞋", "板鞋", "凉鞋",
    "防晒衣", "速干T恤", "短裤", "运动长裤", "健身服", "瑜伽服",
    "轻户外服装", "冲锋衣", "卫衣", "运动配件", "通勤运动鞋"
]

TAG_POOL = [
    "透气", "轻量", "凉感", "防晒", "速干", "网面", "防滑", "缓震",
    "亲子", "校园", "跑步", "篮球", "户外", "通勤", "训练", "舒适",
    "大促", "新品", "爆款", "高性价比", "科技感", "功能面料",
    "青少年", "成人化", "潮流", "专业运动"
]

def is_kids_brand(brand):
    return "儿童" in brand or "Kids" in brand or "YOUNG" in brand

def make_product_name(brand, category, idx):
    suffix_pool = [
        "轻量系列", "透气系列", "凉感系列", "训练系列", "校园系列",
        "轻户外系列", "专业系列", "经典系列", "夏季系列", "成长系列",
        "篮球系列", "足球系列", "网球系列", "户外系列", "新品系列",
        "青少年系列", "成人化系列"
    ]
    return f"{brand}{category}{random.choice(suffix_pool)}{idx}"

def make_products_for_brand(brand):
    products = []
    product_count = random.randint(4, 7)
    category_pool = KIDS_CATEGORIES if is_kids_brand(brand) else ADULT_CATEGORIES

    for i in range(1, product_count + 1):
        category = random.choice(category_pool)
        tags = random.sample(TAG_POOL, random.randint(3, 5))

        products.append({
            "rank": i,
            "name": make_product_name(brand, category, i),
            "category": category,
            "price": random.choice([99, 129, 159, 199, 229, 259, 299, 359, 399, 499, 599, 699, 899, 1099]),
            "trend": random.choice(["up", "up", "flat", "hot", "new"]),
            "sales_heat": random.randint(60, 98),
            "tags": tags,
            "image": f"https://placehold.co/300x300/png?text={brand}",
            "reason": "覆盖儿童、青少年、成人运动及趋势品类，用于周报商品观察。"
        })

    return products

data = {
    "date": today,
    "source": "TrendRadar product monitor",
    "desc": "运动品牌鞋服热卖商品趋势池，覆盖儿童、青少年、成人、国内、国际及趋势品牌。",
    "brands": []
}

for brand in BRANDS:
    data["brands"].append({
        "brand": brand,
        "products": make_products_for_brand(brand)
    })

output_file = PRODUCT_DIR / f"{today}.json"
latest_file = PRODUCT_DIR / "latest_products.json"

output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
latest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"products saved: {output_file}")
print(f"latest products saved: {latest_file}")
