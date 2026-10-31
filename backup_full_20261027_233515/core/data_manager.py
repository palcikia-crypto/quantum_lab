#!/usr/bin/env python3
"""data_manager.py — качает данные с Binance на все ТФ/пары/сроки.
Своя БД market.db. Старую klines.db не трогает."""
import os, json, time, sqlite3, urllib.request
from datetime import datetime, timedelta

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/market.db')
CFG = json.load(open(os.path.join(BASE, 'config/lab.json')))

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/data_manager.log'), 'a') as f: f.write(line+'\n')

def init_db():
    c = sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS candles (
        symbol TEXT, tf TEXT, ts INTEGER,
        o REAL, h REAL, l REAL, c REAL, v REAL,
        PRIMARY KEY (symbol, tf, ts)
    );
    CREATE INDEX IF NOT EXISTS idx_candles ON candles(symbol, tf, ts);
    CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
    ''')
    c.commit(); c.close()

def fetch_klines(symbol, interval, start_ms, end_ms, limit=1000):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&startTime={start_ms}&endTime={end_ms}&limit={limit}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def get_last_ts(symbol, tf):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT MAX(ts) FROM candles WHERE symbol=? AND tf=?", (symbol, tf)).fetchone()
    c.close()
    return r[0] if r and r[0] else 0

def save_candles(symbol, tf, rows):
    c = sqlite3.connect(DB)
    data = [(symbol, tf, int(r[0]//1000), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in rows]
    c.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)", data)
    c.commit(); c.close()
    return len(data)

def update_pair_tf(symbol, tf, days):
    interval = CFG['timeframes'][tf]['interval']
    end_ms = int(time.time() * 1000)
    start_ms = int((time.time() - days*86400) * 1000)
    last_ts = get_last_ts(symbol, tf)
    if last_ts:
        start_ms = max(start_ms, last_ts * 1000 + 1)
    total = 0
    while start_ms < end_ms:
        try:
            rows = fetch_klines(symbol, interval, start_ms, end_ms, 1000)
            if not rows: break
            n = save_candles(symbol, tf, rows)
            total += n
            start_ms = int(rows[-1][0]) + 1
            if len(rows) < 1000: break
            time.sleep(0.1)
        except Exception as e:
            log(f'  {symbol} {tf}: ошибка {e}'); time.sleep(2); break
    return total

def update_all(only_pair=None, only_tf=None):
    init_db()
    log('=== DATA UPDATE START ===')
    pairs = [only_pair] if only_pair else CFG['pairs']
    tfs = [only_tf] if only_tf else list(CFG['timeframes'].keys())
    total = 0
    for pair in pairs:
        for tf in tfs:
            days = CFG['timeframes'][tf]['days']
            n = update_pair_tf(pair, tf, days)
            if n: log(f'  {pair} {tf}: +{n} свечей')
            total += n
    log(f'=== DONE: +{total} свечей ===')
    return total

def stats():
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT symbol, tf, COUNT(*), MAX(ts) FROM candles GROUP BY symbol, tf").fetchall()
    c.close()
    return [{'symbol': r[0], 'tf': r[1], 'count': r[2], 'last': datetime.fromtimestamp(r[3]).isoformat() if r[3] else None} for r in rows]

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--stats':
        for s in stats(): print(s)
    elif len(sys.argv) > 1 and sys.argv[1] == '--test':
        update_all('BTCUSDT', '1h')
    else:
        update_all()
