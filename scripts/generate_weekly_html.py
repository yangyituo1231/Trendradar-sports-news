from pathlib import Path
from datetime import datetime
import json, re, html
from collections import Counter

WEEKLY_FILE = Path('output/weekly/latest_week.json')
ANALYSIS_FILE = Path('output/weekly/weekly_analysis.json')
PRODUCT_SIGNAL_FILE = Path('output/products/latest_product_signals.json')
OUTPUT_DIR = Path('output/weekly')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_HTML = OUTPUT_DIR / 'weekly_report.html'


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception as e:
        print(f'load json error: {path} {e!r}')
        return default


def raw(x):
    return re.sub(r'\s+', ' ', str(x or '').replace('\n', ' ')).strip()


def esc(x):
    return html.escape(raw(x))


def short(x, n=42):
    s = raw(x)
    return esc(s if len(s) <= n else s[:n] + '...')


def as_list(x):
    return x if isinstance(x, list) else []


def get_list(d, key):
    return as_list(d.get(key, [])) if isinstance(d, dict) else []


def pair_rows(items, name_key):
    out = []
    for it in items or []:
        if isinstance(it, (list, tuple)) and len(it) >= 2:
            out.append({name_key: it[0], 'count': it[1]})
        elif isinstance(it, dict):
            out.append(it)
    return out


def parse_ai(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    txt = raw(value)
    txt = re.sub(r'^```json\s*', '', txt)
    txt = re.sub(r'^```\s*', '', txt)
    txt = re.sub(r'\s*```$', '', txt)
    try:
        return json.loads(txt)
    except Exception:
        return {'raw': txt}


def sentence(item):
    if isinstance(item, dict):
        title = item.get('theme') or item.get('title') or ''
        heat = item.get('heat', '')
        body = item.get('suggestion') or item.get('risk') or item.get('action') or item.get('desc') or ''
        prefix = f'ã{esc(title)}ã' if title else ''
        heat_text = f'ç­åº¦{esc(heat)}ã' if heat != '' else ''
        return prefix + heat_text + esc(body)
    return esc(item)


def render_list(items, limit=5):
    return ''.join(f'<li>{sentence(x)}</li>' for x in as_list(items)[:limit])


weekly = load_json(WEEKLY_FILE, {})
analysis = load_json(ANALYSIS_FILE, {})
product_signal_file = load_json(PRODUCT_SIGNAL_FILE, {})

summary = analysis.get('summary', {}) if isinstance(analysis, dict) else {}
summary = summary if isinstance(summary, dict) else {}
news = analysis.get('news', {}) if isinstance(analysis, dict) else {}
news = news if isinstance(news, dict) else {}
product_signals = analysis.get('product_signals', {}) if isinstance(analysis, dict) else {}
if not isinstance(product_signals, dict) or not product_signals:
    product_signals = product_signal_file if isinstance(product_signal_file, dict) else {}

days = get_list(weekly, 'days')
if not days and summary.get('date_range'):
    days = [summary.get('date_range')]

news_pool = news.get('news_pool', []) if isinstance(news, dict) else []
if not isinstance(news_pool, list) or not news_pool:
    news_pool = get_list(weekly, 'top_news')

keywords = analysis.get('keywords', []) if isinstance(analysis, dict) else []
if not isinstance(keywords, list):
    keywords = get_list(weekly, 'keywords')

regions = analysis.get('regions') or analysis.get('region_analysis') or []
regions = regions if isinstance(regions, list) else []
opportunities = get_list(analysis, 'opportunities')
risks = get_list(analysis, 'risks')
actions = get_list(analysis, 'actions')
product_suggestions = get_list(analysis, 'product_suggestions')
ai = parse_ai(analysis.get('ai_judgement') or summary.get('ai_judgement') or '')

signal_count = int(product_signals.get('signal_count') or len(product_signals.get('signals', [])) or 0)
signal_brands = pair_rows(product_signals.get('top_brands', []), 'brand')
signal_keywords = pair_rows(product_signals.get('top_keywords', []), 'keyword')
signal_categories = pair_rows(product_signals.get('top_categories', []), 'category')
signal_seasons = pair_rows(product_signals.get('top_seasons', []), 'season')
signal_items = get_list(product_signals, 'signals')


def weekly_summary():
    parts = []
    if summary.get('date_range'):
        parts.append(f"ç»è®¡å¨æï¼{summary.get('date_range')}")
    for k in ['core_judgement', 'product_direction', 'regional_direction', 'next_action']:
        if summary.get(k):
            parts.append(summary.get(k))
    if not parts:
        parts.append('æ¬å¨è¡ä¸ç­ç¹å´ç»åçå¨ä½ãå¹³å°æµéãååè¶å¿ãåºåå®¢æµåå¤©æ°åç±»å±å¼ãåç»­ééç¹å³æ³¨ç«åå¨åãååå¼åè¾å¥åéç¹åºåæ¿æ¥æçã')
    return esc('ï½'.join(parts))


if not opportunities:
    opportunities = [
        {'theme':'åçå¨ä½','suggestion':'éç¹å³æ³¨ç«åç­¾çº¦ãèåãæ°åãæ¸ éåç¤¾åªå£°éååã'},
        {'theme':'ååè¶å¿','suggestion':'éç¹å³æ³¨å¿ç«¥è¿å¨éãé²æåæãè½»æ·å¤åéå°å¹´æäººåè¶å¿ã'},
        {'theme':'å¹³å°æµé','suggestion':'éç¹å³æ³¨ç´æ­ãå¤§ä¿ãæç´¢ç­è¯ååå®¹ç§èå¯¹ååå¿æºçå½±åã'}]
if not risks:
    risks = ['å¹³å°å¤§ä¿å¼ºåä»·æ ¼å¿æºï¼çº¿ä¸é¨åºéå³æ³¨ææ£ææåº¦åæ ¸å¿ä»·æ ¼å¸¦ç«äºã','å¤©æ°æ³¢å¨å¯è½æ°å¨çº¿ä¸å®¢æµï¼éé¨åºåéå¼ºåå®¤åè¿å¨åé²æ»é²é¨ååæ¿æ¥ã','åçç«äºå å§ï¼çæ¬¾åè´¨åé£é©æåï¼ééè¿åºæ¯éååç»åéå®æåè½¬åã']
if not actions:
    actions = ['æ¯å¨æ²æ·ç«ååçå¨ä½ï¼å½¢æå¯è·è¸ªçååãåå®¹åæ¸ éè§å¯æ¸åã','éç¹è·è¸ªé²æãåæãéå¹²ãéæ°éãè¿å¨åéç­å¤å­£åè½åç±»ã','å´ç»éå°å¹´è¿å¨ãæ ¡å­ä½è²ãäº²å­è¿å¨åååç»åååå®¹è¡¨è¾¾ã']
if not product_suggestions:
    product_suggestions = ['å¢å éå°å¹´è·éãç¯®çéãè®­ç»æçæäººåè®¾è®¡è¡¨è¾¾ã','å¼ºåé²æè¡£ãåæTæ¤ãéå¹²ç­è£¤ãè¿å¨åéç»åå¼åã','è¡¥åè½»æ·å¤éæãå¸½åéä»¶ãäº²å­åæ¬¾åæ ¡å­è¿å¨å¥è£ã']


def render_ai():
    if not ai:
        return ''
    if ai.get('raw'):
        return f"<div class='card ai-card'><div class='card-title'>AIç»è¥å¤æ­</div><div class='ai-content'>{esc(ai.get('raw'))}</div></div>"
    items = [('æ ¸å¿å¤æ­', ai.get('core_judgement','')),('æºä¼å¤æ­', ai.get('opportunity','')),('é£é©å¤æ­', ai.get('risk','')),('ä¸å¨å¨ä½', ai.get('action',''))]
    inner = ''.join(f"<div class='ai-section'><div class='ai-subtitle'>{t}</div><div class='ai-text'>{esc(v)}</div></div>" for t,v in items if v)
    return f"<div class='card ai-card'><div class='card-title'>AIç»è¥å¤æ­</div>{inner}</div>" if inner else ''


def render_news():
    vals = []
    for it in news_pool:
        if isinstance(it, dict) and it.get('title'):
            vals.append(raw(it.get('title')))
        elif isinstance(it, str):
            vals.append(raw(it))
    if not vals:
        return "<div class='empty'>ææ æ¬å¨éç¹èµè®¯æ°æ®</div>"
    out = ''
    for i,(title,count) in enumerate(Counter(vals).most_common(8), 1):
        out += f"<div class='news-row'><div class='news-rank'>{i}</div><div><div class='news-title'>{short(title,50)}</div><div class='news-meta'>æ¬å¨åºç° {count} æ¬¡</div></div></div>"
    return out


def render_keywords():
    vals = []
    for it in keywords:
        if isinstance(it, dict):
            w = it.get('word') or it.get('keyword') or it.get('name') or it.get('title')
            if w: vals.append(raw(w))
        elif isinstance(it, str):
            vals.append(raw(it))
    if not vals:
        vals = ['åçç­¾çº¦','é²æåæ','å¿ç«¥è·é','è½»æ·å¤','éå°å¹´','ç´æ­çµå','å¹³å°å¤§ä¿','æ ¡å­ä½è²']
    out = ''
    for i,(word,count) in enumerate(Counter(vals).most_common(22), 1):
        cls = 'hot-word big' if i <= 3 else 'hot-word mid' if i <= 9 else 'hot-word'
        out += f"<span class='{cls}'>{esc(word)}</span>"
    return out


def render_regions():
    if not regions:
        return "<div class='empty'>ææ åºåæ°æ®</div>"
    out = ''
    for r in regions[:6]:
        if not isinstance(r, dict):
            continue
        name = r.get('region') or r.get('name') or 'éç¹åºå'
        st = r.get('summary') or ''
        sug = r.get('suggestion') or ''
        if not st:
            focus = 'ã'.join(raw(x.get('focus','')) for x in as_list(r.get('top_focus'))[:2] if isinstance(x, dict) and x.get('focus'))
            st = f"æ¬å¨éç¹å³æ³¨ï¼{focus or 'åºåå®¢æµãå¤©æ°åç±»ãååæ´»å¨'}ã"
        desc = f"{st} å»ºè®®ï¼{sug}" if sug else st
        out += f"<div class='region-card'><div class='region-name'>{esc(name)}</div><div class='region-desc'>{esc(desc)}</div></div>"
    return out


def render_rank(rows, key, title, limit=10):
    if not rows:
        return f"<div class='signal-card'><div class='signal-title'>{title}</div><div class='empty'>ææ è¶å¿ä¿¡å·</div></div>"
    max_count = max([int(x.get('count',0) or 0) for x in rows[:limit]] + [1])
    out = f"<div class='signal-card'><div class='signal-title'>{title}</div>"
    for i,row in enumerate(rows[:limit],1):
        name = esc(row.get(key,'')); count = int(row.get('count',0) or 0); width = max(8, int(count/max_count*100))
        out += f"<div class='rank-bar-row'><div class='rank-label'><span>{i}</span>{name}</div><div class='rank-bar'><i style='width:{width}%'></i></div><div class='rank-count'>{count}</div></div>"
    return out + '</div>'


def render_tags(rows, key, limit=24):
    if not rows:
        return "<div class='empty'>ææ å³é®è¯ä¿¡å·</div>"
    out = "<div class='signal-tags'>"
    for i,row in enumerate(rows[:limit],1):
        cls = 'tag-large' if i <= 5 else 'tag-mid' if i <= 12 else ''
        out += f"<span class='{cls}'>{esc(row.get(key,''))}<em>{int(row.get('count',0) or 0)}</em></span>"
    return out + '</div>'


def icon_for(category, keywords, title):
    text = f"{category} {' '.join(keywords)} {title}"
    if 'è¶³å¼' in text or 'è·é' in text: return 'ð'
    if 'é²æ' in text or 'åæ' in text: return 'âï¸'
    if 'ç¯®ç' in text: return 'ð'
    if 'æ·å¤' in text or 'å²éè¡£' in text: return 'â°ï¸'
    if 'ç¾½ç»æ' in text or 'ä¿æ' in text: return 'âï¸'
    if 'æ ¡å­' in text or 'å¼å­¦' in text: return 'ð'
    if 'ç«¥è£' in text or 'å¿ç«¥æè£' in text: return 'ð'
    return 'â¨'


def insight_for(category, keywords, title):
    text = f"{category} {' '.join(keywords)} {title}"
    if 'è¶³å¼' in text: return 'å³æ³¨å¿ç«¥è¶³å¼æ¯æãæé¿è·éãå»å­¦èä¹¦ä¸ä¸ä¸ç§æè¡¨è¾¾ã'
    if 'é²æ' in text or 'åæ' in text: return 'å³æ³¨å¤å­£é²æãåæãéå¹²åè½»èéæ°ç»åã'
    if 'ç¢³æ¿' in text or 'ç«é' in text: return 'å³æ³¨éå°å¹´è·éæäººåï¼ä½éæ§å¶ä¸ä¸ç§æä½¿ç¨è¾¹çã'
    if 'ç¯®ç' in text: return 'å³æ³¨æ ¡å­ç¯®çãè®­ç»åºæ¯åä¸­å¤§ç«¥è¿å¨éåçº§ã'
    if 'æ·å¤' in text or 'å²éè¡£' in text: return 'å³æ³¨è½»æ·å¤ãé²æ°´é²é£ãäº²å­æ·å¤ååºæ¯éåã'
    if 'æ ¡å­' in text or 'å¼å­¦' in text: return 'å³æ³¨å¼å­¦å­£ãæ ¡å­ä½è²ãä¹¦åéæç»åéå®ã'
    return 'å³æ³¨è¯¥ä¿¡å·èåçåçå¨ä½ãåååç¹åç»ç«¯éåè¡¨è¾¾ã'


def build_cards():
    cards, brand_limit, cat_limit = [], Counter(), Counter()
    items = sorted([x for x in signal_items if isinstance(x, dict)], key=lambda x:int(x.get('heat',0) or 0), reverse=True)
    for s in items:
        brands = s.get('brand_hits', []) if isinstance(s.get('brand_hits'), list) else []
        keys = s.get('keyword_hits', []) if isinstance(s.get('keyword_hits'), list) else []
        brand = 'ã'.join(brands[:2]) if brands else 'è¡ä¸è¶å¿'
        cat = s.get('category','')
        title = s.get('short_title') or s.get('title','')
        if brand_limit[brand] >= 2 or cat_limit[cat] >= 3: continue
        brand_limit[brand] += 1; cat_limit[cat] += 1
        cards.append({'brand':brand,'name':title,'category':cat,'heat':s.get('heat',''),'trend':s.get('season_tag',''),'tags':keys[:3],'source':s.get('source',''),'icon':icon_for(cat,keys,title),'insight':insight_for(cat,keys,title)})
        if len(cards) >= 12: break
    return cards


product_cards = build_cards()


def render_products():
    if not product_cards:
        return "<div class='empty'>ææ ååè¶å¿æ°æ®</div>"
    out = ''
    for i,p in enumerate(product_cards,1):
        tags = ' / '.join(raw(x) for x in p.get('tags',[])[:3])
        out += f"""
        <div class='product-card'>
          <div class='product-img-wrap product-signal-cover'><div class='product-rank'>TOP {i}</div><div class='product-icon'>{p.get('icon','â¨')}</div><div class='product-signal-category'>{esc(p.get('category',''))}</div><div class='product-signal-heat'>ç­åº¦ {esc(p.get('heat',''))}</div></div>
          <div class='product-brand'>{esc(p.get('brand',''))}</div><div class='product-name'>{short(p.get('name',''),42)}</div>
          <div class='product-meta'><span>{esc(p.get('category',''))}</span><span>{esc(p.get('trend',''))}</span><span>{esc(p.get('source',''))}</span></div>
          <div class='product-tags'>{esc(tags)}</div><div class='product-insight'>{esc(p.get('insight',''))}</div>
        </div>"""
    return out


def render_hot_items():
    if not signal_items:
        return "<div class='empty'>ææ é«ç­ååä¿¡å·</div>"
    out = ''
    items = sorted([x for x in signal_items if isinstance(x, dict)], key=lambda x:int(x.get('heat',0) or 0), reverse=True)
    for i,s in enumerate(items[:8],1):
        brands = s.get('brand_hits', []) if isinstance(s.get('brand_hits'), list) else []
        out += f"<div class='signal-news-row'><div class='signal-news-rank'>{i}</div><div class='signal-news-main'><div class='signal-news-title'>{short(s.get('title',''),58)}</div><div class='signal-news-meta'><span>{esc(s.get('category','ç»¼åè¶å¿'))}</span><span>{esc(s.get('season_tag','å¨å¹´'))}</span><span>ç­åº¦ {esc(s.get('heat',''))}</span><span>{esc(s.get('source','å¬å¼èµè®¯'))}</span></div><div class='signal-news-brand'>{esc('ã'.join(brands[:3]))}</div></div></div>"
    return out


def render_suggestions():
    return ''.join(f"<div class='suggest-card'>{sentence(x)}</div>" for x in product_suggestions[:4])


generated_time = datetime.now().strftime('%Y-%m-%d %H:%M')
html_text = f"""
<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><title>è¿å¨åçè¡ä¸å¨æ¥</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#eaf1fb;font-family:'Microsoft YaHei','PingFang SC',Arial,sans-serif;color:#102a5c;padding:24px}}.report{{width:1280px;margin:auto}}.cover{{position:relative;height:260px;border-radius:26px;overflow:hidden;background:radial-gradient(circle at 85% 20%,rgba(255,139,0,.32),transparent 28%),radial-gradient(circle at 16% 88%,rgba(11,99,216,.24),transparent 30%),linear-gradient(135deg,#052b78 0%,#0b63d8 52%,#1d8fff 100%);color:#fff;padding:34px 42px;box-shadow:0 20px 46px rgba(9,55,128,.26);margin-bottom:18px}}.cover::after{{content:'';position:absolute;right:-80px;bottom:-120px;width:420px;height:420px;border-radius:50%;border:42px solid rgba(255,255,255,.12)}}.cover-tag{{display:inline-block;padding:7px 14px;border-radius:999px;background:rgba(255,255,255,.16);font-size:14px;font-weight:900;margin-bottom:18px}}.cover-title{{font-size:56px;line-height:1.05;font-weight:950;letter-spacing:-1px}}.cover-sub{{margin-top:14px;font-size:22px;font-weight:850;opacity:.95}}.cover-footer{{position:absolute;left:42px;bottom:28px;font-size:15px;font-weight:800;opacity:.9}}.stats{{position:absolute;right:34px;top:34px;display:grid;grid-template-columns:repeat(4,104px);gap:10px}}.stat{{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.24);border-radius:18px;padding:15px 12px;text-align:center;backdrop-filter:blur(6px)}}.stat-num{{font-size:30px;font-weight:950}}.stat-label{{font-size:12px;margin-top:4px;opacity:.9}}
.page{{background:#fff;border-radius:24px;padding:22px;box-shadow:0 18px 38px rgba(20,50,100,.12);margin-bottom:18px}}.section-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;border-bottom:2px solid #e1ebf8;padding-bottom:10px}}.section-title{{font-size:25px;font-weight:950;color:#062b78}}.section-kicker{{color:#0b63d8;font-weight:950;font-size:13px}}.summary-box{{background:linear-gradient(135deg,#f4f8ff,#eef6ff);border:1px solid #dbe6f6;border-radius:20px;padding:20px 22px;font-size:20px;line-height:1.7;font-weight:850;color:#0d2d68}}.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card,.signal-card{{border:1px solid #dbe6f6;border-radius:18px;background:#fbfdff;padding:16px}}.card-title,.signal-title{{font-size:17px;font-weight:950;color:#0b4db3;margin-bottom:10px}}ul{{padding-left:20px}}li{{margin-bottom:10px;font-size:15px;line-height:1.55;font-weight:760;color:#233e68}}
.news-row{{display:grid;grid-template-columns:38px 1fr;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid #edf2fa}}.news-rank{{width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#063b88,#0d7df2);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:950}}.news-title{{font-size:15.5px;font-weight:950;color:#0d2d68}}.news-meta{{font-size:12px;color:#6b7f9f;margin-top:3px}}.word-cloud{{min-height:250px;padding:22px;display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:14px 18px;background:linear-gradient(135deg,#f8fbff,#eef6ff);border-radius:18px;border:1px solid #dbe6f6}}.hot-word{{font-weight:950;color:#0b63d8;background:#fff;border:1px solid #dbe6f6;border-radius:999px;padding:7px 14px;font-size:14px;box-shadow:0 5px 14px rgba(20,60,110,.06)}}.hot-word.mid{{font-size:17px;color:#0f766e;background:#ecfdf5}}.hot-word.big{{font-size:24px;color:#062b78;background:#dcecff}}
.region-card{{border-radius:18px;background:linear-gradient(135deg,#f7fbff,#ffffff);border:1px solid #dbe6f6;padding:16px;min-height:112px}}.region-name{{font-size:20px;font-weight:950;color:#0b4db3;margin-bottom:8px}}.region-desc{{font-size:14.5px;line-height:1.5;color:#315174;font-weight:750}}.signal-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}.rank-bar-row{{display:grid;grid-template-columns:132px 1fr 38px;gap:10px;align-items:center;margin-bottom:10px}}.rank-label{{font-size:13px;font-weight:900;color:#183a76;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.rank-label span{{display:inline-flex;width:22px;height:22px;align-items:center;justify-content:center;background:#0b63d8;color:#fff;border-radius:7px;margin-right:7px;font-size:11px}}.rank-bar{{height:9px;background:#edf5ff;border-radius:999px;overflow:hidden}}.rank-bar i{{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#0b63d8,#19a3ff)}}.rank-count{{font-size:13px;font-weight:950;color:#0b63d8;text-align:right}}.signal-tags{{display:flex;flex-wrap:wrap;gap:10px}}.signal-tags span{{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:999px;background:#f3f8ff;border:1px solid #dbe6f6;color:#0b4db3;font-size:13px;font-weight:900}}.signal-tags span.tag-mid{{font-size:15px;background:#ecfdf5;color:#0f766e}}.signal-tags span.tag-large{{font-size:18px;background:#dcecff;color:#062b78}}.signal-tags em{{font-style:normal;background:#fff;border-radius:999px;padding:2px 6px;color:#64748b;font-size:11px}}
.signal-news-row{{display:grid;grid-template-columns:34px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid #edf2fa}}.signal-news-rank{{width:30px;height:30px;border-radius:9px;background:#0f766e;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:950}}.signal-news-title{{font-size:15px;font-weight:950;color:#0d2d68}}.signal-news-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}.signal-news-meta span{{font-size:11px;background:#edf5ff;color:#365379;border-radius:8px;padding:3px 6px;font-weight:800}}.signal-news-brand{{font-size:12px;color:#0f766e;font-weight:850;margin-top:5px}}
.products{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.product-card{{border:1px solid #dbe6f6;border-radius:18px;background:#fbfdff;padding:12px;box-shadow:0 8px 18px rgba(20,60,110,.06)}}.product-img-wrap{{position:relative;width:100%;height:150px;border-radius:15px;overflow:hidden;background:#edf5ff;margin-bottom:10px}}.product-signal-cover{{display:flex;flex-direction:column;justify-content:center;align-items:center;background:radial-gradient(circle at 80% 20%,rgba(25,163,255,.22),transparent 30%),linear-gradient(135deg,#edf5ff,#f8fbff)}}.product-icon{{font-size:46px;line-height:1;margin-bottom:10px}}.product-signal-category{{font-size:22px;font-weight:950;color:#0b4db3}}.product-signal-heat{{margin-top:10px;font-size:14px;font-weight:900;color:#0f766e;background:#ecfdf5;padding:5px 12px;border-radius:999px}}.product-rank{{position:absolute;top:8px;left:8px;padding:4px 8px;border-radius:999px;background:rgba(6,43,120,.88);color:#fff;font-size:11px;font-weight:950}}.product-brand{{font-size:13px;color:#0b63d8;font-weight:950}}.product-name{{font-size:15.5px;line-height:1.35;font-weight:950;color:#0d2d68;margin-top:5px;min-height:42px}}.product-meta{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;font-size:11px;color:#51698d}}.product-meta span{{background:#edf5ff;padding:3px 6px;border-radius:8px}}.product-tags{{margin-top:8px;font-size:12px;color:#1d8c54;font-weight:850}}.product-insight{{margin-top:10px;padding:10px;border-radius:12px;background:#f0fdf4;color:#166534;font-size:12.5px;line-height:1.45;font-weight:850}}
.suggest-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.suggest-card{{border-radius:18px;background:linear-gradient(135deg,#fff7ed,#ffffff);border:1px solid #fed7aa;padding:16px;font-size:15px;line-height:1.55;font-weight:850;color:#7c2d12;min-height:130px}}.ai-card{{margin-top:16px;background:linear-gradient(135deg,#f8fbff,#ffffff)}}.ai-section{{margin-top:14px;padding:14px;border-radius:12px;background:#f8fbff;border:1px solid #dbe6f6}}.ai-subtitle{{font-size:15px;font-weight:950;color:#0b4db3;margin-bottom:8px}}.ai-text{{font-size:14px;line-height:1.8;color:#233e68;font-weight:700}}.ai-content{{font-size:16px;line-height:1.75;font-weight:800;color:#233e68;white-space:pre-wrap}}.empty{{color:#8a99ad;font-size:14px;padding:20px;text-align:center}}.footer{{text-align:center;color:#7184a3;font-size:12px;margin:14px 0 4px}}
</style></head><body><div class='report'>
<section class='cover'><div class='cover-tag'>361Â°å¿ç«¥ Â· å¨åº¦ç»è¥æ´å¯</div><div class='cover-title'>è¿å¨åçè¡ä¸å¨æ¥</div><div class='cover-sub'>åçå¨ä½ Ã ååè¶å¿ Ã å¹³å°æµé Ã åºåæºä¼ Ã ç»ç«¯å»ºè®®</div><div class='cover-footer'>ONE DEGREE BEYONDï½ç»è¥ç®¡çé¨ï½çææ¶é´ {generated_time}</div><div class='stats'><div class='stat'><div class='stat-num'>{len(days)}</div><div class='stat-label'>ç»è®¡å¤©æ°</div></div><div class='stat'><div class='stat-num'>{len(news_pool)}</div><div class='stat-label'>èµè®¯æ ·æ¬</div></div><div class='stat'><div class='stat-num'>{signal_count}</div><div class='stat-label'>è¶å¿ä¿¡å·</div></div><div class='stat'><div class='stat-num'>{len(product_cards)}</div><div class='stat-label'>ååè§å¯</div></div></div></section>
<section class='page'><div class='section-head'><div class='section-title'>ä¸ãæ¬å¨æ ¸å¿å¤æ­</div><div class='section-kicker'>WEEKLY JUDGEMENT</div></div><div class='summary-box'>{weekly_summary()}</div>{render_ai()}</section>
<section class='page'><div class='section-head'><div class='section-title'>äºãæ¬å¨è¶å¿æ»è§</div><div class='section-kicker'>TREND OVERVIEW</div></div><div class='grid-3'><div class='card'><div class='card-title'>æºä¼æ¹å</div><ul>{render_list(opportunities,4)}</ul></div><div class='card'><div class='card-title'>é£é©æç¤º</div><ul>{render_list(risks,4)}</ul></div><div class='card'><div class='card-title'>ä¸å¨å¨ä½</div><ul>{render_list(actions,4)}</ul></div></div></section>
<section class='page'><div class='section-head'><div class='section-title'>ä¸ãæ¬å¨éç¹èµè®¯ä¸ç­è¯</div><div class='section-kicker'>NEWS & KEYWORDS</div></div><div class='grid-2'><div class='card'><div class='card-title'>æ¬å¨ TOP èµè®¯</div>{render_news()}</div><div><div class='word-cloud'>{render_keywords()}</div></div></div></section>
<section class='page'><div class='section-head'><div class='section-title'>åãåºåæºä¼ä¸æ¸ éè§å¯</div><div class='section-kicker'>REGIONAL INSIGHT</div></div><div class='grid-3'>{render_regions()}</div></section>
<section class='page'><div class='section-head'><div class='section-title'>äºãçå®ååè¶å¿ä¿¡å·çæ¿</div><div class='section-kicker'>PRODUCT SIGNALS</div></div><div class='signal-grid'>{render_rank(signal_brands,'brand','åçç­åº¦ TOP10',10)}{render_rank(signal_categories,'category','åç±»/åºæ¯ç­åº¦ TOP10',10)}</div><div class='signal-grid'><div class='signal-card'><div class='signal-title'>å³é®è¯ä¿¡å·</div>{render_tags(signal_keywords,'keyword',24)}</div>{render_rank(signal_seasons,'season','åå­£è¶å¿åå¸',8)}</div><div class='signal-card'><div class='signal-title'>é«ç­åå/æ°åä¿¡å·</div>{render_hot_items()}</div></section>
<section class='page'><div class='section-head'><div class='section-title'>å­ãä»£è¡¨ååè§å¯</div><div class='section-kicker'>REPRESENTATIVE PRODUCTS</div></div><div class='products'>{render_products()}</div></section>
<section class='page'><div class='section-head'><div class='section-title'>ä¸ãä¸å­£åº¦ååå¼åå»ºè®®</div><div class='section-kicker'>PRODUCT PLANNING</div></div><div class='suggest-grid'>{render_suggestions()}</div></section>
<div class='footer'>æ°æ®æ¥æºï¼TrendRadar æ¥æ¥åå²åº / å¨æ¥åº / ååè¶å¿ä¿¡å·åº ï½ å¶ä½ï¼è¿å¨åçè¡ä¸å¨æ¥èªå¨åç³»ç»</div>
</div></body></html>"""

OUTPUT_HTML.write_text(html_text, encoding='utf-8')
print(f'weekly html generated: {OUTPUT_HTML}')
