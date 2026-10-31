#!/usr/bin/env python3
"""okx_gate.py — гейт для OKX: прогоняет стратегии на свечах из okx.db."""
import os, sys, sqlite3, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/okx.db')
OUT = os.path.join(BASE, 'data/okx_gate.json')

def load_candles(symbol='BTC-USDT', tf='15m'):
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? ORDER BY ts", (symbol, tf)).fetchall()
    c.close()
    if len(rows) < 100: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def simulate(up, dn, o, c, start=20, fee=0.001):
    trades = []
    hi = min(len(c)-1, len(c))
    for i in range(start, hi):
        if up[i]:
            entry = o[i+1] if i+1 < len(o) else c[i]
            exit_p = c[i+1] if i+1 < len(c) else c[i]
            trades.append((exit_p - entry) / entry - fee)
        elif dn[i]:
            entry = o[i+1] if i+1 < len(o) else c[i]
            exit_p = c[i+1] if i+1 < len(c) else c[i]
            trades.append((entry - exit_p) / entry - fee)
    return trades

def check_l1(pnls):
    n = len(pnls)
    if n < 50: return {'wr': 0, 'n': n, 'pass': False}
    wins = sum(1 for p in pnls if p > 0)
    wr = 100 * wins / n
    return {'wr': round(wr,1), 'n': n, 'pass': wr >= 52 and n >= 50}

def run_gate(symbol, tf, strat_name, strat_fn):
    data = load_candles(symbol, tf)
    if not data: return None
    o,h,l,c,v = data['o'], data['h'], data['l'], data['c'], data['v']
    try:
        up, dn = strat_fn(o,h,l,c,v,{})
    except Exception as e:
        return None
    from okx_sim import simulate_scalp, check_l1 as sim_l1
    pnls = simulate_scalp(up, dn, o, h, l, c, sl_pct=0.003, tp_pct=0.005, fee=0.001)
    L1 = sim_l1(pnls)
    verdict = 'GOLDEN' if L1['pass'] else 'SKIP'
    return {'symbol': symbol, 'tf': tf, 'strategy': strat_name,
            'verdict': verdict, 'L1': L1, 'score': 10.0 if L1['pass'] else 0.0}

if __name__ == '__main__':
    from strategy_pool import STRATEGIES
    results = []
    for name, fn in STRATEGIES.items():
        try:
            r = run_gate('BTC-USDT', '15m', name, fn)
            if r: results.append(r)
        except: pass
    from collections import Counter
    c = Counter(r['verdict'] for r in results)
    print(f'Прогонов: {len(results)}')
    print(f'Вердикты: {dict(c)}')
    print()
    print('GOLDEN (OKX):')
    for r in results:
        if r['verdict'] == 'GOLDEN':
            print(f"  {r['strategy']}: WR={r['L1']['wr']}% n={r['L1']['n']}")
    json.dump({'results': results}, open(OUT, 'w'), indent=2)
    print(f'\n✅ сохранено в {OUT}')
