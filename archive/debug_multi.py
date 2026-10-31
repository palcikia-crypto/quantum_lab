#!/usr/bin/env python3
"""debug_multi.py — тест obi_short на 6ч/24ч, BTC/XRP/SOL."""
import os, sys, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_scalp_strategies import SCALP_STRATEGIES
from filter_optimizer_mini import load_data, simulate

SYMBOLS = ['BTC-USDT', 'XRP-USDT', 'SOL-USDT']
PERIODS = [('6h', 6*3600), ('24h', 24*3600)]
TPSL = [(0.0015, 0.001, 120), (0.001, 0.001, 120)]

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

now = int(time.time())

for p_name, p_sec in PERIODS:
    log(f'=== {p_name} ===')
    for sym in SYMBOLS:
        obs, trades, fundings = load_data(sym, now - p_sec, now)
        if not obs:
            log(f'  {sym}: нет данных')
            continue
        for tp, sl, timeout in TPSL:
            res = simulate(obs, trades, fundings, -0.4, 0.00005, 0, 0.0005, tp, sl, timeout)
            n = res.get('n', 0)
            wr = res.get('wr', 0)
            pnl = res.get('pnl', 0)
            log(f'  {sym:12s} TP={tp*100:.2f}% SL={sl*100:.2f}% → n={n}, WR={wr:.1f}%, PnL={pnl:+.2f}%')
