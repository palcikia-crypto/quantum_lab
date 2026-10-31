#!/usr/bin/env python3
"""run_gate_all.py — gate на всех ТФ (15m + 4h). Автоматически."""
import sys, os, json
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
from strategy_pool import STRATEGIES
from gate_v3 import run_gate
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT']
TFS = [('15m','current'), ('4h','open')]
results = []
for tf, model in TFS:
    for pair in PAIRS:
        for name, fn in STRATEGIES.items():
            try:
                r = run_gate(pair, tf, name, fn, model=model, use_h1=True)
                if r and r['L1']['n'] >= 100: results.append(r)
            except: pass
results.sort(key=lambda x: (-x['score'], -x['L1']['wr']))
summary = {v: sum(1 for r in results if r['verdict']==v) for v in ['GOLDEN','TRADE_NOW','WATCH','SKIP']}
with open(os.path.join(BASE,'data/gate_all.json'),'w') as f:
    json.dump({'timestamp':datetime.now().isoformat(),'summary':summary,'results':results}, f, indent=2, ensure_ascii=False)
print(f'GATE ALL: {summary}, прогонов: {len(results)}')
