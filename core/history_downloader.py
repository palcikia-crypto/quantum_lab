#!/usr/bin/env python3
"""history_downloader.py — универсальный загрузчик истории: Binance + Polymarket."""
import os, sys, json, time, sqlite3, urllib.request
from datetime import datetime, timedelta

BASE = os.path.expanduser('~/quantum_lab')
DB_BINANCE = os.path.join(BASE, 'data/market.db')
DB_POLY = os.path.join(BASE, 'data/market_polymarket.db')
UA = {'User-Agent': 'Mozilla/5.0'}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

# ═══ BINANCE ═══
def download_binance(symbol, interval='15m', start_date=None, end_date=None):
    """Скачивает свечи Binance и сохраняет в market.db."""
    if not start_date: start_date = datetime.now() - timedelta(days=30)
    if not end_date: end_date = datetime.now()
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    c = sqlite3.connect(DB_BINANCE)
    c.execute('''CREATE TABLE IF NOT EXISTS candles (
        symbol TEXT, tf TEXT, ts INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL,
        PRIMARY KEY (symbol, tf, ts))''')
    c.commit()
    
    total = 0
    cur = start_ts
    while cur < end_ts:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&startTime={cur}&limit=1000'
        try:
            data = fetch(url)
        except Exception as e:
            print(f'⚠️ Binance {symbol} {interval}: {e}')
            break
        if not data: break
        rows = [(symbol, interval, int(k[0]//1000), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])) for k in data]
        c.executemany('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)', rows)
        c.commit()
        total += len(rows)
        cur = int(data[-1][0]) + 1
        print(f'  {symbol} {interval}: +{len(rows)} (всего {total})')
        if len(data) < 1000: break
        time.sleep(0.2)
    c.close()
    print(f'✅ Binance {symbol} {interval}: {total} свечей')
    return total

# ═══ POLYMARKET ═══
def download_polymarket(symbol, start_date=None, end_date=None):
    """Скачивает историю цен Polymarket для 15m рынков."""
    if not start_date: start_date = datetime.now() - timedelta(days=7)
    if not end_date: end_date = datetime.now()
    
    c = sqlite3.connect(DB_POLY)
    c.execute('''CREATE TABLE IF NOT EXISTS poly_prices (
        symbol TEXT, token TEXT, side TEXT, ts INTEGER, price REAL,
        PRIMARY KEY (symbol, token, ts))''')
    c.commit()
    
    # Проходим по 15m окнам
    cur = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    total = 0
    while cur < end_ts:
        window = (cur // 900) * 900
        slug = f'{symbol.lower()}-updown-15m-{window}'
        try:
            d = fetch(f'https://gamma-api.polymarket.com/events?slug={slug}')
            if d:
                m = d[0]['markets'][0]
                clob = m.get('clobTokenIds')
                if isinstance(clob, str): clob = json.loads(clob)
                for side, token in zip(['up','down'], clob):
                    # Пробуем bucket 1800 (30 мин) — единственный доступный для старых
                    hist_url = f'https://clob.polymarket.com/prices-history?market={token}&interval=max&fidelity=30'
                    try:
                        hist = fetch(hist_url)
                        data = hist.get('history', []) if isinstance(hist, dict) else hist
                        rows = [(symbol, token, side, int(p['t']), float(p['p'])) for p in data if 't' in p and 'p' in p]
                        if rows:
                            c.executemany('INSERT OR REPLACE INTO poly_prices VALUES (?,?,?,?,?)', rows)
                            c.commit()
                            total += len(rows)
                            print(f'  {slug} {side}: +{len(rows)}')
                    except Exception as e:
                        pass
        except Exception as e:
            pass
        cur = window + 900
        time.sleep(0.3)
    c.close()
    print(f'✅ Polymarket {symbol}: {total} цен')
    return total

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['binance','polymarket'], required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--interval', default='15m')
    parser.add_argument('--days', type=int, default=7)
    args = parser.parse_args()
    
    start = datetime.now() - timedelta(days=args.days)
    if args.source == 'binance':
        download_binance(args.symbol, args.interval, start)
    else:
        download_polymarket(args.symbol, start)
