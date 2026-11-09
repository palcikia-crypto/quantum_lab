#!/usr/bin/env python3
"""okx_feed.py — сбор рыночных данных OKX (стакан + funding) в data/orderbook.db."""
import json, os, sqlite3, time, urllib.request

BASE = os.path.expanduser('~/quantum_lab')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
ACTIVE = os.path.join(BASE, 'data/okx_active_v4.json')
LOG = os.path.join(BASE, 'logs/okx_feed.log')

DEFAULT = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT',
           'ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT']


def log(m):
    line = '[%s] %s' % (time.strftime('%H:%M:%S'), m)
    print(line, flush=True)
    try:
        with open(LOG, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


def to_inst(sym):
    if '-' in sym:
        return sym
    if sym.endswith('USDT'):
        return sym[:-4] + '-USDT'
    return sym


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'quantum-lab/1.0'})
    with urllib.request.urlopen(req, timeout=10) as f:
        return json.load(f)


def fetch_book(inst):
    d = get('https://www.okx.com/api/v5/market/books?instId=%s&sz=20' % inst)
    book = d['data'][0]
    bid = book['bids'][0]
    ask = book['asks'][0]
    bv = sum(float(x[1]) for x in book['bids'])
    av = sum(float(x[1]) for x in book['asks'])
    imb = (bv - av) / (bv + av) if (bv + av) else 0.0
    return imb, float(bid[0]), float(ask[0])


def fetch_funding(inst):
    d = get('https://www.okx.com/api/v5/public/funding-rate?instId=%s-SWAP' % inst)
    return float(d['data'][0]['fundingRate'])


def main():
    os.makedirs(os.path.dirname(OB_DB), exist_ok=True)
    c = sqlite3.connect(OB_DB, timeout=10)
    c.execute('CREATE TABLE IF NOT EXISTS orderbooks (symbol TEXT, ts INTEGER, imbalance REAL, best_bid REAL, best_ask REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS funding (symbol TEXT, ts INTEGER, funding_rate REAL)')
    c.commit()
    c.close()
    log('🟢 OKX FEED запущен')
    seen = set()
    while True:
        try:
            syms = []
            try:
                a = json.load(open(ACTIVE))
                syms = [v['symbol'] for v in a.get('pairs', {}).values()]
            except Exception:
                pass
            syms = syms or DEFAULT
            now = int(time.time())
            conn = sqlite3.connect(OB_DB, timeout=10)
            for s in syms:
                try:
                    inst = to_inst(s)
                    imb, bb, ba = fetch_book(inst)
                    conn.execute('INSERT INTO orderbooks VALUES (?,?,?,?,?)', (s, now, imb, bb, ba))
                    try:
                        fr = fetch_funding(inst)
                        conn.execute('INSERT INTO funding VALUES (?,?,?)', (s, now, fr))
                    except Exception:
                        pass
                    if s not in seen:
                        log('  ✅ %s: OBI=%.3f bid=%s ask=%s' % (s, imb, bb, ba))
                        seen.add(s)
                except Exception as e:
                    if s not in seen:
                        log('  ⚠️ %s: %s' % (s, e))
            conn.commit()
            conn.close()
        except Exception as e:
            log('FEED ERROR: %s' % e)
        time.sleep(3)


if __name__ == '__main__':
    main()
