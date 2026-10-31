#!/usr/bin/env python3
"""debug_simulate.py — пошаговая диагностика: где обрывается simulate."""
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
trades = c.execute("""SELECT ts, side, price, volume FROM trades
                      WHERE symbol=? AND ts>=? ORDER BY ts""",
                   (SYMBOL, now - PERIOD)).fetchall()
swap = SYMBOL + '-SWAP'
fundings = c.execute("""SELECT ts, funding_rate FROM funding
                        WHERE symbol=? AND ts>=? ORDER BY ts""",
                     (swap, now - PERIOD - 3600)).fetchall()
c.close()

log(f'obs={len(obs)}, trades={len(trades)}, fundings={len(fundings)}')

# Шаг 1: сколько раз strat_fn даёт SHORT (без фильтров)
signals = 0
for ob in obs:
    ts, bid, ask, spread, obi = ob
    if obi is None: continue
    side = STRAT_FN(obi, 0, spread, (bid+ask)/2, 0)
    if side == 'SHORT':
        signals += 1
log(f'Шаг 1: сигналов obi_short (без фильтров): {signals}')

# Шаг 2: сколько раз obi < -0.4
obi_below = sum(1 for ob in obs if ob[4] is not None and ob[4] < -0.4)
log(f'Шаг 2: obi < -0.4: {obi_below}')

# Шаг 3: сколько раз obi < -0.4 AND spread < 0.0005
both = sum(1 for ob in obs if ob[4] is not None and ob[4] < -0.4 and ob[3] is not None and ob[3] < 0.0005)
log(f'Шаг 3: obi < -0.4 AND spread < 0.0005: {both}')

# Шаг 4: + funding > 0.00005
funding_by_ts = {f[0]: f[1] for f in fundings}
def get_funding(ts):
    prev = None
    for fts in sorted(funding_by_ts):
        if fts <= ts: prev = funding_by_ts[fts]
        else: break
    return prev

step4 = 0
for ob in obs:
    ts, bid, ask, spread, obi = ob
    if obi is None or obi >= -0.4: continue
    if spread is None or spread > 0.0005: continue
    fr = get_funding(ts)
    if fr is not None and fr > 0.00005:
        step4 += 1
log(f'Шаг 4: + funding > 0.00005: {step4}')

# Шаг 5: + pressure < 0
step5 = 0
for ob in obs:
    ts, bid, ask, spread, obi = ob
    if obi is None or obi >= -0.4: continue
    if spread is None or spread > 0.0005: continue
    fr = get_funding(ts)
    if fr is not None and fr > 0.00005:
        buy = sum(t[3] for t in trades if t[1]=='buy' and ts-60 <= t[0] <= ts)
        sell = sum(t[3] for t in trades if t[1]=='sell' and ts-60 <= t[0] <= ts)
        pressure = buy - sell
        if pressure < 0:
            step5 += 1
log(f'Шаг 5: + pressure < 0: {step5}')

# Шаг 6: сколько сделок закрылось (TP/SL/timeout)
step6 = 0
for ob in obs:
    ts, bid, ask, spread, obi = ob
    if obi is None or obi >= -0.4: continue
    if spread is None or spread > 0.0005: continue
    fr = get_funding(ts)
    if fr is None or fr <= 0.00005: continue
    buy = sum(t[3] for t in trades if t[1]=='buy' and ts-60 <= t[0] <= ts)
    sell = sum(t[3] for t in trades if t[1]=='sell' and ts-60 <= t[0] <= ts)
    pressure = buy - sell
    if pressure >= 0: continue

    # Вход
    entry = bid
    tp_p = entry * (1 - TP)
    sl_p = entry * (1 + SL)
    exit_p = None
    for j, ob2 in enumerate(obs):
        if ob2[0] <= ts: continue
        if ob2[0] - ts > TIMEOUT:
            exit_p = (ob2[1] + ob2[2]) / 2
            break
        for t in trades:
            if t[0] != ob2[0]: continue
            p = t[2]
            if p >= sl_p: exit_p = sl_p; break
            if p <= tp_p: exit_p = tp_p; break
        if exit_p is not None: break
    if exit_p is not None:
        step6 += 1

log(f'Шаг 6: закрылось (TP/SL/timeout): {step6}')

# Шаг 7: PnL
if step6 > 0:
    log(f'Шаг 7: PnL — есть сделки ({step6})')
else:
    log(f'Шаг 7: PnL — НЕТ закрытых сделок')

