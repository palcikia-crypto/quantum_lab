#!/usr/bin/env python3
"""oracle.py — оракул: реальное время с Binance. Цена, объём, funding, режим."""
import os, json, time, sqlite3, urllib.request
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/oracle.db')
PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT', 'ARBUSDT']
INTERVAL = 5

def init_db():
    c = sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS prices (
        ts INTEGER, symbol TEXT, price REAL, volume REAL, bid REAL, ask REAL, spread REAL,
        PRIMARY KEY (symbol, ts));
    CREATE TABLE IF NOT EXISTS regime (
        ts INTEGER, symbol TEXT, regime TEXT, atr REAL, adx REAL, vol_z REAL,
        PRIMARY KEY (symbol, ts));
    ''')
    c.commit(); c.close()

def fetch(url, timeout=5):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def get_price(symbol):
    try:
        r = fetch(f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}')
        return {'price': float(r['lastPrice']), 'volume': float(r['volume']),
                'bid': float(r['bidPrice']), 'ask': float(r['askPrice']),
                'spread': float(r['askPrice']) - float(r['bidPrice'])}
    except: return None

def get_klines(symbol, interval='1h', limit=100):
    try:
        r = fetch(f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}')
        return r
    except: return None

def calc_regime(klines):
    """Определяет режим: trend_up, trend_down, flat, high_vol, low_vol."""
    if not klines or len(klines) < 50: return {'regime': 'unknown'}
    closes = [float(k[4]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    # ATR
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(closes))]
    atr = sum(trs[-14:])/14
    # SMA50
    sma50 = sum(closes[-50:])/50
    price = closes[-1]
    # ADX (упрощённо)
    plus_dm = [max(highs[i]-highs[i-1], 0) for i in range(1, len(closes))]
    minus_dm = [max(lows[i-1]-lows[i], 0) for i in range(1, len(closes))]
    plus_di = sum(plus_dm[-14:])/14
    minus_di = sum(minus_dm[-14:])/14
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    adx = dx  # упрощённо
    # волатильность
    vol_z = atr / (sum(trs[-50:])/50) if sum(trs[-50:]) > 0 else 1
    # режим
    if adx > 25 and price > sma50: regime = 'trend_up'
    elif adx > 25 and price < sma50: regime = 'trend_down'
    elif vol_z > 1.5: regime = 'high_vol'
    elif vol_z < 0.5: regime = 'low_vol'
    else: regime = 'flat'
    return {'regime': regime, 'atr': round(atr,4), 'adx': round(adx,1), 'vol_z': round(vol_z,2)}

def update():
    init_db()
    ts = int(time.time())
    c = sqlite3.connect(DB)
    for sym in PAIRS:
        p = get_price(sym)
        if p:
            c.execute("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)",
                      (ts, sym, p['price'], p['volume'], p['bid'], p['ask'], p['spread']))
        k = get_klines(sym, '1h', 100)
        if k:
            reg = calc_regime(k)
            c.execute("INSERT OR REPLACE INTO regime VALUES (?,?,?,?,?,?)",
                      (ts, sym, reg['regime'], reg['atr'], reg['adx'], reg['vol_z']))
    c.commit(); c.close()
    # чистим старые (оставляем 1 час)
    c = sqlite3.connect(DB)
    c.execute("DELETE FROM prices WHERE ts < ?", (ts - 3600,))
    c.execute("DELETE FROM regime WHERE ts < ?", (ts - 86400,))
    c.commit(); c.close()

def get_state(symbol=None):
    c = sqlite3.connect(DB, timeout=3)
    if symbol:
        p = c.execute("SELECT * FROM prices WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)).fetchone()
        r = c.execute("SELECT * FROM regime WHERE symbol=? ORDER BY ts DESC LIMIT 1", (symbol,)).fetchone()
        c.close()
        return {'price': dict(zip(['ts','symbol','price','volume','bid','ask','spread'], p)) if p else None,
                'regime': dict(zip(['ts','symbol','regime','atr','adx','vol_z'], r)) if r else None}
    else:
        rows = c.execute("SELECT p.symbol, p.price, r.regime FROM prices p JOIN regime r ON p.symbol=r.symbol AND p.ts=r.ts WHERE p.ts = (SELECT MAX(ts) FROM prices)").fetchall()
        c.close()
        return [{'symbol': x[0], 'price': x[1], 'regime': x[2]} for x in rows]

def get_all_regimes():
    c = sqlite3.connect(DB, timeout=3)
    rows = c.execute("SELECT symbol, regime, atr, adx, vol_z FROM regime WHERE ts = (SELECT MAX(ts) FROM regime)").fetchall()
    c.close()
    return [{'symbol': x[0], 'regime': x[1], 'atr': x[2], 'adx': x[3], 'vol_z': x[4]} for x in rows]

if __name__ == '__main__':
    import sys
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == 'loop':
        print('Oracle loop started')
        while True:
            try: update()
            except Exception as e: print(f'error: {e}')
            time.sleep(INTERVAL)
    elif len(sys.argv) > 1 and sys.argv[1] == 'state':
        print(json.dumps(get_state(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == 'regimes':
        print(json.dumps(get_all_regimes(), indent=2, ensure_ascii=False))
    else:
        update()
        print(json.dumps(get_state(), indent=2, ensure_ascii=False))
