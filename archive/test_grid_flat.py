#!/usr/bin/env python3
"""test_grid_flat.py — тест grid_sma_20 в flat (бэктест на market.db)."""
import os, sys, sqlite3, time
import numpy as np
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_mutator import generate_mutants
from oracle import calc_regime

MARKET_DB = os.path.join(BASE, 'data/market.db')
PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
TP, SL, TIMEOUT, FEE = 0.006, 0.004, 2, 0.0015

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

def load_candles(sym, start_ts, end_ts, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute("""SELECT ts,o,h,l,c,v FROM candles
                        WHERE symbol=? AND tf=? AND ts>=? AND ts<? ORDER BY ts""",
                     (sym, tf, start_ts, end_ts)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def sim_trades(up, dn, o, h, l, c, ts, tp=TP, sl=SL, timeout=TIMEOUT, start=50):
    trades = []
    n = len(c)
    if n < start+2: return trades
    i = start; last_i = -1
    while i < n - 1:
        if i <= last_i: i += 1; continue
        side = None
        if up[i]: side = 'LONG'
        elif dn[i]: side = 'SHORT'
        if not side: i += 1; continue
        entry = c[i]
        tp_p = entry*(1+tp) if side=='LONG' else entry*(1-tp)
        sl_p = entry*(1-sl) if side=='LONG' else entry*(1+sl)
        end = min(i+1+timeout, n); exit_p = None
        for j in range(i+1, end):
            if side == 'LONG':
                if l[j] <= sl_p: exit_p = sl_p; break
                if h[j] >= tp_p: exit_p = tp_p; break
            else:
                if h[j] >= sl_p: exit_p = sl_p; break
                if l[j] <= tp_p: exit_p = tp_p; break
        if exit_p is None:
            jj = min(i+timeout, n-1); exit_p = c[jj]; last_i = jj
        else:
            last_i = i
        move = (exit_p - entry)/entry if side=='LONG' else (entry - exit_p)/entry
        pnl = (move - FEE) * 100
        trades.append({'pnl': float(pnl), 'regime': None})
        i += 1
    return trades

def main():
    log('=== TEST grid_sma_20 в flat ===')
    muts = generate_mutants()
    if 'okx_grid_sma_20' not in muts:
        log('❌ нет okx_grid_sma_20')
        return
    fn = muts['okx_grid_sma_20']

    now = int(time.time())
    # 7 дней
    start_ts = now - 7*86400

    all_trades = []
    for sym in PAIRS:
        data = load_candles(sym, start_ts, now)
        if not data: continue
        try:
            up, dn = fn(data['o'], data['h'], data['l'], data['c'], data['v'], {})
        except Exception as e:
            log(f'{sym}: ошибка {e}')
            continue

        # Определяем режим для каждого бара
        klines = [(int(data['ts'][i]), data['o'][i], data['h'][i], data['l'][i], data['c'][i], data['v'][i]) for i in range(len(data['ts']))]
        regimes = []
        for i in range(50, len(klines)):
            reg = calc_regime(klines[:i+1])
            regimes.append(reg['regime'])

        trades = sim_trades(up, dn, data['o'], data['h'], data['l'], data['c'], data['ts'])
        # Фильтр: только flat
        for i, t in enumerate(trades):
            if i < len(regimes) and regimes[i] == 'flat':
                all_trades.append({'pnl': t['pnl'], 'sym': sym})

    n = len(all_trades)
    wins = sum(1 for t in all_trades if t['pnl'] > 0)
    pnl = sum(t['pnl'] for t in all_trades)
    wr = 100.0 * wins / n if n else 0
    log(f'grid_sma_20 в flat: n={n}, wins={wins}, WR={wr:.1f}%, PnL={pnl:+.2f}%')

if __name__ == '__main__':
    main()
