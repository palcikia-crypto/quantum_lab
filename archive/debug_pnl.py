#!/usr/bin/env python3
"""debug_pnl.py — проверка PnL для obi_short на SOL."""
import os, sys, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_scalp_strategies import SCALP_STRATEGIES

OB_DB = os.path.join(BASE, 'data/orderbook.db')
SYMBOL = 'SOL-USDT'
STRAT_FN = SCALP_STRATEGIES['scalp_obi_short']
PERIOD = 3600
TP, SL, TIMEOUT, FEE = 0.0015, 0.00075, 60, 0.0005

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

c = sqlite3.connect(OB_DB, timeout=10)
now = int(time.time())
obs = c.execute("""SELECT ts, best_bid, best_ask, spread, imbalance
                   FROM orderbooks WHERE symbol=? AND ts>=? ORDER BY ts""",
                (SYMBOL, now - PERIOD)).fetchall()
c.close()

log(f'obs={len(obs)}')

trades = []
cooldown = 0
for i, ob in enumerate(obs):
    ts, bid, ask, spread, obi = ob
    if ts < cooldown: continue
    if obi is None or obi >= -0.4: continue

    entry = bid
    tp_p = entry * (1 - TP)
    sl_p = entry * (1 + SL)
    exit_p = None
    exit_type = None
    for j in range(i + 1, len(obs)):
        o_ts, o_bid, o_ask = obs[j][0], obs[j][1], obs[j][2]
        if o_ts - ts > TIMEOUT:
            exit_p = (o_bid + o_ask) / 2
            exit_type = 'timeout'
            break
        if o_ask >= sl_p:
            exit_p = sl_p
            exit_type = 'SL'
            break
        if o_bid <= tp_p:
            exit_p = tp_p
            exit_type = 'TP'
            break
    if exit_p is None: continue

    move = (entry - exit_p) / entry
    pnl = (move - FEE) * 100
    trades.append({'pnl': pnl, 'type': exit_type})
    cooldown = ts + TIMEOUT

n = len(trades)
wins = sum(1 for t in trades if t['pnl'] > 0)
pnl_sum = sum(t['pnl'] for t in trades)
tp_count = sum(1 for t in trades if t['type'] == 'TP')
sl_count = sum(1 for t in trades if t['type'] == 'SL')
to_count = sum(1 for t in trades if t['type'] == 'timeout')

log(f'Сделок: {n}')
log(f'TP: {tp_count}, SL: {sl_count}, timeout: {to_count}')
log(f'Побед: {wins}, WR: {100.0*wins/n:.1f}%')
log(f'PnL: {pnl_sum:+.2f}%')
log(f'Средний PnL: {pnl_sum/n:+.4f}%')
