#!/usr/bin/env python3
"""auto_add.py — автоматически добавляет GOLDEN с WR>60% в active."""
import json, os, sys
from datetime import datetime
sys.path.insert(0, 'core')
from strategy_pool import STRATEGIES
from strategy_combinator import generate_combinations
from strategy_mutator import generate_mutations
from gate import run_gate

BASE = os.path.expanduser('~/quantum_lab')
ACTIVE = os.path.join(BASE, 'data/active_strategies.json')
BLACKLIST = ['bb_15_1.5', 'mean_rev_20_1.5']  # минусовые
MIN_WR = 60.0; MIN_N = 500
PAIRS = ['BTCUSDT','ETHUSDT','XRPUSDT','SOLUSDT','DOGEUSDT']

def run_auto_add():
    print('=== AUTO-ADD START ===')
    combos = generate_combinations(STRATEGIES, max_combos=20)
    muts = generate_mutations(max_mutants=40)
    candidates = {**combos, **muts}
    print(f'Кандидатов: {len(candidates)}')
    added = 0
    d = json.load(open(ACTIVE, encoding='utf-8'))
    for name, fn in candidates.items():
        for pair in PAIRS[:2]:
            try:
                r = run_gate(pair, '15m', name, fn)
                if name in BLACKLIST: continue
                if r and r['verdict']=='GOLDEN' and r['L1']['wr'] >= MIN_WR and r['L1']['n'] >= MIN_N:
                    key = f"{pair}_15m_{name}"
                    if key not in d['pairs']:
                        d['pairs'][key] = {'symbol':pair,'tf':'15m','strategy':name,
                            'wr':r['L1']['wr'],'n':r['L1']['n'],'p':0.0,
                            'verdict':'GOLDEN','score':r['score'],'model':'auto_add','trade':True}
                        added += 1
                        print(f"  ➕ {key}: WR={r['L1']['wr']}% n={r['L1']['n']}")
            except Exception: pass
    if added:
        d['updated_at'] = datetime.now().isoformat()
        json.dump(d, open(ACTIVE,'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'✅ добавлено {added} в active')
    else: print('ℹ️ новых GOLDEN WR>60% не найдено')
    return added

if __name__ == '__main__':
    run_auto_add()
