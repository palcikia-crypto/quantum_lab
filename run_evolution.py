#!/usr/bin/env python3
"""run_evolution.py — эволюция стратегий (L1 grid -> L2 features -> L3 mutations)."""
import sys, os, json
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
from full_access import load_all_strategies, load_evolution
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
strategies = load_all_strategies()
print(f'Стратегий: {len(strategies)}')
evo = load_evolution()
if evo:
    print('evolution_old загружен')
    # Пробуем вызвать L1_grid (если есть)
    if hasattr(evo, 'L1_grid'):
        print('L1_grid есть')
    if hasattr(evo, 'L2_features'):
        print('L2_features есть')
    if hasattr(evo, 'L3_mutations'):
        print('L3_mutations есть')
else:
    print('evolution_old НЕ загружен')
# Сохраняем отчёт
out = {'timestamp': datetime.now().isoformat(), 'strategies': list(strategies.keys()),
       'evolution_loaded': evo is not None}
json.dump(out, open(os.path.join(BASE, 'data/evolution_report.json'), 'w'), indent=2, ensure_ascii=False)
print(f'Сохранено: evolution_report.json')
