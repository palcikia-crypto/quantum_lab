#!/usr/bin/env python3
"""auto_apply_graals.py — автоподключение граалей в by_regime/v3/v4."""
import os, json, shutil, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
HOLY = os.path.join(BASE, 'data/holy_grail.json')
BY_REGIME = os.path.join(BASE, 'data/okx_tpsl_by_regime.json')
V3 = os.path.join(BASE, 'data/okx_tpsl_v3.json')
LOG = os.path.join(BASE, 'logs/auto_apply_graals.log')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def backup(path):
    if os.path.exists(path):
        shutil.copy(path, f'{path}.bak.{int(time.time())}')
        return True
    return False

def main():
    log('=== AUTO APPLY GRAALS ===')
    if not os.path.exists(HOLY):
        log('❌ holy_grail.json нет')
        return

    try:
        holy = json.load(open(HOLY))
        stable = holy.get('stable', [])
    except Exception as e:
        log(f'❌ holy_grail error: {e}')
        return

    if not stable:
        log('ℹ️ нет граалей')
        return

    log(f'Граалей: {len(stable)}')

    by_pair = {}
    for s in stable:
        sym = s['sym'].replace('USDT', '-USDT')
        if sym not in by_pair:
            by_pair[sym] = s

    if os.path.exists(BY_REGIME):
        try:
            cur = json.load(open(BY_REGIME))
            if cur.get('source') == 'manual_optimize':
                log('⏸️ by_regime = manual_optimize — не трогаем')
            else:
                backup(BY_REGIME)
                for sym, s in by_pair.items():
                    cur['per_pair'][sym] = {
                        reg: {'strategy': s['strat'], 'tp': 0.006, 'sl': 0.004, 'timeout_bars': 2}
                        for reg in ['flat', 'trend_up', 'trend_down']
                    }
                cur['source'] = 'auto_apply_graals'
                cur['updated_at'] = datetime.now().isoformat()
                json.dump(cur, open(BY_REGIME, 'w'), indent=2, ensure_ascii=False)
                log(f'✅ by_regime обновлён: {len(by_pair)} пар')
        except Exception as e:
            log(f'⚠️ by_regime: {e}')

    if os.path.exists(V3):
        try:
            cur = json.load(open(V3))
            backup(V3)
            for sym, s in by_pair.items():
                cur['per_pair'][sym] = {
                    reg: {'strategy': s['strat'], 'tp': 0.006, 'sl': 0.004, 'timeout_bars': 2}
                    for reg in ['flat', 'trend_up', 'trend_down']
                }
            cur['source'] = 'auto_apply_graals'
            cur['updated_at'] = datetime.now().isoformat()
            json.dump(cur, open(V3, 'w'), indent=2, ensure_ascii=False)
            log(f'✅ v3 обновлён: {len(by_pair)} пар')
        except Exception as e:
            log(f'⚠️ v3: {e}')

    log('=== AUTO APPLY GRAALS DONE ===')

if __name__ == '__main__':
    main()
