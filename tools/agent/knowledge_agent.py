#!/usr/bin/env python3
"""Собирает знания из интернета: новости, цены, GitHub. Без API."""
import os, sys, json, sqlite3, time, urllib.request, re
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/knowledge.db')
LOG = os.path.join(BASE, 'logs/knowledge_agent.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def init_db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER, source TEXT, category TEXT, title TEXT, content TEXT, url TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER, pattern TEXT, count INTEGER, last_seen INTEGER
    )""")
    c.commit(); c.close()

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', errors='ignore')
    except Exception as e:
        log(f'fetch error {url}: {e}')
        return None

def save(source, category, title, content, url=''):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO knowledge (ts, source, category, title, content, url) VALUES (?,?,?,?,?,?)",
              (int(time.time()), source, category, title[:200], content[:2000], url))
    c.commit(); c.close()

def learn_crypto_news():
    """RSS с Cointelegraph, CoinDesk."""
    feeds = [
        ('https://cointelegraph.com/rss', 'Cointelegraph'),
    ]
    for url, name in feeds:
        xml = fetch(url)
        if not xml: continue
        items = re.findall(r'<item>(.*?)</item>', xml, re.S)[:5]
        for item in items:
            title = re.search(r'<title>(.*?)</title>', item, re.S)
            desc = re.search(r'<description>(.*?)</description>', item, re.S)
            link = re.search(r'<link>(.*?)</link>', item, re.S)
            if title:
                t = re.sub(r'<[^>]+>', '', title.group(1)).strip()
                d = re.sub(r'<[^>]+>', '', desc.group(1)).strip() if desc else ''
                u = link.group(1).strip() if link else ''
                save(name, 'news', t, d, u)
                log(f'📰 {name}: {t[:60]}')

def learn_okx_funding():
    """Funding rate с OKX (публичный API, без ключа)."""
    try:
        url = 'https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP'
        data = json.loads(fetch(url))
        if data.get('data'):
            fr = data['data'][0]
            save('OKX', 'funding', 'BTC funding', json.dumps(fr)[:1000], url)
            log(f'💰 BTC funding: {fr.get("fundingRate")}')
    except Exception as e:
        log(f'funding error: {e}')

def learn_github_trends():
    """GitHub trending Python (без API)."""
    html = fetch('https://github.com/trending/python?since=daily')
    if not html: return
    # только /owner/repo, без мусора
    BAD = {'sponsors','apps','login','trending','features','topics','collections','events','marketplace','pricing','enterprise','team','about','security','site','contact','readme','explore'}
    repos = re.findall(r'href="/([^/"]+/[^/"]+)"', html)
    repos = [r for r in repos if not any(b in r.split('/')[0] for b in BAD) and 'stargazers' not in r][:5]
    for r in repos:
        url = 'https://github.com/' + r
        save('GitHub', 'code', f'trending: {r}', url, url)
        log(f'🐙 GitHub: {r}')

def learn_ml_papers():
    """arXiv ML (без API)."""
    xml = fetch('http://export.arxiv.org/rss/cs.LG')
    if not xml: return
    items = re.findall(r'<item>(.*?)</item>', xml, re.S)[:3]
    for item in items:
        title = re.search(r'<title>(.*?)</title>', item, re.S)
        if title:
            t = re.sub(r'<[^>]+>', '', title.group(1)).strip()
            save('arXiv', 'ml', t, '', '')
            log(f'📄 arXiv: {t[:60]}')

def update_patterns():
    """Анализирует накопленные знания: какие темы часто встречаются."""
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT category, COUNT(*) FROM knowledge GROUP BY category").fetchall()
    for cat, cnt in rows:
        c.execute("""INSERT INTO patterns (ts, pattern, count, last_seen) VALUES (?,?,?,?)
                     ON CONFLICT DO NOTHING""", (int(time.time()), f'cat:{cat}', cnt, int(time.time())))
    c.commit(); c.close()
    log(f'📊 patterns: {dict(rows)}')

def main():
    log('=== KNOWLEDGE AGENT RUN ===')
    init_db()
    learn_crypto_news()
    learn_okx_funding()
    learn_github_trends()
    learn_ml_papers()
    update_patterns()
    c = sqlite3.connect(DB)
    total = c.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    c.close()
    log(f'✅ всего знаний: {total}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
