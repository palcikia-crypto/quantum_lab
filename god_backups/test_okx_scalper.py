#!/usr/bin/env python3
"""okx_scalper.py — скальпинг по стакану OKX (books5, 5 уровней, БЕСПЛАТНО)."""
import asyncio, json, sqlite3, os, time
import websockets
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx.db')
LOG = os.path.join(BASE, 'logs/okx_scalper.log')

OBI_LONG = 0.4   # снижен порог (books5 менее глубокий)
OBI_SHORT = -0.4
SPREAD_MAX = 0.05

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

def init_db():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS obi_signals (
        ts INTEGER, symbol TEXT, obi REAL, spread REAL, bid_depth REAL, ask_depth REAL,
        signal TEXT, PRIMARY KEY (ts, symbol))''')
    c.commit(); c.close()

async def collect_obi(symbol='BTC-USDT', duration=300):
    """books5: 5 уровней, 100ms, БЕСПЛАТНО."""
    url = 'wss://ws.okx.com:8443/ws/v5/public'
    async with websockets.connect(url) as ws:
        # books5 — 5 уровней, доступен всем
        sub = {'op': 'subscribe', 'args': [{'channel': 'books5', 'instId': symbol}]}
        await ws.send(json.dumps(sub))
        log(f'✅ Подписка на {symbol} books5 (5 уровней)')

        start = time.time()
        signals = 0
        while time.time() - start < duration:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if 'data' not in data: continue

                for book in data['data']:
                    bids = book.get('bids', [])
                    asks = book.get('asks', [])
                    if not bids or not asks: continue

                    # books5: топ-5 уровней
                    bid_depth = sum(float(b[1]) for b in bids[:5])
                    ask_depth = sum(float(a[1]) for a in asks[:5])
                    total = bid_depth + ask_depth
                    if total == 0: continue

                    obi = (bid_depth - ask_depth) / total
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    spread = (best_ask - best_bid) / best_bid

                    signal = 'NONE'
                    if spread > SPREAD_MAX: continue
                    if obi > OBI_LONG: signal = 'LONG'
                    elif obi < OBI_SHORT: signal = 'SHORT'

                    if signal != 'NONE':
                        ts = int(time.time())
                        c = sqlite3.connect(DB)
                        c.execute('INSERT OR REPLACE INTO obi_signals VALUES (?,?,?,?,?,?,?)',
                                  (ts, symbol, round(obi,4), round(spread,4), bid_depth, ask_depth, signal))
                        c.commit(); c.close()
                        signals += 1
                        log(f'  {symbol} OBI={obi:.3f} spread={spread:.4f} → {signal}')
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log(f'⚠️ {e}')
        log(f'✅ OBI за {duration}с: {signals} сигналов')

if __name__ == '__main__':
    init_db()
    asyncio.run(collect_obi('BTC-USDT', duration=120))
