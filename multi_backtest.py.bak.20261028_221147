#!/usr/bin/env python3
"""multi_backtest.py — многоуровневый бэктест 2д/7д/30д.
Оставляет только стратегии в плюс на ВСЕХ периодах.
Пишет data/okx_tpsl_by_regime.json (ТОП-2 на пару)."""
import os, sys, json, sqlite3, time
from collections import defaultdict
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE,'core'))
from okx_mutator import generate_mutants
muts = generate_mutants()

MARKET_DB = os.path.join(BASE,'data/market.db')
OUT = os.path.join(BASE,'data/okx_tpsl_by_regime.json')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
TOP_OKX = [
    'okx_vwap_rev_10', 'okx_vwap_rev_20', 'okx_vwap_rev_30',
    'okx_macd_5_35_5', 'okx_ema_7_25', 'okx_grid_sma_20',
    'okx_grid_sma_10', 'okx_ema_5_20', 'okx_ema_6_18',
    'okx_grid_sma_30', 'okx_ema_8_24', 'okx_donchian_20',
]
PERIODS = [('2d', 2*86400), ('7d', 7*86400), ('30d', 30*86400)]
TP, SL, TIMEOUT, FEE = 0.006, 0.004, 2, 0.0015
MIN_N = 5
MIN_PNL = 0.1


def load_candles(sym, start_ts, end_ts, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute(
        "SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? AND ts>=? AND ts<? ORDER BY ts",
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
        end = min(i+1+timeout, n); exit_p = None; reason = None
        for j in range(i+1, end):
            if side == 'LONG':
                if l[j] <= sl_p: exit_p = sl_p; reason='SL'; break
                if h[j] >= tp_p: exit_p = tp_p; reason='TP'; break
            else:
                if h[j] >= sl_p: exit_p = sl_p; reason='SL'; break
                if l[j] <= tp_p: exit_p = tp_p; reason='TP'; break
        if exit_p is None:
            jj = min(i+timeout, n-1); exit_p = c[jj]; reason='timeout'; last_i = jj
        else:
            last_i = i
        move = (exit_p - entry)/entry if side=='LONG' else (entry - exit_p)/entry
        pnl = (move - FEE) * 100
        trades.append({'pnl':float(pnl), 'reason':reason})
        i += 1
    return trades


def main():
    try:
        load = float(open('/proc/loadavg').read().split()[0])
    except:
        load = 0
    if load > 6:
        print(f'load {load:.1f} > 6, пропускаю')
        return
    print(f'=== MULTI BACKTEST {time.strftime("%Y-%m-%d %H:%M:%S")} ===')
    now = int(time.time())
    all_res = defaultdict(dict)
    for p_name, p_sec in PERIODS:
        start_ts = now - p_sec
        end_ts = now
        for sym in PAIRS:
            data = load_candles(sym, start_ts, end_ts)
            if not data: continue
            for strat in TOP_OKX:
                if strat not in muts: continue
                try:
                    up, dn = muts[strat](data['o'], data['h'], data['l'], data['c'], data['v'], {})
                except:
                    continue
                trades = sim_trades(up, dn, data['o'], data['h'], data['l'], data['c'], data['ts'])
                if not trades: continue
                n = len(trades); wins = sum(1 for t in trades if t['pnl']>0)
                pnl = sum(t['pnl'] for t in trades)
                all_res[(sym, strat)][p_name] = {'n':n, 'wr':100*wins/n, 'pnl':pnl}

    # Фильтр: в плюс на всех 3, n>=MIN_N, pnl>=MIN_PNL
    stable = []
    for (sym, strat), periods in all_res.items():
        ok = True
        for p_name, _ in PERIODS:
            if p_name not in periods: ok = False; break
            r = periods[p_name]
            if r['n'] < MIN_N or r['pnl'] < MIN_PNL: ok = False; break
        if ok:
            stable.append({'sym':sym, 'strat':strat, 'periods':periods,
                           'min_pnl': min(periods[p]['pnl'] for p, _ in PERIODS)})

    stable.sort(key=lambda x: -x['min_pnl'])
    print(f'Устойчивых: {len(stable)}')
    for s in stable[:15]:
        p = s['periods']
        print(f"  {s['sym']:10s} {s['strat']:22s} 2d={p['2d']['pnl']:+.2f} 7d={p['7d']['pnl']:+.2f} 30d={p['30d']['pnl']:+.2f} min={s['min_pnl']:+.2f}")

    if not stable:
        print('⚠️ Устойчивых нет — by_regime не изменён')
        return

    # ТОП-2 на пару -> by_regime
    by_pair = defaultdict(list)
    for s in stable:
        by_pair[s['sym']].append(s)

    new_pp = {}
    for sym, items in by_pair.items():
        sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
        items.sort(key=lambda x: -x['min_pnl'])
        top = items[:2]
        regs = {}
        for reg in ['flat', 'trend_up', 'trend_down']:
            regs[reg] = {
                'strategy': top[0]['strat'],
                'tp': TP, 'sl': SL, 'timeout_bars': TIMEOUT,
                'alt_strategy': top[1]['strat'] if len(top) > 1 else None,
                'min_pnl': round(top[0]['min_pnl'], 2),
            }
        new_pp[sym_dash] = regs

    out = {
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'source': 'multi_backtest',
        'params': {'tp':TP,'sl':SL,'timeout_bars':TIMEOUT,
                   'periods':[p[0] for p in PERIODS], 'min_n':MIN_N, 'min_pnl':MIN_PNL},
        'stable_count': len(stable),
        'per_pair': new_pp,
    }
    json.dump(out, open(OUT,'w'), indent=2, ensure_ascii=False)
    print(f'✅ Записано: {OUT} (пар: {len(new_pp)}, устойчивых: {len(stable)})')


if __name__ == '__main__':
    main()
