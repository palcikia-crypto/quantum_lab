#!/usr/bin/env python3
"""debug_sim_tpsl.py — проверка simulate с разными TP/SL."""
import os, sys, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from filter_optimizer_mini import load_data, simulate

OB_DB = os.path.join(BASE, 'data/orderbook.db')
SYMBOL = 'SOL-USDT'
PERIOD = 3600

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

now = int(time.time())
obs, trades, fundings = load_data(SYMBOL, now - PERIOD, now)
log(f'obs={len(obs)}, trades={len(trades)}, fundings={len(fundings)}')

# Тестируем разные TP/SL
TPSL_LIST = [
    (0.0005, 0.0005, 60),
    (0.001, 0.0005, 60),
    (0.0015, 0.00075, 60),
    (0.001, 0.001, 120),
    (0.0015, 0.001, 120),
]

for tp, sl, timeout in TPSL_LIST:
    res = simulate(obs, trades, fundings, -0.4, 0.00005, 0, 0.0005, tp, sl, timeout)
    n = res.get('n', 0)
    wr = res.get('wr', 0)
    pnl = res.get('pnl', 0)
    log(f'TP={tp*100:.2f}% SL={sl*100:.2f}% TO={timeout}s → n={n}, WR={wr:.1f}%, PnL={pnl:+.2f}%')

