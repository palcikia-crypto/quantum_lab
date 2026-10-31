#!/usr/bin/env python3
"""filter_test_raw.py — тест БЕЗ фильтров: есть ли сигналы obi_short?"""
import os, sys, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_scalp_strategies import SCALP_STRATEGIES

OB_DB = os.path.join(BASE, 'data/orderbook.db')
SYMBOL = 'SOL-USDT'
STRAT_NAME = 'scalp_obi_short'
STRAT_FN = SCALP_STRATEGIES[STRAT_NAME]
PERIOD = 3600

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

def load_data(symbol, start_ts, end_ts):
    c = sqlite3.connect(OB_DB, timeout=10)
    obs = c.execute("""SELECT ts, best_bid, best_ask, spread, imbalance
                       FROM orderbooks WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                    (symbol, start_ts, end_ts)).fetchall()
    trades = c.execute("""SELECT ts, side, price, volume FROM trades
                          WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                       (symbol, start_ts, end_ts)).fetchall()
    c.close()
    return obs, trades

def main():
    log('=== RAW TEST (без фильтров) ===')
    now = int(time.time())
    obs, trades = load_data(SYMBOL, now - PERIOD, now)
    log(f'obs={len(obs)}, trades={len(trades)}')

    # Сколько раз obi < -0.4?
    obi_below = sum(1 for ob in obs if ob[4] is not None and ob[4] < -0.4)
    log(f'obi < -0.4: {obi_below} раз')

    # Сколько раз spread < 0.0005? (но spread в orderbook.db — в % или долях?)
    spreads = [ob[3] for ob in obs if ob[3] is not None]
    if spreads:
        log(f'spread: min={min(spreads):.6f}, max={max(spreads):.6f}, avg={sum(spreads)/len(spreads):.6f}')

    # Сколько раз pressure > -500?
    trades_by_ts = defaultdict(list)
    for t in trades:
        trades_by_ts[t[0]].append(t)

    pressure_above = 0
    for ob in obs:
        ts = ob[0]
        buy = sum(t[3] for t in trades if t[1]=='buy' and ts-60 <= t[0] <= ts)
        sell = sum(t[3] for t in trades if t[1]=='sell' and ts-60 <= t[0] <= ts)
        pressure = buy - sell
        if pressure > -500:
            pressure_above += 1
    log(f'pressure > -500: {pressure_above} раз')

    # Сколько раз funding < 0.00005?
    c = sqlite3.connect(OB_DB, timeout=10)
    fundings = c.execute("""SELECT ts, funding_rate FROM funding
                            WHERE symbol=? AND ts>=? ORDER BY ts""",
                         (SYMBOL + '-SWAP', now - PERIOD - 3600)).fetchall()
    c.close()
    if fundings:
        fr_values = [f[1] for f in fundings]
        log(f'funding: min={min(fr_values):.6f}, max={max(fr_values):.6f}, avg={sum(fr_values)/len(fr_values):.6f}')
        log(f'funding < 0.00005: {sum(1 for f in fr_values if f < 0.00005)} раз')

    # Сигналы obi_short (без фильтров)
    signals = 0
    for ob in obs:
        ts, bid, ask, spread, obi = ob
        if obi is None: continue
        side = STRAT_FN(obi, 0, spread, (bid+ask)/2, 0)
        if side == 'SHORT':
            signals += 1
    log(f'Сигналов obi_short (без фильтров): {signals}')

if __name__ == '__main__':
    main()
