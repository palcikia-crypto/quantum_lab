import json, os
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
EVO = os.path.join(BASE, 'data/evolution.json')
ACTIVE = os.path.join(BASE, 'data/active_strategies.json')
GATE = os.path.join(BASE, 'data/gate_all.json')

evo = json.load(open(EVO))
gate = json.load(open(GATE)) if os.path.exists(GATE) else {'results': []}
gate_by_key = {r['symbol'] + '_' + r['tf']: r for r in gate.get('results', [])}

pairs = {}
# 1. Добавляем ВСЕ эволюционные (по 15m, если нет в gate — всё равно добавляем)
for r in evo.get('top', []):
    sym = r['symbol']; strat = r['strategy']; wr = r['wr']; n = r['n']
    # Ищем в gate (любой ТФ)
    found = False
    for key, g in gate_by_key.items():
        if g['symbol'] == sym and g['strategy'] == strat:
            pairs[key] = {
                'symbol': sym, 'tf': g['tf'], 'strategy': strat,
                'wr': wr, 'n': n, 'p': g['L1'].get('p', 1),
                'verdict': g['verdict'], 'score': g.get('score', 0),
                'model': g.get('model', 'current'),
                'trade': g['verdict'] in ('GOLDEN', 'TRADE_NOW'),
            }
            found = True
            break
    if not found:
        # Нет в gate — добавляем как 15m WATCH
        key = sym + '_15m'
        pairs[key] = {
            'symbol': sym, 'tf': '15m', 'strategy': strat,
            'wr': wr, 'n': n, 'p': 0.01,
            'verdict': 'WATCH', 'score': wr / 10,
            'model': 'current', 'trade': False,
        }

# 2. Добавляем gate GOLDEN (если не в evolution)
for key, g in gate_by_key.items():
    if g['verdict'] == 'GOLDEN' and key not in pairs:
        pairs[key] = {
            'symbol': g['symbol'], 'tf': g['tf'], 'strategy': g['strategy'],
            'wr': g['L1']['wr'], 'n': g['L1']['n'], 'p': g['L1'].get('p', 1),
            'verdict': g['verdict'], 'score': g.get('score', 0),
            'model': g.get('model', 'current'), 'trade': True,
        }

# 3. Добавляем gate GOLDEN stoch_20 (XRP, BTC) как trade=True
for key in list(pairs.keys()):
    if pairs[key]['verdict'] == 'GOLDEN':
        pairs[key]['trade'] = True

out = {'updated_at': datetime.now().isoformat(), 'source': 'evolution+gate', 'pairs': pairs}
json.dump(out, open(ACTIVE, 'w'), indent=2, ensure_ascii=False)
trades = sum(1 for v in pairs.values() if v['trade'])
print(f'Active обновлён: {len(pairs)} стратегий, {trades} для торговли')
for k, v in pairs.items():
    print(f"  {k:20} {v['strategy']:15} {v['verdict']:10} trade={v['trade']} WR={v['wr']}%")
