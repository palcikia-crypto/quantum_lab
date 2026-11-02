#!/usr/bin/env python3
"""okx_collector.py — гибрид: стаканы через WebSocket, свечи через REST."""
import asyncio, json, sqlite3, os, urllib.request
import websockets

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx.db')
UA = {'User-Agent': 'Mozilla/5.0'}

def init_db():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS candles (
        symbol TEXT, tf TEXT, ts INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL,
        PRIMARY KEY (symbol, tf, ts))''')
    c.execute('''CREATE TABLE IF NOT EXISTS orderbooks (
        ts INTEGER, symbol TEXT, best_bid REAL, best_ask REAL, spread REAL,
        bid_depth REAL, ask_depth REAL, imbalance REAL,
        PRIMARY KEY (ts, symbol))''')
    c.commit(); c.close()

def fetch_candles(symbol='BTC-USDT', bar='15m', limit=100):
    """Свечи через REST (надёжно)."""
    url = f'https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={bar}&limit={limit}'
    req = urllib.request.Request(url, headers=UA)
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if d.get('code') != '0': return 0
        cdb = sqlite3.connect(DB)
        n = 0
        for row in d.get('data', []):
            ts = int(row[0]) // 1000
            o,h,l,c,v = map(float, row[1:6])
            cdb.execute('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)',
                        (symbol, bar, ts, o,h,l,c,v))
            n += 1
        cdb.commit(); cdb.close()
        return n
    except Exception as e:
        print(f'⚠️ candles {symbol}: {e}')
        return 0

async def collect_books(symbol='BTC-USDT', duration=300):
    """Стаканы через WebSocket (tick-by-tick)."""
    url = 'wss://ws.okx.com:8443/ws/v5/public'
    async with websockets.connect(url) as ws:
        sub = {'op': 'subscribe', 'args': [{'channel': 'bbo-tbt', 'instId': symbol}]}
        await ws.send(json.dumps(sub))
        print(f'✅ Подписка на {symbol} bbo-tbt')
        start = asyncio.get_event_loop().time()
        n = 0
        while asyncio.get_event_loop().time() - start < duration:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if 'data' not in data: continue
                for row in data['data']:
                    ts = int(row['ts']) // 1000
                    bid = float(row['bids'][0][0]); ask = float(row['asks'][0][0])
                    spread = ask - bid
                    cdb = sqlite3.connect(DB)
                    cdb.execute('INSERT OR REPLACE INTO orderbooks VALUES (?,?,?,?,?,?,?,?)',
                                (ts, symbol, bid, ask, spread, 0, 0, 0))
                    cdb.commit(); cdb.close()
                    n += 1
                    if n % 100 == 0: print(f'  books: {n}')
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f'⚠️ books: {e}')
        print(f'✅ books за {duration}с: {n}')

async def main():
    init_db()
    # 1. Свечи через REST (сразу)
    n_c = fetch_candles('BTC-USDT', '15m', 100)
    print(f'✅ candles: {n_c} (REST)')
    # 2. Стаканы через WebSocket (5 мин)
    await collect_books('BTC-USDT', duration=300)

if __name__ == '__main__':
    asyncio.run(main())
