import json, os
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
gate = json.load(open(os.path.join(BASE, 'data/gate_v2.json')))
pairs = {}
for r in gate.get('results', []):
    if r['verdict'] not in ('GOLDEN', 'TRADE_NOW', 'WATCH'): continue
    key = r['symbol'] + '_' + r['tf']
    if key not in pairs or r['score'] > pairs[key]['score']:
        pairs[key] = {
            'symbol': r['symbol'], 'tf': r['tf'], 'strategy': r['strategy'],
            'wr': r['L1']['wr'], 'n': r['L1']['n'], 'p': r['L1']['p'],
            'verdict': r['verdict'], 'score': r['score'], 'model': r['model'],
            'trade': r['verdict'] in ('GOLDEN', 'TRADE_NOW'),
        }
out = {'updated_at': datetime.now().isoformat(), 'source': 'gate_v2',
       'note': 'WATCH = наблюдать, не торговать', 'pairs': pairs}
with open(os.path.join(BASE, 'data/active_strategies.json'), 'w') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print('Создано: ' + str(len(pairs)) + ' стратегий')
for k, v in pairs.items():
    print('  ' + k.ljust(20) + ' ' + v['strategy'].ljust(15) + ' ' + v['verdict'].ljust(10) +
          ' trade=' + str(v['trade']) + ' WR=' + str(v['wr']) + '%')
