#!/usr/bin/env python3
"""debug_multi_mini.py — тест obi_short на 6ч, BTC/XRP/SOL."""
import os, sys, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from filter_optimizer_mini import load_data, simulate

SYMBOLS = ['BTC-USDT', 'XRP-USDT', 'SOL-USDT']
PERIOD = 6*3600
TP, SL, TIMEOUT = 0.0015, 0.001, 120

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

now = int(time.time())

for sym in SYMBOLS:
    obs, trades, fundings = load_data(sym, now - PERIOD, now)
    if not obs:
        log(f'  {sym}: нет данных')
        continue
    res = simulate(obs, trades, fundings, -0.4, 0.00005, 0, 0.0005, TP, SL, TIMEOUT)
    n = res.get('n', 0)
    wr = res.get('wr', 0)
    pnl = res.get('pnl', 0)
    log(f'  {sym:12s} n={n:3d}, WR={wr:5.1f}%, PnL={pnl:+6.2f}%')
