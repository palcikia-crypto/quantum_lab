#!/usr/bin/env python3
"""orderbook_oracle.py — сбор стаканов, тиков, funding, VWAP с OKX WebSocket.
Пишет в data/orderbook.db. НЕ трогает oracle.db, НЕ трогает v2/v3."""
import asyncio, json, sqlite3, os, time, sys
from datetime import datetime
try:
    import websockets
except ImportError:
    print('❌ websockets не установлен. Установи: pip install websockets')
    sys.exit(1)

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/orderbook.db')
LOG = os.path.join(BASE, 'logs/orderbook_oracle.log')

# Пары: 7 из v3 + BTC/ETH/SOL для v2 (всего 10)
SYMBOLS = [
    'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'XRP-USDT',
    'DOGE-USDT', 'LINK-USDT', 'ARB-USDT', 'AVAX-USDT',
    'ADA-USDT', 'DOT-USDT',
]

SWAP_SYMBOLS = [
    'BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP',
    'XRP-USDT-SWAP', 'DOGE-USDT-SWAP', 'LINK-USDT-SWAP',
]

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS orderbooks (
        ts INTEGER, symbol TEXT,
        best_bid REAL, best_ask REAL, spread REAL,
        bid_depth REAL, ask_depth REAL, imbalance REAL,
        PRIMARY KEY (ts, symbol)
    );
    CREATE TABLE IF NOT EXISTS trades (
        ts INTEGER, symbol TEXT, side TEXT, price REAL, volume REAL,
        PRIMARY KEY (ts, symbol, side, price)
    );
    CREATE TABLE IF NOT EXISTS funding (
        ts INTEGER, symbol TEXT, funding_rate REAL, next_funding_ts INTEGER,
        PRIMARY KEY (ts, symbol)
    );
    CREATE TABLE IF NOT EXISTS vwap (
        ts INTEGER, symbol TEXT, vwap_1m REAL, vwap_5m REAL,
        PRIMARY KEY (ts, symbol)
    );
    CREATE INDEX IF NOT EXISTS idx_ob_sym_ts ON orderbooks(symbol, ts);
    CREATE INDEX IF NOT EXISTS idx_tr_sym_ts ON trades(symbol, ts);
    ''')
    c.commit(); c.close()

# ====== Буферы в памяти (для VWAP и tick pressure) ======
TICK_BUFFER = {}  # symbol -> [(ts, price, volume, side), ...]
VWAP_WINDOW = 300  # 5 минут

def calc_vwap(symbol):
    """VWAP за 1 мин и 5 мин по тикам."""
    now = int(time.time())
    ticks = TICK_BUFFER.get(symbol, [])
    # чистим старше 5 мин
    ticks = [t for t in ticks if now - t[0] <= VWAP_WINDOW]
    TICK_BUFFER[symbol] = ticks

    def vwap_for(window):
        relevant = [t for t in ticks if now - t[0] <= window]
        if not relevant:
            return 0.0
        total_pv = sum(t[1] * t[2] for t in relevant)
        total_v = sum(t[2] for t in relevant)
        return round(total_pv / total_v, 6) if total_v > 0 else 0.0

    return vwap_for(60), vwap_for(300)

def calc_tick_pressure(symbol):
    """buy_volume - sell_volume за 1 мин."""
    now = int(time.time())
    ticks = TICK_BUFFER.get(symbol, [])
    buy = sum(t[2] for t in ticks if t[3] == 'buy' and now - t[0] <= 60)
    sell = sum(t[2] for t in ticks if t[3] == 'sell' and now - t[0] <= 60)
    return buy - sell

def save_funding(symbol, fr, next_ts):
    """Сохраняет funding rate в БД."""
    try:
        ts = int(time.time())
        c = sqlite3.connect(DB, timeout=5)
        c.execute('INSERT OR REPLACE INTO funding VALUES (?,?,?,?)',
                  (ts, symbol, float(fr), int(next_ts) // 1000 if next_ts else 0))
        c.commit(); c.close()
        log(f'✅ funding {symbol}: {fr}')
    except Exception as e:
        log(f'⚠️ save_funding {symbol}: {e}')

async def subscribe_books(ws, symbols):
    """Подписка на books5 (5 уровней)."""
    args = [{'channel': 'books5', 'instId': s} for s in symbols]
    await ws.send(json.dumps({'op': 'subscribe', 'args': args}))
    log(f'✅ books5: {len(args)} пар')

async def subscribe_trades(ws, symbols):
    """Подписка на trades (тики)."""
    args = [{'channel': 'trades', 'instId': s} for s in symbols]
    await ws.send(json.dumps({'op': 'subscribe', 'args': args}))
    log(f'✅ trades: {len(args)} пар')

async def subscribe_funding(ws, symbols):
    """Подписка на funding-rate (для SWAP) с логированием."""
    args = [{'channel': 'funding-rate', 'instId': s} for s in symbols]
    await ws.send(json.dumps({'op': 'subscribe', 'args': args}))
    log(f'📤 funding-rate subscribe: {len(args)} SWAP')
    # Читаем ответ OKX
    try:
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        r = json.loads(resp)
        if r.get('event') == 'subscribe':
            log(f'✅ funding-rate ПОДПИСКА OK: {r.get("arg",{}).get("instId","?")}')
        elif r.get('event') == 'error':
            log(f'❌ funding-rate ОШИБКА: {r.get("code")} {r.get("msg")}')
        else:
            log(f'ℹ️ funding-rate ответ: {r.get("event","?")}')
    except asyncio.TimeoutError:
        log('⏱️ funding-rate: нет ответа (timeout 5s)')
    except Exception as e:
        log(f'⚠️ funding-rate recv: {e}')

def save_orderbook(symbol, bids, asks):
    """Сохраняет стакан в БД."""
    if not bids or not asks:
        return
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    spread = (best_ask - best_bid) / best_bid if best_bid > 0 else 0
    bid_depth = sum(float(b[1]) for b in bids[:5])
    ask_depth = sum(float(a[1]) for a in asks[:5])
    total = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total if total > 0 else 0

    ts = int(time.time())
    try:
        c = sqlite3.connect(DB, timeout=5)
        c.execute('INSERT OR REPLACE INTO orderbooks VALUES (?,?,?,?,?,?,?,?)',
                  (ts, symbol, best_bid, best_ask, round(spread, 6),
                   bid_depth, ask_depth, round(imbalance, 4)))
        # VWAP
        v1, v5 = calc_vwap(symbol)
        if v1 > 0:
            c.execute('INSERT OR REPLACE INTO vwap VALUES (?,?,?,?)',
                      (ts, symbol, v1, v5))
        c.commit(); c.close()
    except Exception as e:
        log(f'⚠️ save_orderbook {symbol}: {e}')

def save_trade(symbol, trade):
    """Сохраняет тик в БД и буфер."""
    try:
        ts = int(trade['ts']) // 1000
        price = float(trade['px'])
        volume = float(trade['sz'])
        side = trade['side']
        # буфер
        TICK_BUFFER.setdefault(symbol, []).append((ts, price, volume, side))
        # БД
        c = sqlite3.connect(DB, timeout=5)
        c.execute('INSERT OR REPLACE INTO trades VALUES (?,?,?,?,?)',
                  (ts, symbol, side, price, volume))
        c.commit(); c.close()
    except Exception as e:
        log(f'⚠️ save_trade {symbol}: {e}')

async def run():
    init_db()
    log(f'=== ORDERBOOK ORACLE STARTED: {len(SYMBOLS)} пар ===')
    url = 'wss://ws.okx.com:8443/ws/v5/public'

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                await subscribe_books(ws, SYMBOLS)
                await subscribe_trades(ws, SYMBOLS)
                await subscribe_funding(ws, SWAP_SYMBOLS)
                log('✅ Подписки активны, слушаем...')

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        arg = msg.get('arg', {})
                        channel = arg.get('channel', '')
                        inst = arg.get('instId', '')
                        data = msg.get('data', [])
                        if not data:
                            continue

                        if channel == 'books5':
                            book = data[0]
                            save_orderbook(inst, book.get('bids', []), book.get('asks', []))
                        elif channel == 'funding-rate':
                            for f in data:
                                try:
                                    save_funding(inst, f.get('fundingRate', 0), f.get('nextFundingTime', 0))
                                except Exception as e:
                                    log(f'⚠️ funding: {e}')
                        elif channel == 'trades':
                            for t in data:
                                save_trade(inst, t)
                    except Exception as e:
                        log(f'⚠️ msg parse: {e}')
        except Exception as e:
            log(f'❌ WS error: {e} — reconnect через 5 сек')
            await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(run())
