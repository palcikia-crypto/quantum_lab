#!/usr/bin/env python3
"""okx_bot.py — торговый бот OKX (читает okx_active.json, торгует через REST)."""
import os, sys, json, time, sqlite3, urllib.request
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
LOG = os.path.join(BASE, 'logs/okx_bot.log')
API_KEY = os.environ.get('OKX_API_KEY', '')
API_SECRET = os.environ.get('OKX_API_SECRET', '')
API_PASSPHRASE = os.environ.get('OKX_API_PASSPHRASE', '')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def load_active():
    try:
        return json.load(open(ACTIVE)).get('pairs', {})
    except: return {}

def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def get_candles(symbol='BTC-USDT', bar='15m', limit=100):
    url = f'https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={bar}&limit={limit}'
    try:
        d = fetch_json(url)
        if d.get('code') != '0': return None
        rows = d.get('data', [])
        return {'o':[float(r[1]) for r in rows], 'h':[float(r[2]) for r in rows],
                'l':[float(r[3]) for r in rows], 'c':[float(r[4]) for r in rows],
                'v':[float(r[5]) for r in rows]}
    except: return None

def main():
    log('=== OKX BOT STARTED ===')
    if not API_KEY:
        log('⚠️ Нет OKX_API_KEY — бот работает в режиме наблюдения (без ордеров)')
    while True:
        active = load_active()
        if not active:
            log('active пуст — жду')
            time.sleep(60); continue
        log(f'active: {len(active)} пар')
        for key, cfg in active.items():
            symbol = cfg.get('symbol', key.split('_')[0])
            strat = cfg.get('strategy', '')
            log(f'  {symbol} {strat}')
        time.sleep(300)

if __name__ == '__main__':
    main()
