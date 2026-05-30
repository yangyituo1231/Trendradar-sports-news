from pathlib import Path
from datetime import datetime
import json
import random
from urllib.parse import quote

PRODUCT_DIR = Path("output/products")
PRODUCT_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
random.seed(today)

# =========================================================
# 半真实商品趋势池
# 逻辑：真实品牌 + 真实代表商品方向 + 趋势判断 + 稳定图片占位
# 后续可升级为平台真实抓取
# =========================================================

PRODUCT_POOL = [
    # =========================
    # 儿童 / 青少年品牌
    # =========================
    {
        "brand": "安踏儿童",
        "products": [
            {"name": "安踏儿童足弓成长鞋", "category": "儿童跑鞋", "price": 299, "tags": ["足弓支撑", "校园运动", "儿童专业鞋"], "heat": 96},
            {"name": "安踏儿童氮科技跑鞋", "category": "青少年跑鞋", "price": 399, "tags": ["轻量缓震", "成人化设计", "跑步"], "heat": 94},
            {"name": "安踏儿童防晒衣", "category": "防晒衣", "price": 199, "tags": ["防晒", "轻薄", "夏季功能"], "heat": 91},
        ],
    },
    {
        "brand": "361儿童",
        "products": [
            {"name": "361儿童飞燃青少年跑鞋", "category": "青少年跑鞋", "price": 359, "tags": ["竞速感", "轻量", "成人化"], "heat": 96},
            {"name": "361儿童校园训练鞋", "category": "校园运动鞋", "price": 259, "tags": ["校园", "训练", "高性价比"], "heat": 93},
            {"name": "361儿童凉感速干T恤", "category": "凉感T恤", "price": 129, "tags": ["凉感", "速干", "夏季"], "heat": 90},
        ],
    },
    {
        "brand": "李宁YOUNG",
        "products": [
            {"name": "李宁YOUNG超轻儿童跑鞋", "category": "儿童跑鞋", "price": 399, "tags": ["超轻", "跑步", "校园"], "heat": 94},
            {"name": "李宁YOUNG篮球训练鞋", "category": "青少年篮球鞋", "price": 459, "tags": ["篮球", "缓震", "专业运动"], "heat": 92},
            {"name": "李宁YOUNG国潮运动套装", "category": "运动套装", "price": 299, "tags": ["国潮", "套装", "亲子"], "heat": 89},
        ],
    },
    {
        "brand": "FILA Kids",
        "products": [
            {"name": "FILA Kids小白鞋", "category": "儿童休闲鞋", "price": 499, "tags": ["精致", "小白鞋", "城市休闲"], "heat": 93},
            {"name": "FILA Kids网球风套装", "category": "运动套装", "price": 599, "tags": ["网球风", "高端童装", "穿搭"], "heat": 91},
            {"name": "FILA Kids轻户外外套", "category": "儿童外套", "price": 699, "tags": ["轻户外", "精致", "亲子"], "heat": 88},
        ],
    },
    {
        "brand": "Nike Kids",
        "products": [
            {"name": "Nike Kids Pegasus儿童跑鞋", "category": "儿童跑鞋", "price": 499, "tags": ["跑步", "经典系列", "缓震"], "heat": 95},
            {"name": "Nike Kids Dunk童鞋", "category": "儿童板鞋", "price": 599, "tags": ["潮流", "板鞋", "校园"], "heat": 93},
            {"name": "Nike Kids篮球训练鞋", "category": "儿童篮球鞋", "price": 529, "tags": ["篮球", "训练", "运动心智"], "heat": 91},
        ],
    },
    {
        "brand": "Adidas Kids",
        "products": [
            {"name": "Adidas Kids Samba童鞋", "category": "儿童板鞋", "price": 599, "tags": ["Samba", "复古", "潮流"], "heat": 94},
            {"name": "Adidas Kids Ultraboost童鞋", "category": "儿童跑鞋", "price": 699, "tags": ["缓震", "跑步", "舒适"], "heat": 91},
            {"name": "Adidas Kids三叶草套装", "category": "运动套装", "price": 499, "tags": ["三叶草", "潮流", "亲子"], "heat": 89},
        ],
    },

    # =========================
    # 国内成人运动品牌
    # =========================
    {
        "brand": "安踏",
        "products": [
            {"name": "安踏冠军跑鞋系列", "category": "跑鞋", "price": 599, "tags": ["专业跑步", "国货科技", "缓震"], "heat": 95},
            {"name": "安踏轻户外防晒衣", "category": "防晒衣", "price": 299, "tags": ["防晒", "轻户外", "夏季"], "heat": 93},
            {"name": "安踏篮球训练鞋", "category": "篮球鞋", "price": 499, "tags": ["篮球", "训练", "缓震"], "heat": 90},
        ],
    },
    {
        "brand": "李宁",
        "products": [
            {"name": "李宁超轻系列跑鞋", "category": "跑鞋", "price": 599, "tags": ["超轻", "跑步", "专业"], "heat": 94},
            {"name": "李宁赤兔系列跑鞋", "category": "跑鞋", "price": 399, "tags": ["入门跑步", "性价比", "训练"], "heat": 92},
            {"name": "李宁韦德篮球鞋", "category": "篮球鞋", "price": 899, "tags": ["篮球", "IP", "专业运动"], "heat": 91},
        ],
    },
    {
        "brand": "361°",
        "products": [
            {"name": "361°飞燃系列跑鞋", "category": "跑鞋", "price": 599, "tags": ["竞速", "跑步", "专业"], "heat": 94},
            {"name": "361°雨屏科技外套", "category": "轻户外服装", "price": 399, "tags": ["轻户外", "防护", "功能面料"], "heat": 91},
            {"name": "361°运动凉鞋", "category": "运动凉鞋", "price": 199, "tags": ["夏季", "凉鞋", "舒适"], "heat": 89},
        ],
    },
    {
        "brand": "特步",
        "products": [
            {"name": "特步冠军版跑鞋", "category": "跑鞋", "price": 599, "tags": ["跑步", "马拉松", "竞速"], "heat": 93},
            {"name": "特步轻量训练鞋", "category": "训练鞋", "price": 299, "tags": ["训练", "轻量", "校园"], "heat": 89},
            {"name": "特步夏季速干T恤", "category": "速干T恤", "price": 129, "tags": ["速干", "夏季", "跑步"], "heat": 88},
        ],
    },

    # =========================
    # 国际运动 / 趋势品牌
    # =========================
    {
        "brand": "Nike",
        "products": [
            {"name": "Nike Pegasus系列跑鞋", "category": "跑鞋", "price": 899, "tags": ["经典跑鞋", "缓震", "大众跑者"], "heat": 96},
            {"name": "Nike Vomero系列跑鞋", "category": "跑鞋", "price": 1099, "tags": ["厚底缓震", "跑步", "舒适"], "heat": 94},
            {"name": "Nike Dunk休闲鞋", "category": "板鞋", "price": 799, "tags": ["潮流", "校园", "复古"], "heat": 92},
        ],
    },
    {
        "brand": "Adidas",
        "products": [
            {"name": "Adidas Samba OG", "category": "板鞋", "price": 799, "tags": ["Samba", "复古", "潮流"], "heat": 96},
            {"name": "Adidas Adizero跑鞋", "category": "跑鞋", "price": 999, "tags": ["竞速", "跑步", "专业"], "heat": 93},
            {"name": "Adidas Ultraboost", "category": "跑鞋", "price": 1299, "tags": ["缓震", "舒适", "通勤"], "heat": 91},
        ],
    },
    {
        "brand": "On",
        "products": [
            {"name": "On Cloudsurfer跑鞋", "category": "跑鞋", "price": 1290, "tags": ["云感缓震", "高端跑鞋", "城市运动"], "heat": 95},
            {"name": "On Cloudmonster跑鞋", "category": "跑鞋", "price": 1390, "tags": ["厚底", "跑步", "潮流"], "heat": 94},
            {"name": "On Cloud 6通勤运动鞋", "category": "通勤运动鞋", "price": 1190, "tags": ["通勤", "轻量", "城市"], "heat": 91},
        ],
    },
    {
        "brand": "Hoka",
        "products": [
            {"name": "Hoka Clifton系列跑鞋", "category": "跑鞋", "price": 1199, "tags": ["厚底缓震", "跑步", "舒适"], "heat": 95},
            {"name": "Hoka Bondi系列跑鞋", "category": "跑鞋", "price": 1399, "tags": ["厚底", "慢跑", "缓震"], "heat": 93},
            {"name": "Hoka Speedgoat越野跑鞋", "category": "户外跑鞋", "price": 1299, "tags": ["越野", "户外", "抓地"], "heat": 91},
        ],
    },
    {
        "brand": "Salomon",
        "products": [
            {"name": "Salomon XT-6户外鞋", "category": "户外鞋", "price": 1499, "tags": ["山系穿搭", "户外", "潮流"], "heat": 94},
            {"name": "Salomon ACS系列户外鞋", "category": "户外鞋", "price": 1299, "tags": ["轻户外", "城市户外", "功能"], "heat": 91},
            {"name": "Salomon 越野跑鞋", "category": "越野跑鞋", "price": 1199, "tags": ["越野", "抓地", "专业运动"], "heat": 89},
        ],
    },
    {
        "brand": "lululemon",
        "products": [
            {"name": "lululemon Align瑜伽裤", "category": "瑜伽服", "price": 850, "tags": ["瑜伽", "女性运动", "高端"], "heat": 94},
            {"name": "lululemon训练T恤", "category": "训练服", "price": 480, "tags": ["训练", "舒适", "生活方式"], "heat": 90},
            {"name": "lululemon轻量外套", "category": "轻户外服装", "price": 1180, "tags": ["轻户外", "通勤", "高端"], "heat": 89},
        ],
    },
    {
        "brand": "The North Face",
        "products": [
            {"name": "北面防晒皮肤衣", "category": "防晒衣", "price": 699, "tags": ["防晒", "户外", "轻量"], "heat": 93},
            {"name": "北面轻量冲锋衣", "category": "冲锋衣", "price": 1299, "tags": ["户外", "防护", "功能"], "heat": 91},
            {"name": "北面徒步鞋", "category": "户外鞋", "price": 899, "tags": ["徒步", "户外", "抓地"], "heat": 88},
        ],
    },
    {
        "brand": "迪桑特",
        "products": [
            {"name": "迪桑特训练外套", "category": "训练服", "price": 1290, "tags": ["高端运动", "训练", "科技感"], "heat": 90},
            {"name": "迪桑特轻量跑步T恤", "category": "速干T恤", "price": 590, "tags": ["速干", "跑步", "高端"], "heat": 88},
            {"name": "迪桑特城市运动鞋", "category": "通勤运动鞋", "price": 990, "tags": ["通勤", "城市运动", "舒适"], "heat": 87},
        ],
    },
]

IMAGE_MAP = {
    "跑鞋": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800",
    "青少年跑鞋": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800",
    "儿童跑鞋": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800",
    "篮球鞋": "https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=800",
    "青少年篮球鞋": "https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=800",
    "儿童篮球鞋": "https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=800",
    "板鞋": "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?w=800",
    "儿童板鞋": "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?w=800",
    "户外鞋": "https://images.unsplash.com/photo-1520639888713-7851133b1ed0?w=800",
    "户外跑鞋": "https://images.unsplash.com/photo-1520639888713-7851133b1ed0?w=800",
    "越野跑鞋": "https://images.unsplash.com/photo-1520639888713-7851133b1ed0?w=800",
    "防晒衣": "https://images.unsplash.com/photo-1523381294911-8d3cead13475?w=800",
    "凉感T恤": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800",
    "速干T恤": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800",
    "轻户外服装": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=800",
    "冲锋衣": "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=800",
    "瑜伽服": "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=800",
    "训练服": "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=800",
    "通勤运动鞋": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=800",
    "运动凉鞋": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=800",
    "运动套装": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=800",
    "儿童休闲鞋": "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?w=800",
}


def get_image(category, brand):
    if category in IMAGE_MAP:
        return IMAGE_MAP[category]
    text = quote(f"{brand} {category}")
    return f"https://placehold.co/420x300/eaf2ff/0b4db3?text={text}"


def normalize_trend():
    return random.choice(["up", "up", "hot", "new", "flat"])


data = {
    "date": today,
    "source": "TrendRadar product monitor",
    "desc": "半真实运动品牌鞋服商品趋势池：覆盖儿童、青少年、成人、国内、国际及趋势品牌；用于周报商品观察，后续可升级为平台真实抓取。",
    "brands": []
}

for brand_block in PRODUCT_POOL:
    brand = brand_block["brand"]
    products = []

    for idx, p in enumerate(brand_block["products"], start=1):
        heat = int(p.get("heat", random.randint(80, 95)))
        heat = min(99, max(70, heat + random.randint(-2, 2)))

        products.append({
            "rank": idx,
            "name": p["name"],
            "category": p["category"],
            "price": p["price"],
            "trend": normalize_trend(),
            "sales_heat": heat,
            "tags": p["tags"],
            "image": get_image(p["category"], brand),
            "reason": "结合品牌代表款、季节品类、平台热词与运动场景生成，用于周报商品观察。"
        })

    data["brands"].append({
        "brand": brand,
        "products": products
    })

output_file = PRODUCT_DIR / f"{today}.json"
latest_file = PRODUCT_DIR / "latest_products.json"

output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
latest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"products saved: {output_file}")
print(f"latest products saved: {latest_file}")
