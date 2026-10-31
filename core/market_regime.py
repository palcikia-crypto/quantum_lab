#!/usr/bin/env python3
"""market_regime.py — определение режима рынка по парам. Сводка в data/regime.json."""
import os, json, sys
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
import oracle

def main():
    oracle.init_db()
    regimes = oracle.get_all_regimes()
    by_regime = {}
    for r in regimes:
        by_regime.setdefault(r['regime'], []).append(r['symbol'])
    out = {'timestamp': datetime.now().isoformat(), 'regimes': regimes, 'summary': by_regime}
    with open(os.path.join(BASE, 'data/regime.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
