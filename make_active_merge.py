#!/usr/bin/env python3
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
from history_manager import save_history
BASE = os.path.expanduser('~/quantum_lab')
ACTIVE = os.path.join(BASE, 'data/active_strategies.json')
GATE = os.path.join(BASE, 'data/gate_all.json')
EVO = os.path.join(BASE, 'data/evolution.json')
old = json.load(open(ACTIVE)) if os.path.exists(ACTIVE) else {'pairs': {}}
pairs = old.get('pairs', {})
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
        if key not in pairs or pairs[key]['verdict'] != 'GOLDEN':
            pairs[key] = {'symbol': r['symbol'], 'tf': '15m', 'strategy': r['strategy'],
                'wr': r['wr'], 'n': r['n'], 'p': 0.01, 'verdict': 'WATCH',
                'score': r['wr'] / 10, 'model': 'current', 'trade': False}
out = {'updated_at': datetime.now().isoformat(), 'source': 'merge', 'pairs': pairs}
json.dump(out, open(ACTIVE, 'w'), indent=2, ensure_ascii=False)
save_history('active_history', out)
print(f'Active: {len(pairs)} стратегий, {sum(1 for v in pairs.values() if v["trade"])} trade')
