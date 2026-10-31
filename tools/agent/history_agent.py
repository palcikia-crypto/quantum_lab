#!/usr/bin/env python3
"""Backfill: качает историю от now-days до now, независимо от последней свечи."""
import os, sys, sqlite3, time, urllib.request, json
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DATA = os.path.join(BASE, 'data')
LOG = os.path.join(BASE, 'logs/agent.log')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
TARGET_DAYS = 730
TFS = {'15m': '15m', '1h': '1H', '4h': '4H'}
UA = {'User-Agent': 'Mozilla/5.0'}

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] [history] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_coverage(sym, tf):
    try:
        c = sqlite3.connect(os.path.join(DATA, 'market.db'))
        r = c.execute("SELECT MIN(ts), MAX(ts), COUNT(*) FROM candles WHERE symbol=? AND tf=?", (sym, tf)).fetchone()
        c.close()
        if not r or not r[0]: return {'days': 0, 'rows': 0}
        return {'days': round((r[1]-r[0])/86400, 1), 'rows': r[2]}
    except: return {'days': 0, 'rows': 0}

def fetch_okx(sym, bar, before_ms):
    """OKX: history-candles, before=timestamp (качает в прошлое)."""
    sym_okx = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    url = f'https://www.okx.com/api/v5/market/history-candles?instId={sym_okx}&bar={bar}&limit=100'
    if before_ms: url += f'&after={before_ms}'
    try:
        req = urllib.request.Request(url, headers=UA)
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if d.get('code') != '0': return []
        return d.get('data', [])
    except Exception as e:
        log(f'  ⚠️ fetch {sym} {bar}: {e}')
        return []

def backfill(sym, tf, days):
    """Качает историю от now-days до now, независимо от последней свечи."""
    bar = TFS[tf]
    end_ms = int(time.time() * 1000)
    start_ms = int((time.time() - days*86400) * 1000)
    before = end_ms
    total = 0
    c = sqlite3.connect(os.path.join(DATA, 'market.db'))
    for page in range(300):
        rows = fetch_okx(sym, bar, before)
        if not rows: break
        n = 0
        for row in rows:
            ts = int(row[0]) // 1000
            if ts < start_ms // 1000: continue  # старые — стоп
            o,h,l,cl,v = map(float, row[1:6])
            c.execute("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)",
                      (sym, tf, ts, o, h, l, cl, v))
            n += 1
        c.commit()
        total += n
        if n == 0: break
        # следующая страница — ещё раньше
        before = int(rows[-1][0])
        if before <= start_ms: break
        if (page+1) % 10 == 0:
            log(f'  {sym} {tf}: +{total} (стр {page+1})')
        time.sleep(0.15)
    c.close()
    return total

def main():
    log('=== HISTORY BACKFILL ===')
    for sym in PAIRS:
        for tf in TFS:
            cov = get_coverage(sym, tf)
            need = TARGET_DAYS - cov['days']
            if need <= 5:  # хватает
                log(f'✅ {sym} {tf}: {cov["days"]} дней — ок')
                continue
            log(f'⬇️ {sym} {tf}: {cov["days"]} → {TARGET_DAYS} дней (качаем {int(need)})')
            n = backfill(sym, tf, TARGET_DAYS)
            cov2 = get_coverage(sym, tf)
            log(f'  📊 {sym} {tf}: +{n} свечей, теперь {cov2["days"]} дней / {cov2["rows"]} строк')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
