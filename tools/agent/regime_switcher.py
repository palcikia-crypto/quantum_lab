#!/usr/bin/env python3
"""regime_switcher.py — переключает стратегии при смене режима."""
import os, json, sqlite3, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/regime_switcher.log')
ORACLE = os.path.join(BASE, 'data/oracle.db')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
REGIME_FILE = os.path.join(BASE, 'data/okx_active_regime.json')
# Белый список: только стратегии, прошедшие 4/4 в stability_check_2
WHITELIST = {'okx_vwap_rev_7', 'okx_vwap_rev_13', 'okx_vwap_rev_15', 'okx_grid_sma_13', 'okx_grid_sma_15'}

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_regime(sym):
    if not os.path.exists(ORACLE): return None
    c = sqlite3.connect(ORACLE, timeout=5)
    r = c.execute("SELECT regime, adx FROM regime WHERE symbol=? ORDER BY ts DESC LIMIT 1", (sym,)).fetchone()
    c.close()
    return {'regime': r[0], 'adx': r[1]} if r else None

def main():
    log('=== REGIME SWITCHER ===')
    if not os.path.exists(REGIME_FILE):
        log('нет okx_active_regime.json — пропуск'); return
    reg_data = json.load(open(REGIME_FILE))
    per_pair = reg_data.get('per_pair', {})
    if not os.path.exists(ACTIVE): return
    active = json.load(open(ACTIVE))
    pairs = active.get('pairs', {})
    switched = 0
    for key, v in pairs.items():
        sym_key = v['symbol']  # BTC-USDT
        r = get_regime(sym_key.replace('-', ''))
        if not r: continue
        reg = r['regime']
        lst = per_pair.get(sym_key, {}).get(reg, [])
        if not lst: continue
        best = lst[0]
        new_strat = best.get('strategy')
        if new_strat and new_strat != v['strategy'] and new_strat in WHITELIST:
            log(f'  🔄 {sym_key}: {v["strategy"]} → {new_strat} (regime={reg})')
            v['strategy'] = new_strat
            v['regime_at_switch'] = reg
            v['switched_at'] = datetime.now().isoformat()
            switched += 1
    if switched:
        active['regime_switched_at'] = datetime.now().isoformat()
        json.dump(active, open(ACTIVE, 'w'), indent=2)
        log(f'  ✅ переключено {switched} пар по режиму')
    else:
        log('  ✅ режим не изменился')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
