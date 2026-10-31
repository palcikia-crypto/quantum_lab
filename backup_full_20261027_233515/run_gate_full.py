#!/usr/bin/env python3
"""run_gate_full.py — gate L1-L13. Использует full_access для 34 стратегий."""
import sys, os, json
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
from full_access import load_all_strategies, full_gate
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT']
TFS = [('15m','current'), ('4h','open')]
strategies = load_all_strategies()
print(f'Стратегий: {len(strategies)}', flush=True)
results = []
for tf, model in TFS:
    print(f'--- {tf} ---', flush=True)
    for pair in PAIRS:
        for name, fn in strategies.items():
            try:
                r = full_gate(pair, tf, name, fn, model=model)
                if r and r['L1']['n'] >= 100:
                    results.append(r)
            except: pass
        print(f'  {pair}: {len(results)} прошло', flush=True)
results.sort(key=lambda x: (-x.get('L8-L13_pass', 0), -x['score'], -x['L1']['wr']))
summary = {v: sum(1 for r in results if r['verdict']==v) for v in ['GOLDEN','TRADE_NOW','WATCH','SKIP']}
with open(os.path.join(BASE, 'data/gate_all.json'), 'w') as f:
    json.dump({'timestamp': datetime.now().isoformat(), 'summary': summary, 'results': results}, f, indent=2, ensure_ascii=False)
print(f'\nGATE FULL: {summary}, прогонов: {len(results)}', flush=True)
for r in results[:10]:
    l813 = r.get('L8-L13_pass', '-')
    print(f'  {r["symbol"]:10} {r["tf"]:3} {r["strategy"]:15} {r["verdict"]:10} WR={r["L1"]["wr"]}% L8-13={l813}/6', flush=True)
