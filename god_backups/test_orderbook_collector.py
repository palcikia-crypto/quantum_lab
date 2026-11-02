#!/usr/bin/env python3
"""orderbook_collector.py — собирает стаканы Polymarket для 15m рынков и сохраняет в SQLite."""
import os, sys, json, time, sqlite3, urllib.request
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/orderbooks.db')
UA = {'User-Agent': 'Mozilla/5.0'}

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=10, encoding='utf-8').read())

def get_market_slug(symbol):
    """Возвращает slug для текущего 15m окна."""
    now = int(time.time())
    window = (now // 900) * 900
    return f'{symbol.lower()}-updown-15m-{window}'

def get_tokens(slug):
    """Возвращает (up_token, down_token) из Gamma API."""
    url = f'https://gamma-api.polymarket.com/events?slug={slug}'
    try:
        d = fetch(url)
        if not d: return None
        m = d[0]['markets'][0]
        clob = m.get('clobTokenIds')
        if isinstance(clob, str): clob = json.loads(clob)
        if not clob or len(clob) != 2: return None
        return {'up': clob[0], 'down': clob[1]}
    except Exception as e:
        print(f'⚠️ get_tokens {slug}: {e}')
        return None

def get_book(token_id):
    """Возвращает стакан (bids, asks) для токена."""
    url = f'https://clob.polymarket.com/book?token_id={token_id}'
    try:
        book = fetch(url)
        return book
    except Exception as e:
        print(f'⚠️ get_book {token_id[:20]}: {e}')
        return None

def compute_metrics(book):
    """Считает метрики стакана: spread, depth, imbalance."""
    if not book: return None
    bids = book.get('bids', [])
    asks = book.get('asks', [])
    if not bids or not asks: return None
    best_bid = max(float(b['price']) for b in bids)
    best_ask = min(float(a['price']) for a in asks)
    spread = best_ask - best_bid
    bid_depth = sum(float(b['size']) for b in bids)
    ask_depth = sum(float(a['size']) for a in asks)
    total = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total if total > 0 else 0
    return {
        'best_bid': round(best_bid, 4),
        'best_ask': round(best_ask, 4),
        'spread': round(spread, 4),
        'bid_depth': round(bid_depth, 2),
        'ask_depth': round(ask_depth, 2),
        'imbalance': round(imbalance, 4),
    }

def init_db():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS orderbooks (
        ts INTEGER, symbol TEXT, side TEXT, token TEXT,
        best_bid REAL, best_ask REAL, spread REAL,
        bid_depth REAL, ask_depth REAL, imbalance REAL,
        PRIMARY KEY (ts, symbol, side)
    )''')
    c.commit(); c.close()

def collect_once(symbols=('BTC','ETH','XRP','SOL','DOGE')):
    init_db()
    ts = int(time.time())
    rows = []
    for sym in symbols:
        slug = get_market_slug(sym)
        tokens = get_tokens(slug)
        if not tokens: continue
        for side, token in tokens.items():
            book = get_book(token)
            m = compute_metrics(book)
            if m:
                rows.append((ts, sym, side, token, m['best_bid'], m['best_ask'],
                             m['spread'], m['bid_depth'], m['ask_depth'], m['imbalance']))
        print(f'  {sym}: {len(rows)} строк')
    if rows:
        c = sqlite3.connect(DB)
        c.executemany('INSERT OR REPLACE INTO orderbooks VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
        c.commit(); c.close()
        print(f'✅ сохранено {len(rows)} стаканов за {datetime.now():%H:%M:%S}')
    return len(rows)

if __name__ == '__main__':
    print('=== ORDERBOOK COLLECTOR ===')
    collect_once()
