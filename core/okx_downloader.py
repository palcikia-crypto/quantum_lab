#!/usr/bin/env python3
"""okx_downloader.py — автономная докачка (BTC/ETH/XRP/SOL/DOGE)."""
import json, sqlite3, os, urllib.request, time
DB = os.path.expanduser('~/quantum_lab/data/okx.db')
UA = {'User-Agent': 'Mozilla/5.0'}

def download(symbol='BTC-USDT', bar='15m', max_pages=50):
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS candles (symbol TEXT, tf TEXT, ts INTEGER,
        o REAL, h REAL, l REAL, c REAL, v REAL, PRIMARY KEY (symbol, tf, ts))''')
    c.commit()
    row = c.execute("SELECT MIN(ts) FROM candles WHERE symbol=? AND tf=?", (symbol, bar)).fetchone()
    c.close()
    after = str(row[0] * 1000) if row and row[0] else None
    total = 0
    for page in range(max_pages):
        url = f'https://www.okx.com/api/v5/market/history-candles?instId={symbol}&bar={bar}&limit=100'
        if after: url += f'&after={after}'
        try:
            req = urllib.request.Request(url, headers=UA)
            d = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if d.get('code') != '0': break
            rows = d.get('data', [])
            if not rows: break
            c = sqlite3.connect(DB)
            for row in rows:
                ts = int(row[0]) // 1000
                o,h,l,cl,v = map(float, row[1:6])
                c.execute('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)',
                          (symbol, bar, ts, o,h,l,cl,v))
                total += 1
            c.commit(); c.close()
            after = rows[-1][0]
            if (page+1) % 20 == 0: print(f'  {symbol}: +{total}')
            time.sleep(0.12)
        except Exception as e:
            print(f'⚠️ {symbol}: {e}'); break
    print(f'✅ {symbol}: +{total}')
    return total

if __name__ == '__main__':
    for sym in ['BTC-USDT','ETH-USDT','XRP-USDT','SOL-USDT','DOGE-USDT']:
        download(sym, '15m', 50)
