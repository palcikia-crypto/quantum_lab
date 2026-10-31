#!/usr/bin/env python3
"""update_active.py — обновляет active_strategies.json из gate_all.json."""
import json, os
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
gate_path = os.path.join(BASE, 'data/gate_all.json')
if not os.path.exists(gate_path):
    print('gate_all.json нет'); sys.exit(1)
gate = json.load(open(gate_path))
pairs = {}
for r in gate.get('results', []):
    if r['verdict'] not in ('GOLDEN','TRADE_NOW','WATCH'): continue

    key = r['symbol'] + '_' + r['tf']
    if key not in pairs or r['score'] > pairs[key]['score']:
        pairs[key] = {
            'symbol': r['symbol'], 'tf': r['tf'], 'strategy': r['strategy'],
            'wr': r['L1']['wr'], 'n': r['L1']['n'], 'p': r['L1']['p'],
            'verdict': r['verdict'], 'score': r['score'], 'model': r['model'],
            'trade': r['verdict'] in ('GOLDEN','TRADE_NOW'),
        }
out = {'updated_at': datetime.now().isoformat(), 'source':'gate_all', 'pairs':pairs}
json.dump(out, open(os.path.join(BASE,'data/active_strategies.json'),'w'), indent=2, ensure_ascii=False)
trades = sum(1 for v in pairs.values() if v['trade'])
print(f'ACTIVE: {len(pairs)} стратегий, {trades} для торговли')
