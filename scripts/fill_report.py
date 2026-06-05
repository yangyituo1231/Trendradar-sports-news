from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from collections import Counter
import random, json, re, os

TEMPLATE_FILE = Path('daily-report.html')
OUTPUT_HTML = Path('daily-report-filled.html')
TOP_NEWS_FILE = Path('output/news/top_news.json')
COMPETITOR_NEWS_FILE = Path('output/news/competitor_news.json')

template = TEMPLATE_FILE.read_text(encoding='utf-8')
now = datetime.now()
today = now
day2 = today + timedelta(days=1)
day3 = today + timedelta(days=2)
random.seed(today.strftime('%Y-%m-%d-%H'))
weekday_map = {0:'星期一',1:'星期二',2:'星期三',3:'星期四',4:'星期五',5:'星期六',6:'星期日'}

def md(d): return d.strftime('%m-%d')
def clean_title(text):
    text = str(text or '').replace('\n','').strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r' - .*?$', '', text)
    text = re.sub(r'_.*?$', '', text)
    return text

def short(text, n=42):
    text = clean_title(text)
    return text if len(text) <= n else text[:n] + '...'

def short_cn(text, n=32):
    text = clean_title(text)
    return text if len(text) <= n else text[:n]

def season_name(month):
    if month in [3,4,5]: return 'spring'
    if month in [6,7,8]: return 'summer'
    if month in [9,10,11]: return 'autumn'
    return 'winter'
SEASON = season_name(today.month)

# =========================================================
# 读取新闻
# =========================================================
news_items = []
news_file = Path('output/news/latest.json')

def parse_news_time(item):
    v = item.get('published_at') or item.get('pubDate') or item.get('date') or item.get('time') or ''
    if not v: return 0
    try:
        return parsedate_to_datetime(v).timestamp()
    except Exception:
        return 0

if news_file.exists():
    try:
        raw = json.loads(news_file.read_text(encoding='utf-8'))
        news_items = raw.get('items', []) if isinstance(raw, dict) else raw
    except Exception as e:
        print('load latest news error:', repr(e))

def news_rank_score(item):
    return int(item.get('score') or 0) * 10000000000 + parse_news_time(item)

stock_words = ['涨停','跌停','龙虎榜','证券','A股','港股','收盘','开盘','股价','市值','个股','券商','研报','融资融券','减持','增持']
filtered_news = []
for item in news_items:
    if not isinstance(item, dict): continue
    title = clean_title(item.get('title',''))
    if any(w in title for w in stock_words): continue
    ts = parse_news_time(item)
    if ts > 0:
        news_dt = datetime.fromtimestamp(ts)
        if (today - news_dt).days > 30: continue
    filtered_news.append(item)

news_items = sorted(filtered_news, key=news_rank_score, reverse=True)
titles = [clean_title(x.get('title','')) for x in news_items if x.get('title')]
joined = ' '.join(titles)

# =========================================================
# 天气
# =========================================================
weather = {}
weather_file = Path('output/weather/latest.json')
if weather_file.exists():
    try: weather = json.loads(weather_file.read_text(encoding='utf-8'))
    except Exception as e: print('load weather error:', repr(e))
weather_regions = weather.get('regions', {}) if isinstance(weather, dict) else {}

def get_weather_region(key): return weather_regions.get(key, {})
def get_day_weather(key, idx):
    days = get_weather_region(key).get('days', [])
    if idx < len(days): return days[idx]
    return {'weather':'多云','code':2,'temp_max':25,'temp_min':18,'precipitation':0,'wind':12,'risk_score':25}
def weather_day_label(key, idx): return get_day_weather(key, idx).get('weather','多云')
def weather_risk_raw(key): return int(get_weather_region(key).get('risk_score', 25))
def weather_stats(key):
    days = [get_day_weather(key, i) for i in range(3)]
    return {
        'max_temp': max(float(d.get('temp_max',25)) for d in days),
        'min_temp': min(float(d.get('temp_min',18)) for d in days),
        'max_rain': max(float(d.get('precipitation',0)) for d in days),
        'max_wind': max(float(d.get('wind',12)) for d in days),
        'codes': [int(d.get('code',2)) for d in days],
        'weathers': [str(d.get('weather','多云')) for d in days],
        'risk': weather_risk_raw(key),
    }
def has_snow(s): return any(c in [71,73,75,77,85,86] for c in s['codes']) or any('雪' in w for w in s['weathers'])
def has_rain(s): return s['max_rain'] >= 3 or any(c in [51,53,55,61,63,65,80,81,82,95,96,99] for c in s['codes']) or any('雨' in w for w in s['weathers'])
def has_storm(s): return s['max_rain'] >= 20 or any(c in [82,95,96,99] for c in s['codes']) or any('雷' in w or '强' in w for w in s['weathers'])
def is_hot(s): return s['max_temp'] >= 30
def is_very_hot(s): return s['max_temp'] >= 35
def is_cold(s): return s['min_temp'] <= 5
def is_freezing(s): return s['min_temp'] <= 0
def is_windy(s): return s['max_wind'] >= 25

def weather_business_type(key):
    s = weather_stats(key)
    if has_snow(s) or is_freezing(s): return 'snow_ice'
    if is_cold(s): return 'cold'
    if has_storm(s): return 'storm'
    if has_rain(s): return 'rain'
    if is_very_hot(s): return 'very_hot'
    if is_hot(s): return 'hot'
    if is_windy(s): return 'wind'
    if SEASON == 'spring': return 'spring_mild'
    if SEASON == 'autumn': return 'autumn_mild'
    if SEASON == 'winter': return 'winter_mild'
    return 'normal'

def heat_class_by_weather(key):
    t = weather_business_type(key)
    if t in ['very_hot','hot']: return 'heat-dot-hot'
    if t in ['storm','rain']: return 'heat-dot-rain'
    if t in ['snow_ice','cold','winter_mild']: return 'heat-dot-cold'
    return 'heat-dot-normal'

def map_heat_class():
    types = [weather_business_type(k) for k in ['north','east','south','southwest','northwest']]
    if any(t in types for t in ['very_hot','hot']): return 'heat-hot'
    if any(t in types for t in ['storm','rain']): return 'heat-rain'
    if any(t in types for t in ['snow_ice','cold','winter_mild']): return 'heat-cold'
    return 'heat-normal'

def weather_desc(key):
    mapping = {
        'snow_ice':'雨雪或低温结冰风险提升，防滑、保暖及室内客流承接需关注',
        'cold':'低温天气影响户外停留，保暖、棉服、帽类及运动鞋需求提升',
        'storm':'强降雨或雷阵雨扰动客流，防雨、防滑与室内运动场景需关注',
        'rain':'降雨影响客流，防雨、轻防护与室内运动场景需求提升',
        'very_hot':'高温天气明显，防晒、凉感、速干品类进入主推窗口',
        'hot':'气温偏高，防晒、短裤、轻薄T恤需求提升',
        'wind':'阵风偏强，轻外套、帽子等防护单品关注提升',
        'spring_mild':'春季出行恢复，轻外套、亲子运动与户外场景具备增长基础',
        'autumn_mild':'秋季运动与开学场景延续，轻外套、长裤及校园运动需求提升',
        'winter_mild':'冬季温和天气下，保暖基础款与室内运动场景仍需关注',
        'normal':'天气整体平稳，户外与亲子活动具备恢复基础',
    }
    return mapping.get(weather_business_type(key), mapping['normal'])

def weather_icon(key):
    t = weather_business_type(key)
    if t in ['storm','rain']: return '☔'
    if t in ['very_hot','hot']: return '☀️'
    if t in ['snow_ice','cold','winter_mild']: return '❄️'
    if t == 'wind': return '🌬️'
    return '🌤️'

# =========================================================
# DeepSeek
# =========================================================
def deepseek_client():
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key: return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url='https://api.deepseek.com')
    except Exception as e:
        print('DeepSeek client error:', repr(e)); return None

def extract_json(text):
    if not text: return None
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    try: return json.loads(text)
    except Exception: pass
    for pattern in [r'\[.*\]', r'\{.*\}']:
        m = re.search(pattern, text, re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: pass
    return None

def ask_deepseek_json(prompt, max_tokens=900):
    client = deepseek_client()
    if client is None: return None
    try:
        resp = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role':'system','content':'你是运动鞋服行业经营分析助手，只输出严格JSON，不要解释。'}, {'role':'user','content':prompt}],
            temperature=0.22,
            max_tokens=max_tokens,
        )
        return extract_json(resp.choices[0].message.content.strip())
    except Exception as e:
        print('DeepSeek JSON error:', repr(e)); return None

def ask_deepseek_text(prompt, max_tokens=220):
    client = deepseek_client()
    if client is None: return None
    try:
        resp = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role':'system','content':'你是专业、简洁、偏经营实战的运动鞋服零售分析师。'}, {'role':'user','content':prompt}],
            temperature=0.35,
            max_tokens=max_tokens,
        )
        return re.sub(r'\s+', '', resp.choices[0].message.content.strip())
    except Exception as e:
        print('DeepSeek text error:', repr(e)); return None

# =========================================================
# TOP5 + 竞品动态
# =========================================================
MAJOR_EVENT_WORDS = ['签约','代言','联名','战略合作','长期合作','合作伙伴','新品发布','发布会','旗舰店','实验室','换帅','CEO','总裁','董事长','收购','投资','中国战略','首发','限定','定制','入局','合作','开店','开业']
MAJOR_BRAND_WORDS = ['安踏','李宁','361','361度','361儿童','特步','耐克','Nike','阿迪达斯','Adidas','Puma','彪马','FILA','FILA KIDS','李宁YOUNG','安踏儿童','特步儿童','HOKA','昂跑','On','亚瑟士','ASICS','New Balance','lululemon','萨洛蒙','Salomon','始祖鸟','巴拉巴拉']
COMPETITOR_BRANDS = {'安踏儿童':'安踏儿童','FILA KIDS':'FILA KIDS','李宁YOUNG':'李宁YOUNG','特步儿童':'特步儿童','巴拉巴拉':'巴拉巴拉','Nike':'Nike','耐克':'Nike','阿迪达斯':'阿迪达斯','Adidas':'阿迪达斯','Puma':'Puma','彪马':'Puma','安踏':'安踏','李宁':'李宁','特步':'特步','361':'361','361度':'361','HOKA':'HOKA','昂跑':'On昂跑','On':'On昂跑','亚瑟士':'亚瑟士','ASICS':'亚瑟士'}
TRAFFIC_EVENT_WORDS = ['热梗','爆火','出圈','刷屏','小红书','抖音','社交媒体','种草','年轻人','顶流','爆款','出街','破圈']
INDUSTRY_CONTEXT_WORDS = ['运动','鞋','鞋服','童装','儿童','品牌','消费','零售','商场','门店','户外','跑步','防晒','凉感','618','大促']

def is_major_industry_event(title):
    title = clean_title(title)
    brand_event = any(b in title for b in MAJOR_BRAND_WORDS) and any(w in title for w in MAJOR_EVENT_WORDS)
    traffic_event = any(w in title for w in TRAFFIC_EVENT_WORDS) and any(w in title for w in INDUSTRY_CONTEXT_WORDS)
    management_event = any(b in title for b in MAJOR_BRAND_WORDS) and any(w in title for w in ['换帅','CEO','总裁','董事长','高管','管理层'])
    return brand_event or traffic_event or management_event

def major_event_score(item):
    title = clean_title(item.get('title',''))
    score = 0
    if is_major_industry_event(title): score += 120
    if any(b in title for b in MAJOR_BRAND_WORDS): score += 35
    if any(w in title for w in MAJOR_EVENT_WORDS): score += 60
    if any(w in title for w in TRAFFIC_EVENT_WORDS): score += 40
    if any(w in title for w in ['库里','Curry','谷爱凌','欧文','詹姆斯','东契奇','苏炳添','张伟丽']): score += 45
    return score

def topic_key(title):
    pure = re.sub(r'[，。！？、；：:,.!?（）()【】\[\]「」“”\"\'《》]', '', clean_title(title))
    if is_major_industry_event(pure):
        brands = [b for b in MAJOR_BRAND_WORDS if b in pure]
        events = [w for w in MAJOR_EVENT_WORDS + TRAFFIC_EVENT_WORDS if w in pure]
        people = [p for p in ['库里','Curry','谷爱凌','欧文','詹姆斯','东契奇','苏炳添','张伟丽'] if p in pure]
        key_parts = brands[:1] + people[:1] + events[:1]
        return '重大事件_' + ('_'.join(key_parts) if key_parts else pure[:10])
    groups = {
        '品牌PK':['PK','对比','谁更','成绩单','克阿迪'], '平台大促':['618','大促','预售','战报','抖音','天猫','京东','唯品','直播'],
        '防晒凉感':['防晒','凉感','速干','高温','夏天','防晒衣'], '户外跑步':['户外','跑步','跑鞋','骑行','露营','徒步','马拉松','越野跑'],
        '童装儿童':['童装','儿童','亲子','校园','童鞋','青少年','Kappa Kids'], '商圈客流':['商场','商圈','门店','客流','会员','奥莱','购物中心'],
        '宏观消费':['GDP','社零','消费','就业','收入','政策','补贴','内需'], '文旅出行':['文旅','旅游','暑期','出行','景区','亲子游'], 'AI科技':['AI','人工智能','机器人','智能','大模型','科技']
    }
    for k, words in groups.items():
        if any(w in pure for w in words): return k
    return pure[:12]

CATEGORY_RULES = {
    '电商平台': {'keywords':['618','双11','双十一','双12','大促','预售','电商','直播','抖音','小红书','种草','百亿补贴','战报','平台','店播'], 'tag':'大促/电商','logo':'大促','icon':'🛒','class':'logo-blue','desc':'平台流量与大促节奏变化，重点观察夏季品类曝光、直播转化与终端承接。'},
    '品牌竞争': {'keywords':['品牌','Nike','耐克','阿迪','安踏','李宁','特步','361','Kappa','HOKA','昂跑','亚瑟士','C位','市场份额','PK','签约','代言','联名','战略合作','实验室','换帅'], 'tag':'品牌竞争','logo':'品牌','icon':'🏷️','class':'logo-purple','desc':'品牌重大动作反映竞争重心变化，需关注产品心智、代言资产、渠道声量与终端转化。'},
    '童装儿童': {'keywords':['童装','儿童','亲子','校园','儿童运动','运动童装','Kids','KIDS','童鞋','青少年'], 'tag':'童装/儿童运动','logo':'童装','icon':'🧒','class':'logo-sky','desc':'儿童消费从单品购买转向亲子、校园、户外和运动场景综合经营。'},
    '天气消费': {'keywords':['高温','防晒','凉感','速干','暴雨','强对流','降雨','天气','防雨','夏日','夏季','降雪','结冰','低温','防滑','保暖'], 'tag':'天气/功能消费','logo':'天气','icon':'☀️','class':'logo-sky','desc':'天气变化影响客流和主推节奏，防晒、凉感、防雨、防滑及保暖品类需动态前置。'},
    '户外运动': {'keywords':['户外','骑行','露营','文旅','出行','夜经济','跑步','轻户外','徒步','马拉松','越野跑','赛事','训练','跑鞋'], 'tag':'户外/运动场景','logo':'户外','icon':'🚴','class':'logo-green','desc':'户外、跑步、骑行、赛事和夜间消费延伸运动场景，带动装备与亲子需求。'},
    '商圈零售': {'keywords':['商场','商圈','门店','客流','奥莱','折扣','会员','零售','本地生活','购物中心'], 'tag':'商圈/零售经营','logo':'商圈','icon':'🏬','class':'logo-dark','desc':'商圈活动、会员运营和折扣零售影响周末客流与终端转化效率。'},
    '宏观消费': {'keywords':['GDP','社零','社会消费品','消费','CPI','PPI','经济','收入','就业','信心','政策','补贴','以旧换新','内需'], 'tag':'宏观消费','logo':'宏观','icon':'📊','class':'logo-dark','desc':'宏观消费与收入预期影响零售信心，需关注客单、折扣和会员活跃变化。'},
    '文旅出行': {'keywords':['文旅','旅游','暑期','出行','景区','演唱会','赛事','周末','亲子游','酒店','交通'], 'tag':'文旅出行','logo':'文旅','icon':'🧳','class':'logo-green','desc':'文旅与城市出行带动周末客流，亲子、轻户外和功能鞋服存在连带机会。'},
    'AI科技': {'keywords':['AI','人工智能','机器人','智能','科技','算法','大模型','智能硬件'], 'tag':'AI科技','logo':'AI','icon':'🤖','class':'logo-blue','desc':'AI与智能硬件热点提升科技心智，可观察运动科技、内容种草和人群触达机会。'},
    '政策监管': {'keywords':['政策','监管','标准','质量','抽检','合规','补贴','消费券','促消费'], 'tag':'政策监管','logo':'政策','icon':'📌','class':'logo-red','desc':'政策与监管变化影响渠道节奏、消费者信心和终端活动设计。'},
}
fallback_by_category = {c:{'title':t,'source':s} for c,t,s in [
    ('电商平台','平台大促进入预热期，夏季功能品类承接需前置','平台资讯'),('品牌竞争','运动品牌竞争加剧，产品心智与渠道效率成为关键','行业观察'),('童装儿童','儿童运动消费场景外扩，亲子与校园需求继续升温','消费观察'),('天气消费','天气变化影响客流节奏，功能品类进入动态调整窗口','公开气象信息'),('户外运动','跑步、骑行与轻户外场景延续，运动装备需求扩张','消费观察'),('商圈零售','商圈活动与会员运营联动，周末客流修复仍需关注','商业观察'),('宏观消费','宏观消费信心分化，零售端需关注客单与折扣效率','宏观观察'),('文旅出行','文旅出行热度延续，亲子轻户外场景值得承接','文旅观察'),('AI科技','AI科技热度延续，运动品牌内容与效率工具值得关注','科技观察'),('政策监管','促消费与监管信息需跟踪，终端活动应兼顾效率与合规','政策观察')]}

def category_score(title, cat): return sum(1 for kw in CATEGORY_RULES[cat]['keywords'] if kw in title)
def infer_category(item):
    title = clean_title(item.get('title',''))
    if is_major_industry_event(title): return '品牌竞争'
    for c in ['电商平台','童装儿童','天气消费','户外运动','商圈零售','宏观消费','AI科技','文旅出行','政策监管']:
        if any(k in title for k in CATEGORY_RULES[c]['keywords']): return c
    return '品牌竞争' if any(b in title for b in MAJOR_BRAND_WORDS) else '商圈零售'

def item_score(item, cat):
    title, source = clean_title(item.get('title','')), str(item.get('source',''))
    score = category_score(title, cat) * 12 + major_event_score(item)
    for kw in ['618','大促','战报','防晒','凉感','速干','童装','儿童','亲子','跑鞋','户外','骑行','露营','商场','商圈','客流','会员','直播','小红书','抖音','Nike','耐克','阿迪','安踏','李宁','特步','HOKA','昂跑','亚瑟士','361','GDP','社零','消费','就业','政策','文旅','AI','出海']:
        if kw in title: score += 4
    for kw in ['比分','赛程','夺冠','冠军','主教练','球队','球员','转会','受伤']:
        if kw in title: score -= 18
    for src in ['界面新闻','36氪','赢商网','联商网','亿邦动力','电商报','新华网','澎湃新闻','证券时报','新京报','新浪财经','国家统计局','央视新闻','搜狐网','新浪新闻','观察者','每日经济新闻']:
        if src in source: score += 2
    try:
        pub = item.get('published_at') or item.get('pubDate') or item.get('date') or item.get('time') or ''
        dt = parsedate_to_datetime(pub) if pub else None
        if dt:
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            score += 35 if hours <= 12 else 25 if hours <= 24 else 10 if hours <= 48 else -30
        else: score -= 5
    except Exception: score -= 5
    return score

def build_top_news_item(item, cat=None, desc=None):
    title = short(item.get('title',''), 42)
    cat = cat or infer_category(item)
    rule = CATEGORY_RULES.get(cat, CATEGORY_RULES['商圈零售'])
    return {'title':title,'tag':rule['tag'],'source':item.get('source','公开资讯'),'desc':desc or rule['desc'],'logo':rule['logo'],'icon':rule['icon'],'class':rule['class'],'link':item.get('link') or item.get('url') or item.get('href') or '','published_at':item.get('published_at') or item.get('pubDate') or item.get('date') or item.get('time') or ''}

def pick_forced_major_news(limit=2):
    candidates = []
    for item in news_items[:80]:
        if not isinstance(item, dict): continue
        if major_event_score(item) >= 100:
            candidates.append((major_event_score(item)+int(item.get('score') or 0), item))
    candidates.sort(key=lambda x:(x[0], parse_news_time(x[1])), reverse=True)
    result, used_topics = [], set()
    for _, item in candidates:
        if len(result) >= limit: break
        tk = topic_key(item.get('title',''))
        if tk in used_topics: continue
        result.append(build_top_news_item(item, cat='品牌竞争', desc='品牌重大动作带来声量与产品心智变化，需关注终端转化和品类借势。'))
        used_topics.add(tk)
    return result

def pick_top_news_rule():
    used_titles, used_topics, used_cats, result = set(), set(), set(), []
    priority = ['品牌竞争','童装儿童','电商平台','天气消费','户外运动','商圈零售','宏观消费','文旅出行','AI科技','政策监管']
    candidates = []
    for item in news_items:
        if not isinstance(item, dict): continue
        title = clean_title(item.get('title',''))
        if not title: continue
        best_cat = max(priority, key=lambda c: item_score(item, c))
        score = item_score(item, best_cat)
        if score > 0: candidates.append((score, best_cat, item))
    candidates.sort(key=lambda x:x[0], reverse=True)
    for _, cat, item in candidates:
        if len(result) >= 5: break
        title, tk = short(item.get('title',''), 42), topic_key(item.get('title',''))
        if not title or title in used_titles or tk in used_topics: continue
        if cat == '电商平台' and cat in used_cats: continue
        result.append(build_top_news_item(item, cat=cat))
        used_titles.add(title); used_topics.add(tk); used_cats.add(cat)
    for cat in priority:
        if len(result) >= 5: break
        fb, rule = fallback_by_category[cat], CATEGORY_RULES[cat]
        tk = topic_key(fb['title'])
        if fb['title'] in used_titles or tk in used_topics: continue
        result.append({'title':fb['title'],'tag':rule['tag'],'source':fb['source'],'desc':rule['desc'],'logo':rule['logo'],'icon':rule['icon'],'class':rule['class'],'link':'','published_at':''})
        used_titles.add(fb['title']); used_topics.add(tk); used_cats.add(cat)
    return result[:5]

def merge_top_news(forced, selected):
    result, used_titles, used_topics, platform_count = [], set(), set(), 0
    for item in forced + selected:
        if len(result) >= 5: break
        title = clean_title(item.get('title',''))
        if not title: continue
        tk = topic_key(title)
        if title in used_titles or tk in used_topics: continue
        tag = item.get('tag','')
        if '大促' in tag or '电商' in tag:
            if platform_count >= 1: continue
            platform_count += 1
        result.append(item); used_titles.add(title); used_topics.add(tk)
    if len(result) < 5:
        for item in pick_top_news_rule():
            if len(result) >= 5: break
            title, tk = clean_title(item.get('title','')), topic_key(item.get('title',''))
            if title not in used_titles and tk not in used_topics:
                result.append(item); used_titles.add(title); used_topics.add(tk)
    return result[:5]

def pick_top_news_deepseek():
    forced = pick_forced_major_news(limit=2)
    if not titles:
        result = merge_top_news(forced, pick_top_news_rule())
    else:
        news_text = '\n'.join(f"{i+1}. {clean_title(item.get('title',''))}｜{item.get('source','')}" for i,item in enumerate(news_items[:80]) if isinstance(item,dict) and item.get('title'))
        allowed_categories = '、'.join(CATEGORY_RULES.keys())
        prompt = f"""
你是运动鞋服行业资讯筛选助手。请从以下新闻中选出5条最适合361°儿童经营管理部每日阅读的重点资讯。
要求：
1. 必须基于今日新闻生成，不得使用历史模板和固定排序；
2. 优先选择当天最新、信息增量最大、对经营最有参考价值的新闻；
3. 重大品牌事件必须优先：签约、代言、联名、战略合作、实验室、旗舰店、换帅、收购、投资、出圈、爆火；
4. 如果出现李宁、安踏、361、特步、耐克、阿迪达斯等品牌的重大动作，至少保留1条；
5. 不要让“618战报/抖音战报/大促战报”连续固定排第一，除非它确实是当天最重要新闻；
6. 如果多条新闻主题相似，只保留1条，优先发布时间更新、信息更具体的一条；
7. 覆盖范围要更广：品牌竞争、电商平台、童装儿童、天气消费、户外运动、商圈零售、宏观消费、文旅出行、AI科技、政策监管；
8. GDP、社零、就业、消费信心、促消费政策、文旅客流等宏观新闻，如果对零售经营有启示，可以入选；
9. 过滤纯体育比赛比分、球员转会、娱乐八卦；
10. 输出严格JSON数组，长度5；
11. 每项包含：title、category、reason；
12. category只能从以下选择：{allowed_categories}；
13. reason控制在28字以内，必须写经营启示，不要空话；
14. 5条应尽量分散在不同方向，不能4条都是品牌PK或618战报。
新闻：
{news_text}
"""
        arr = ask_deepseek_json(prompt, max_tokens=1100)
        if not isinstance(arr, list) or len(arr) < 3:
            selected = pick_top_news_rule()
        else:
            source_lookup = {clean_title(x.get('title','')):{'source':x.get('source','公开资讯'),'link':x.get('link') or x.get('url') or x.get('href') or '','published_at':x.get('published_at') or x.get('pubDate') or x.get('date') or x.get('time') or ''} for x in news_items if isinstance(x, dict)}
            selected, used_titles, used_topics, used_cats = [], set(), set(), set()
            for row in arr:
                if len(selected) >= 5: break
                if not isinstance(row, dict): continue
                title = short(row.get('title',''), 42)
                if not title: continue
                tk = topic_key(title)
                if title in used_titles or tk in used_topics: continue
                cat = clean_title(row.get('category','商圈零售'))
                rule = CATEGORY_RULES.get(cat, CATEGORY_RULES['商圈零售'])
                if cat == '电商平台' and cat in used_cats: continue
                source, link, published_at = '公开资讯', '', ''
                for raw_title, info in source_lookup.items():
                    if title[:10] in raw_title or raw_title[:10] in title:
                        source, link, published_at = info['source'], info['link'], info.get('published_at',''); break
                desc = short_cn(row.get('reason',''), 32) or rule['desc']
                selected.append({'title':title,'tag':rule['tag'],'source':source,'desc':desc,'logo':rule['logo'],'icon':rule['icon'],'class':rule['class'],'link':link,'published_at':published_at})
                used_titles.add(title); used_topics.add(tk); used_cats.add(cat)
            for item in pick_top_news_rule():
                if len(selected) >= 5: break
                tk = topic_key(item['title'])
                if item['title'] not in used_titles and tk not in used_topics:
                    selected.append(item); used_titles.add(item['title']); used_topics.add(tk)
        result = merge_top_news(forced, selected)
    try:
        TOP_NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOP_NEWS_FILE.write_text(json.dumps({'items': result}, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e: print('write top_news.json error:', repr(e))
    return result[:5]

def build_competitor_news(limit=5):
    result, used_titles = [], set()
    for item in news_items:
        if not isinstance(item, dict): continue
        title = clean_title(item.get('title',''))
        if not title or title in used_titles: continue
        matched_brand = None
        for keyword, brand in COMPETITOR_BRANDS.items():
            if keyword in title:
                matched_brand = brand; break
        if not matched_brand: continue
        if any(w in title for w in ['比分','赛程','夺冠','冠军','主教练','球队','球员','转会','受伤','涨停','跌停','龙虎榜']): continue
        score = int(item.get('score') or 0) + major_event_score(item)
        if any(w in title for w in ['签约','代言','联名','新品','旗舰店','开业','实验室','618','战报','防晒','童装','儿童','小红书','抖音']): score += 80
        result.append({'brand':matched_brand,'title':short_cn(title,30),'source':item.get('source','公开资讯'),'score':score,'published_at':item.get('published_at') or item.get('pubDate') or item.get('date') or item.get('time') or '','link':item.get('link') or item.get('url') or item.get('href') or ''})
        used_titles.add(title)
    result = sorted(result, key=lambda x:x.get('score',0), reverse=True)[:limit]
    try:
        COMPETITOR_NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
        COMPETITOR_NEWS_FILE.write_text(json.dumps({'items':result}, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e: print('write competitor_news.json error:', repr(e))
    return result

top_news = pick_top_news_deepseek()
competitor_news = build_competitor_news(limit=5)

# =========================================================
# 区域经营雷达
# =========================================================
region_map = {
    'east': {'name':'华东','city':'上海/江苏/浙江','weather_key':'east','keywords':['上海','江苏','浙江','南京','苏州','杭州','宁波','无锡','合肥','安徽']},
    'central': {'name':'华中','city':'湖北/湖南/江西','weather_key':'east','keywords':['湖北','湖南','江西','武汉','长沙','南昌','郑州','河南']},
    'south': {'name':'华南','city':'广东/广西','weather_key':'south','keywords':['广东','广西','广州','深圳','佛山','东莞','南宁','福建','厦门','福州']},
    'southwest': {'name':'西南','city':'四川/重庆/贵州','weather_key':'southwest','keywords':['四川','重庆','贵州','云南','成都','贵阳','昆明']},
    'northwest': {'name':'西北','city':'陕西/甘肃/宁夏','weather_key':'northwest','keywords':['陕西','甘肃','宁夏','新疆','西安','兰州','银川','乌鲁木齐']},
}
THEME_KEYWORDS = {'足球运动':['足球','足弓','球鞋','训练','青训','实验室'],'赛事经济':['赛事','比赛','马拉松','运动会','体育节'],'文旅客流':['文旅','旅游','景区','夜经济','出行','商旅'],'商圈客流':['商场','商圈','购物中心','客流','门店','奥莱'],'防晒经济':['防晒','防晒衣','高温','凉感','速干','冰感'],'亲子运动':['儿童','童装','亲子','校园','青少年','童鞋'],'直播电商':['直播','抖音','京东','天猫','小红书','618','大促'],'AI科技':['AI','人工智能','智能','机器人','算法','大模型'],'县域消费':['县域','下沉','小城','低线','县城'],'情绪消费':['情绪','悦己','松弛感','疗愈','治愈']}

def get_region_news(cfg, max_n=10):
    local = []
    for item in news_items:
        if not isinstance(item, dict): continue
        title = clean_title(item.get('title',''))
        if not title: continue
        item_region = item.get('region','')
        if item_region == cfg['name'] or any(k in title for k in cfg['keywords']):
            local.append({'title':title,'source':str(item.get('source','')),'link':str(item.get('link') or item.get('url') or item.get('href') or '')})
    return local[:max_n]

def detect_region_theme(local_news):
    text = ' '.join([x.get('title','') for x in local_news])
    scores = {theme:sum(10 for kw in keywords if kw in text) for theme, keywords in THEME_KEYWORDS.items()}
    best_theme = max(scores, key=scores.get)
    return best_theme if scores.get(best_theme,0) > 0 else '区域消费'

def build_region_payload():
    payload = {}
    for key, cfg in region_map.items():
        local_news = get_region_news(cfg, max_n=8)
        region_news = []
        for item in local_news:
            title = clean_title(item.get('title',''))
            if title and title not in region_news: region_news.append(title)
        payload[key] = {'region':cfg['name'],'cities':cfg['city'],'weather':{'summary':weather_desc(cfg['weather_key']),'day1':weather_day_label(cfg['weather_key'],0),'day2':weather_day_label(cfg['weather_key'],1),'day3':weather_day_label(cfg['weather_key'],2),'type':weather_business_type(cfg['weather_key'])},'news_titles':region_news[:4],'theme':detect_region_theme(local_news)}
    return payload

def build_region_reports_rule():
    reports, actions = {}, {}
    for region, cfg in region_map.items():
        theme = detect_region_theme(get_region_news(cfg, max_n=8))
        reports[region] = {'change':f'{theme}带动区域消费变化','impact':f"{cfg['city']}客流与消费场景受新闻和天气共同影响",'focus':'商品机会'}
        actions[region] = '结合新闻与天气调整主推陈列'
    return reports, actions

def build_region_reports_deepseek():
    fallback_reports, fallback_actions = build_region_reports_rule()
    region_payload = build_region_payload()
    top_news_text = '\n'.join([f"{i+1}. {x['title']}｜{x['tag']}" for i,x in enumerate(top_news[:5])])
    global_news_text = '\n'.join(titles[:12])
    prompt = f"""
你是361°儿童总部经营管理部的区域经营分析师。请为5个区域生成“区域经营雷达”。
输出严格JSON对象，不要解释。key必须为：east, central, south, southwest, northwest。
每个区域必须包含：hot：18-26字；flow：24-42字；focus_type：4-12字；action：18-36字。
要求：必须优先使用区域数据里的news_titles、weather、theme；focus_type和action必须根据区域当天新闻、天气、theme自动判断；action必须是经营动作；不要编造不存在的区域城市事件。
今日TOP资讯：
{top_news_text}
全国新闻：
{global_news_text}
区域数据：
{json.dumps(region_payload, ensure_ascii=False)}
"""
    obj = ask_deepseek_json(prompt, max_tokens=1800)
    print('region deepseek result:', obj)
    if not isinstance(obj, dict): return fallback_reports, fallback_actions
    reports, actions = {}, {}
    for region in region_map.keys():
        row = obj.get(region,{})
        if not isinstance(row, dict):
            reports[region] = fallback_reports[region]; actions[region] = fallback_actions[region]; continue
        hot = short_cn(row.get('hot', fallback_reports[region]['change']), 26)
        flow = short_cn(row.get('flow', fallback_reports[region]['impact']), 60)
        focus_type = short_cn(row.get('focus_type', fallback_reports[region]['focus']), 12)
        action = clean_title(row.get('action',''))
        action = re.sub(r'^建议[:：\s]*','', action)
        action = re.sub(r'^[0-9]+\.\s*','', action)
        action = short_cn(action, 36)
        if len(action) < 8: action = fallback_actions.get(region,'结合新闻与天气调整主推陈列')
        if action in actions.values(): action = short_cn(f'{focus_type}差异化陈列与会员触达', 30)
        reports[region] = {'change':hot,'impact':flow,'focus':focus_type}
        actions[region] = action
    return reports, actions

reports, actions = build_region_reports_deepseek()

def news_heat_score(keywords):
    score = 0
    for t in titles:
        if any(k in t for k in keywords): score += 5
        if any(k in t for k in ['618','大促','防晒','凉感','童装','儿童','亲子','商场','商圈','客流','户外','骑行','赛事','跑步','马拉松','GDP','社零','消费','就业','政策','文旅','AI']): score += 1
    return min(score,25)
def business_keyword_score():
    score = 0
    for k in ['防晒','凉感','童装','儿童','亲子','618','商场','商圈','客流','户外','骑行','小红书','抖音','保暖','防滑','赛事','跑步','马拉松','GDP','社零','消费','就业','政策','文旅','AI','出海']:
        if k in joined: score += 2
    return min(score,20)
def seasonal_weather_score(weather_key):
    t = weather_business_type(weather_key)
    base = {'snow_ice':55,'storm':50,'very_hot':48,'cold':38,'rain':35,'hot':32,'wind':28,'spring_mild':18,'autumn_mild':20,'winter_mild':22,'normal':15}.get(t,15)
    return min(base + min(weather_risk_raw(weather_key)*0.25,18),65)
def total_region_score(weather_key, region_keywords): return min(seasonal_weather_score(weather_key)+news_heat_score(region_keywords)+business_keyword_score(),100)
scores = {r:total_region_score(c['weather_key'], c['keywords']) for r,c in region_map.items()}
sorted_regions = sorted(scores.keys(), key=lambda r:scores[r], reverse=True)
stars = {}
for idx,r in enumerate(sorted_regions):
    s = scores[r]
    stars[r] = '★★★' if idx <= 2 and s >= 62 else '★★' if s >= 45 else '★'
def star_class(star): return 'star-red' if str(star)=='★★★' else 'star-orange' if str(star)=='★★' else 'star-blue'

# =========================================================
# 顶部摘要、预警、趋势、热词
# =========================================================
def make_today_insight_rule():
    if any(k in joined for k in ['签约','代言','联名','战略合作','实验室','换帅']): return '运动品牌重大动作增多，代言资产、产品科技与渠道声量成为竞争焦点。'
    if any(k in joined for k in ['GDP','社零','消费','就业','收入','政策','内需']): return '宏观消费与平台流量共同影响零售节奏，价格带、客流与功能品类需同步跟踪。'
    if any(k in joined for k in ['618','战报','大促','预售']): return '618战报持续释放，运动品牌线上增长与夏季品类竞争同步升温。'
    if any(k in joined for k in ['防晒','凉感','速干','高温']): return '夏季功能消费升温，防晒、凉感与速干品类成为短期热点。'
    if any(k in joined for k in ['户外','骑行','露营','跑步','马拉松']): return '泛运动场景继续扩张，户外、跑步与骑行热度延续。'
    if any(k in joined for k in ['童装','儿童','亲子','校园']): return '儿童运动消费场景继续外扩，亲子与校园需求保持活跃。'
    return '运动鞋服行业热点分化，平台、天气与场景消费共同影响短期趋势。'

def make_today_insight_deepseek():
    prompt = f"""请基于以下新闻，写一句今日行业判断。要求：45字以内，不写门店执行动作，不要口号；如有签约、代言、联名、战略合作、实验室、换帅等重大品牌事件，要优先体现。
新闻：
{chr(10).join(titles[:30])}
"""
    text = ask_deepseek_text(prompt, max_tokens=120)
    return text[:70] if text else make_today_insight_rule()

def make_ai_summary_rule():
    parts = []
    if any(k in joined for k in ['签约','代言','联名','战略合作','实验室','换帅']): parts.append('品牌重大动作带动声量竞争和产品心智变化')
    if any(k in joined for k in ['GDP','社零','消费','就业','收入','政策','内需']): parts.append('宏观消费与收入预期影响零售信心')
    if any(k in joined for k in ['618','大促','预售','战报']): parts.append('大促与平台流量仍是短期主线')
    if any(k in joined for k in ['防晒','凉感','速干','高温']): parts.append('防晒、凉感、速干等夏季功能品类升温')
    if any(k in joined for k in ['童装','儿童','亲子','校园']): parts.append('儿童运动与亲子校园场景延续')
    if any(k in joined for k in ['户外','骑行','露营','跑步','赛事','文旅']): parts.append('轻户外与文旅场景带动鞋服装备关注')
    if any(weather_business_type(k) in ['rain','storm'] for k in ['north','east','south','southwest','northwest']): parts.append('降雨天气可能影响区域客流')
    if not parts: parts.append('今日行业信息整体平稳，关注商圈客流、商品节奏和区域差异')
    return '；'.join(parts[:4]) + '。'

def make_ai_summary_deepseek():
    news_text = '\n'.join(titles[:35])
    comp_text = '\n'.join([f"{x.get('brand','')}｜{x.get('title','')}" for x in competitor_news[:5]])
    weather_text = '；'.join([weather_desc(k) for k in ['north','east','south','southwest','northwest']])
    prompt = f"""你是361°儿童经营管理部的行业情报分析师。请基于新闻、竞品动态和天气生成一段90字以内AI经营摘要。要有明确判断，不要罗列；重大品牌事件优先体现；不要口号。
新闻：
{news_text}
竞品动态：
{comp_text}
天气：
{weather_text}
"""
    text = ask_deepseek_text(prompt, max_tokens=180)
    return text[:150] if text else make_ai_summary_rule()

today_insight = make_today_insight_deepseek()
ai_summary = make_ai_summary_deepseek()

def make_ai_warnings():
    news_text = '\n'.join(titles[:30])
    comp_text = '\n'.join([f"{x.get('brand','')}｜{x.get('title','')}" for x in competitor_news[:5]])
    weather_text = '；'.join([weather_desc(k) for k in ['north','east','south','southwest','northwest']])
    prompt = f"""
你是361°儿童经营管理负责人。请基于今日行业新闻、竞品动态、全国天气、电商大促、区域消费趋势、重大品牌事件、宏观消费、政策、社零/GDP、文旅出行、AI科技热点，生成3条每日动态经营关注点，必须随当天新闻变化。
要求：输出严格JSON数组；每条25-50字；像总部经营预警；不要空话；必须具体到客流、品类、会员、直播、天气、商圈、区域、价格带、品牌声量或政策影响；必须是完整句子；如有签约、代言、联名、发布会、爆火、出圈等事件，至少1条围绕该事件。
新闻：
{news_text}
竞品动态：
{comp_text}
天气：
{weather_text}
"""
    arr = ask_deepseek_json(prompt, max_tokens=500)
    fallback_pool = ['重点品牌事件升温，需关注搜索热度、竞品动作和终端话术承接。','平台大促与直播流量波动，需关注核心SKU库存、价格带和同款转化。','天气变化影响到店节奏，需关注防晒、防雨、防滑和室内运动场景。','儿童运动与亲子场景升温，门店需强化会员触达和试穿转化。','商圈活动与区域客流分化，重点门店需动态调整陈列和导购重点。','宏观消费预期仍有分化，需关注高性价比商品、折扣效率和客单变化。','AI与内容平台热点升温，需关注小红书、抖音种草和商品卖点表达。']
    if not isinstance(arr, list): return fallback_pool[:3]
    result = []
    for x in arr:
        text = ''
        if isinstance(x, dict): text = x.get('risk') or x.get('warning') or x.get('content') or x.get('text') or x.get('desc') or x.get('title') or ''
        else: text = str(x)
        text = clean_title(text)
        for old in ['【预警：','】','{','}',"'risk':",'"risk":',"'warning':",'"warning":',"'content':",'"content":']:
            text = text.replace(old,'')
        if text and text not in result: result.append(text)
    while len(result) < 3: result.append(fallback_pool[len(result)])
    return result[:3]
warnings = make_ai_warnings()

def build_ai_trends_rule():
    checks = [(['签约','代言','联名','战略合作','实验室','换帅'], {'title':'品牌事件带动声量','desc':'签约、合作和科技实验室等动作提升品牌关注，门店需承接产品心智与话题热度。','tag':'品牌竞争'}),(['GDP','社零','消费','就业','政策','收入'], {'title':'宏观消费影响客单','desc':'消费与收入预期变化影响客单和折扣敏感度，门店需优化价格带与会员转化。','tag':'宏观趋势'}),(['618','大促','预售','直播','抖音','小红书'], {'title':'平台热度外溢门店','desc':'大促和内容种草带动比价与试穿需求，需承接直播同款和核心爆款。','tag':'平台趋势'}),(['防晒','凉感','速干','高温','降雨','防雨'], {'title':'天气驱动功能陈列','desc':'天气变化带动防晒、凉感、防雨与速干需求，门店陈列需随区域动态调整。','tag':'天气趋势'}),(['童装','儿童','亲子','校园'], {'title':'亲子校园带动连带','desc':'儿童运动、亲子和校园场景带动套装与童鞋组合，导购需强化搭配转化。','tag':'儿童趋势'}),(['户外','骑行','露营','文旅','出行','赛事'], {'title':'文旅户外延伸场景','desc':'文旅、骑行和轻户外带动出行装备需求，帽包、防晒和舒适鞋履可连带。','tag':'场景趋势'}),(['AI','人工智能','机器人','智能','科技'], {'title':'AI热点带动科技心智','desc':'AI和智能硬件话题提升年轻家庭关注，运动科技和功能面料卖点需加强表达。','tag':'科技趋势'})]
    candidates = [item for keys,item in checks if any(k in joined for k in keys)]
    fallback = [{'title':'区域客流需要细分','desc':'天气、商圈活动与平台热点影响到店节奏，重点商圈需强化会员和试穿转化。','tag':'客流趋势'},{'title':'夏季商品节奏前置','desc':'夏季功能品类进入高频曝光阶段，防晒、凉感、速干和舒适鞋履需前置陈列。','tag':'季节趋势'},{'title':'会员运营承接流量','desc':'线上种草和商圈活动带来短期客流，门店需用会员活动提升复购和转化。','tag':'会员趋势'},{'title':'亲子出行关注提升','desc':'周末亲子与户外出行场景仍有需求，童装、童鞋和帽包配件可组合推荐。','tag':'亲子趋势'}]
    result = []
    for x in candidates + fallback:
        if len(result) >= 4: break
        if x['title'] not in [r['title'] for r in result]: result.append(x)
    return result[:4]

def build_ai_trends():
    news_text = '\n'.join(titles[:40])
    comp_text = '\n'.join([f"{x.get('brand','')}｜{x.get('title','')}" for x in competitor_news[:5]])
    weather_text = '；'.join([weather_desc(k) for k in ['north','east','south','southwest','northwest']])
    prompt = f"""你是361°儿童总部经营管理部经营分析负责人。请基于今日行业新闻、竞品动态、天气变化、电商平台动态、运动与户外消费、商圈客流、重大品牌事件、宏观消费/GDP社零/就业收入/促消费政策、文旅出行、AI科技、品牌竞争，生成4条“经营观察与动作建议”。输出严格JSON数组，长度4；每条包含title、desc、tag；title10-18字，desc30-48字，tag4-6字；不要空话。
新闻：
{news_text}
竞品动态：
{comp_text}
天气：
{weather_text}
"""
    arr = ask_deepseek_json(prompt, max_tokens=1200)
    if not isinstance(arr, list) or len(arr) < 4: return build_ai_trends_rule()
    result, bad_titles = [], ['大促节点提前蓄水','儿童运动场景扩张','商圈客流恢复分化','夏季功能品类升温']
    for row in arr:
        if len(result) >= 4: break
        if not isinstance(row, dict): continue
        title, desc, tag = short_cn(row.get('title',''),18), short_cn(row.get('desc',''),80), short_cn(row.get('tag',''),8)
        if not title or title in bad_titles: continue
        result.append({'title':title,'desc':desc,'tag':tag})
    if len(result) < 4:
        for item in build_ai_trends_rule():
            if len(result) >= 4: break
            if item['title'] not in [r['title'] for r in result]: result.append(item)
    return result[:4]
trend_items = build_ai_trends()

KEYWORD_MAP = {'签约':'品牌签约','代言':'品牌代言','联名':'联名合作','战略合作':'战略合作','实验室':'运动科技','换帅':'品牌换帅','库里':'库里','Curry':'库里','谷爱凌':'谷爱凌','抖音':'抖音直播','直播':'直播带货','店播':'店播','达人':'达人矩阵','小红书':'小红书种草','种草':'内容种草','618':'618','成绩单':'618战报','战报':'618战报','品牌':'品牌站位','C位':'品牌站位','大促':'大促预售','预售':'大促预售','防晒':'防晒品类','防晒衣':'防晒衣','凉感':'凉感科技','速干':'速干T','短裤':'短裤','短袖':'短袖T恤','T恤':'运动T恤','卫衣':'卫衣','冲锋衣':'冲锋衣','羽绒服':'羽绒服','运动凉鞋':'运动凉鞋','凉鞋':'运动凉鞋','跑鞋':'专业跑鞋','户外鞋':'户外鞋','童鞋':'儿童运动鞋','面料':'功能面料','科技':'运动科技','童装':'运动童装','儿童':'儿童运动','亲子':'亲子运动','校园':'校园体育','商场':'商场活动','商圈':'商圈客流','客流':'客流修复','门店':'门店陈列','会员':'会员运营','户外':'户外运动','骑行':'城市骑行','露营':'露营经济','文旅':'文旅客流','夜经济':'夜经济','赛事':'体育赛事','跑步':'跑步经济','马拉松':'马拉松','耐克':'Nike','Nike':'Nike','阿迪达斯':'阿迪达斯','Adidas':'阿迪达斯','亚瑟士':'亚瑟士','昂跑':'On昂跑','HOKA':'HOKA','安踏':'安踏','李宁':'李宁','特步':'特步','361':'361儿童','巴拉巴拉':'巴拉巴拉','消费分层':'消费分层','理性消费':'理性消费','悦己':'悦己消费','情绪消费':'情绪消费','防雨':'防雨装备','低温':'保暖','保暖':'保暖','防滑':'防滑鞋','AI':'AI','人工智能':'人工智能','机器人':'智能机器人','国际化':'国际化','出海':'出海','00后':'00后','年轻人':'年轻人','体育精神':'体育精神','健康':'健康生活','消费':'消费趋势','政策':'政策信号','就业':'就业趋势','暑期':'暑期消费','旅游':'文旅消费','GDP':'GDP','社零':'社零','银发':'银发经济','下沉':'下沉市场'}

def build_words_rule():
    counter = Counter()
    top_joined = ' '.join([item['title'] for item in top_news if item.get('title')])
    comp_joined = ' '.join([item['title'] for item in competitor_news if item.get('title')])
    for raw, mapped in KEYWORD_MAP.items():
        if raw in top_joined: counter[mapped] += 5
        if raw in comp_joined: counter[mapped] += 4
    for idx,t in enumerate(titles[:80]):
        weight = 5 if idx < 10 else 3
        for raw, mapped in KEYWORD_MAP.items():
            if raw in t: counter[mapped] += weight
    for key in ['north','east','south','southwest','northwest']:
        sig = weather_desc(key)
        for raw, mapped in KEYWORD_MAP.items():
            if raw in sig: counter[mapped] += 2
    for w in ['消费趋势','儿童运动','品牌站位','客流修复','618','双11','AI','防晒品类']:
        if w in counter: counter[w] *= 0.45
    seasonal = {'spring':['春季出行','轻外套','亲子运动','校园体育','城市骑行','山系穿搭','运动T恤'],'summer':['防晒品类','凉感科技','速干T','短裤','运动凉鞋','透气跑鞋','618','防晒衣'],'autumn':['开学季','校园体育','卫衣','轻外套','户外运动','99大促','城市骑行'],'winter':['保暖','防滑鞋','童鞋','室内运动','训练装备','羽绒服','冲锋衣']}.get(SEASON, [])
    broad = ['AI','出海','国际化','体育精神','年轻人','情绪消费','城市骑行','健康生活','智能机器人','运动最解压','直播带货','店播增长','会员裂变','多品牌','功能面料','校园体育','亲子出行','智能穿戴','运动社交','户外露营','山系穿搭','速干T','防晒衣','凉感科技','碳板跑鞋','透气跑鞋','新消费','性价比','松弛感','悦己','国潮','她经济','下沉市场','银发经济','GDP','社零','暑假消费']
    candidate_words = [w for w,_ in counter.most_common()]
    if len(candidate_words) < 12: candidate_words += seasonal
    if len(candidate_words) < 16: candidate_words += random.sample(broad, min(6, len(broad)))
    head, tail = candidate_words[:10], candidate_words[10:]
    random.shuffle(head); candidate_words = head + tail
    words = []
    for w in candidate_words:
        if w and len(w) <= 8 and w not in words: words.append(w)
        if len(words) >= 18: break
    return words[:18]

def build_words_deepseek():
    news_text = '\n'.join([clean_title(x.get('title','')) for x in news_items[:50] if isinstance(x,dict)])
    top_text = '\n'.join([f"{i+1}. {x['title']}｜{x['tag']}" for i,x in enumerate(top_news)])
    comp_text = '\n'.join([f"{x.get('brand','')}｜{x.get('title','')}" for x in competitor_news])
    weather_text = '；'.join([weather_desc(k) for k in ['north','east','south','southwest','northwest']])
    prompt = f"""你是运动鞋服行业情报系统。请基于今日行业新闻、TOP重点资讯、竞品动态、全国天气、当前消费趋势、宏观消费、GDP/社零、就业收入、文旅出行、AI科技、重大品牌事件、社会热点，生成22个适合“行业热词雷达”的真实热词。输出严格JSON数组；每个词2-8字；品牌词最多3个；更多生成趋势词、情绪词、消费词、经营词。
TOP资讯：
{top_text}
竞品动态：
{comp_text}
新闻：
{news_text}
天气：
{weather_text}
"""
    arr = ask_deepseek_json(prompt, max_tokens=650)
    words = []
    if isinstance(arr, list):
        for w in arr:
            w = clean_title(str(w))
            if 2 <= len(w) <= 8 and w not in ['儿童运动','品牌站位','户外运动','运动消费','消费趋势','行业趋势','运动品牌','运动行业'] and w not in words:
                words.append(w)
    for w in build_words_rule():
        if len(words) >= 18: break
        if w not in words: words.append(w)
    return words[:18]
words = build_words_deepseek()

# =========================================================
# 数据填充
# =========================================================
data = {'title':'运动品牌行业资讯日报','subtitle':'每日精选 · 洞察趋势 · 辅助决策','today_insight':today_insight,'ai_summary':ai_summary,'warning1':warnings[0],'warning2':warnings[1],'warning3':warnings[2],'date':today.strftime('%Y-%m-%d'),'weekday':weekday_map[today.weekday()],'update_time':today.strftime('%H:%M'),'monitor_count':str(max(len(news_items), random.randint(150,260))),'rss_count':str(max(min(len(news_items),99), random.randint(35,80))),'focus_count':'5','weather_heat_class':map_heat_class(),'east_icon':weather_icon('east'),'central_icon':weather_icon('east'),'south_icon':weather_icon('south'),'southwest_icon':weather_icon('southwest'),'northwest_icon':weather_icon('northwest'),'north_heat':heat_class_by_weather('north'),'east_heat':heat_class_by_weather('east'),'south_heat':heat_class_by_weather('south'),'northwest_heat':heat_class_by_weather('northwest'),'central_heat':heat_class_by_weather('east'),'weather_range':f'{md(today)} ~ {md(day3)}','day1':md(today),'day2':md(day2),'day3':md(day3),'weather_north':weather_desc('north'),'weather_east':weather_desc('east'),'weather_south':weather_desc('south'),'weather_southwest':weather_desc('southwest'),'weather_northwest':weather_desc('northwest'),'north_day1':weather_day_label('north',0),'north_day2':weather_day_label('north',1),'north_day3':weather_day_label('north',2),'east_day1':weather_day_label('east',0),'east_day2':weather_day_label('east',1),'east_day3':weather_day_label('east',2),'south_day1':weather_day_label('south',0),'south_day2':weather_day_label('south',1),'south_day3':weather_day_label('south',2),'southwest_day1':weather_day_label('southwest',0),'southwest_day2':weather_day_label('southwest',1),'southwest_day3':weather_day_label('southwest',2),'northwest_day1':weather_day_label('northwest',0),'northwest_day2':weather_day_label('northwest',1),'northwest_day3':weather_day_label('northwest',2),'generate_time':today.strftime('%Y-%m-%d %H:%M')}

for region in ['east','central','south','southwest','northwest']:
    data[f'{region}_city'] = region_map[region]['city']
    data[f'{region}_hot'] = reports[region].get('change','')
    data[f'{region}_flow'] = reports[region].get('impact','')
    data[f'{region}_focus'] = reports[region].get('focus','商品机会')
    action_text = clean_title(actions.get(region,''))
    action_text = action_text.replace('建议：','').replace('建议:','')
    if len(action_text) < 6: action_text = '结合新闻与天气调整主推陈列'
    data[f'{region}_action'] = action_text
    data[f'{region}_star'] = stars[region]
    data[f'{region}_star_class'] = star_class(stars[region])

for i,item in enumerate(trend_items, start=1):
    data[f'trend{i}_title'] = item['title']; data[f'trend{i}_desc'] = item['desc']; data[f'trend{i}_tag'] = item['tag']
for i,item in enumerate(top_news, start=1):
    data[f'top{i}_title'] = item['title']; data[f'top{i}_tag'] = item['tag']
    pub_time = item.get('published_at') or item.get('pubDate') or item.get('date') or item.get('time') or ''
    data[f'top{i}_time'] = clean_title(pub_time)[:16] if pub_time else today.strftime('%m-%d %H:%M')
    data[f'top{i}_source'] = item['source']; data[f'top{i}_desc'] = item['desc']; data[f'top{i}_logo'] = item['logo']; data[f'top{i}_icon'] = item['icon']; data[f'top{i}_logo_class'] = item['class']
for i in range(1,6):
    item = competitor_news[i-1] if i <= len(competitor_news) else {}
    data[f'comp{i}_brand'] = item.get('brand',''); data[f'comp{i}_title'] = item.get('title',''); data[f'comp{i}_source'] = item.get('source',''); data[f'comp{i}_time'] = clean_title(item.get('published_at',''))[:16] if item.get('published_at') else ''
for i,word in enumerate(words, start=1): data[f'word{i}'] = word
for key,value in data.items(): template = template.replace('{{' + key + '}}', str(value))

# =========================================================
# 保存历史数据
# =========================================================
history_dir = Path('output/history'); history_dir.mkdir(parents=True, exist_ok=True)
history_data = {'date':today.strftime('%Y-%m-%d'),'weekday':weekday_map[today.weekday()],'generate_time':today.strftime('%Y-%m-%d %H:%M'),'today_insight':today_insight,'ai_summary':ai_summary,'top_news': top_news,
'competitor_news': competitor_news,
'warnings': warnings,'region_reports':{region:{'name':region_map[region]['name'],'city':region_map[region]['city'],'hot':data.get(f'{region}_hot',''),'flow':data.get(f'{region}_flow',''),'focus':data.get(f'{region}_focus',''),'action':data.get(f'{region}_action',''),'star':data.get(f'{region}_star','')} for region in ['east','central','south','southwest','northwest']},'trend_items':trend_items,'words':words,'weather':{'north':weather_desc('north'),'east':weather_desc('east'),'south':weather_desc('south'),'southwest':weather_desc('southwest'),'northwest':weather_desc('northwest')}}
history_file = history_dir / f"{today.strftime('%Y-%m-%d')}.json"
history_file.write_text(json.dumps(history_data, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'top news saved: {TOP_NEWS_FILE}')
print(f'competitor news saved: {COMPETITOR_NEWS_FILE}')
print(f'history saved: {history_file}')
OUTPUT_HTML.write_text(template, encoding='utf-8')
print('daily-report-filled.html generated.')
