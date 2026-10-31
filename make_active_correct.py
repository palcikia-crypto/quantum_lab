#!/usr/bin/env python3
import json, os
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
ACTIVE = os.path.join(BASE, 'data/active_strategies.json')
GATE = os.path.join(BASE, 'data/gate_all.json')
EVO = os.path.join(BASE, 'data/evolution.json')
pairs = {}
if os.path.exists(GATE):
    gate = json.load(open(GATE))
    for r in gate.get('results', []):
        if r['verdict'] in ('GOLDEN', 'TRADE_NOW'):
            key = r['symbol'] + '_' + r['tf']
            pairs[key] = {'symbol': r['symbol'], 'tf': r['tf'], 'strategy': r['strategy'],
                'wr': r['L1']['wr'], 'n': r['L1']['n'], 'p': r['L1'].get('p', 1),
                'verdict': r['verdict'], 'score': r.get('score', 0),
                'model': r.get('model', 'current'), 'trade': True}
if os.path.exists(EVO):
    evo = json.load(open(EVO))
    for r in evo.get('top', []):
        if r['wr'] < 52: continue
        key = r['symbol'] + '_15m'
        if key not in pairs:
            pairs[key] = {'symbol': r['symbol'], 'tf': '15m', 'strategy': r['strategy'],
                'wr': r['wr'], 'n': r['n'], 'p': 0.01, 'verdict': 'WATCH',
                'score': r['wr'] / 10, 'model': 'current', 'trade': False}
out = {'updated_at': datetime.now().isoformat(), 'source': 'gate+evolution', 'pairs': pairs}
json.dump(out, open(ACTIVE, 'w'), indent=2, ensure_ascii=False)
print(f'Active: {len(pairs)} стратегий, {sum(1 for v in pairs.values() if v["trade"])} trade')
for k, v in pairs.items():
    print(f'  {k:20} {v["strategy"]:15} {v["verdict"]:10} trade={v["trade"]} WR={v["wr"]}%')
