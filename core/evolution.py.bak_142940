#!/usr/bin/env python3
"""evolution.py — эволюция: L1 grid -> L2 features -> L3 mutations. Работает на market.db."""
import os, sys, json, sqlite3
import numpy as np
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from strategy_pool import STRATEGIES
from gate_v3 import load_candles, apply_h1_filter, simulate

PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT']
TF = '15m'; MODEL = 'current'

def evaluate(symbol, name, fn):
    data = load_candles(symbol, TF)
    if not data or len(data['c']) < 100: return None
    up, dn = fn(data['o'],data['h'],data['l'],data['c'],data['v'],{})
    up, dn = apply_h1_filter(up, dn, symbol, data['ts'])
    pnls = simulate(up, dn, data['o'], data['c'], model=MODEL)
    if len(pnls) < 100: return None
    wins = sum(1 for p in pnls if p > 0)
    return {'symbol': symbol, 'strategy': name, 'wr': round(100*wins/len(pnls),1),
            'n': len(pnls), 'score': round(100*wins/len(pnls) * min(len(pnls),1000)/100,2)}

def L1_grid():
    results = []
    for pair in PAIRS:
        for name, fn in STRATEGIES.items():
            r = evaluate(pair, name, fn)
            if r: results.append(r)
    return results

def L2_features(base):
    return sorted(base, key=lambda x: -x['score'])[:20]

def L3_mutations(top):
    # мутации: top-20 без изменений (реальные мутации требуют переопределения)
    return top

def main():
    import os as _os
    try:
        load = float(open('/proc/loadavg').read().split()[0])
    except:
        load = 0
    if load > 6:
        print(f'load {load:.1f} > 6, пропускаю (не перегружать)'); return
    print('=== EVOLUTION START ===', flush=True)
    l1 = L1_grid(); print(f'L1: {len(l1)} результатов', flush=True)
    l2 = L2_features(l1); print(f'L2: {len(l2)} топ', flush=True)
    l3 = L3_mutations(l2); print(f'L3: {len(l3)} финальных', flush=True)
    out = {'timestamp': datetime.now().isoformat(), 'L1': len(l1), 'L2': len(l2), 'L3': len(l3), 'top': l3}
    with open(os.path.join(BASE, 'data/evolution.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print('Сохранено: evolution.json', flush=True)
    for r in l3[:10]: print(f'  {r["symbol"]:10} {r["strategy"]:15} WR={r["wr"]}% n={r["n"]}', flush=True)

if __name__ == '__main__': main()
