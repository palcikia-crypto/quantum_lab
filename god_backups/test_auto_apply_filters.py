#!/usr/bin/env python3
"""auto_apply_filters.py — внедрение фильтров в v3/v4."""
import os, json, shutil, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
SETTINGS = os.path.join(BASE, 'data/filter_settings.json')
V3 = os.path.join(BASE, 'data/okx_tpsl_v3.json')
V4 = os.path.join(BASE, 'data/okx_tpsl_v4.json')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/auto_apply_filters.log', encoding='utf-8'), 'a') as f:
        f.write(line + '\n')

def backup(path):
    if os.path.exists(path):
        shutil.copy(path, f'{path}.bak.{int(time.time())}')

def main():
    log('=== AUTO APPLY FILTERS ===')
    if not os.path.exists(SETTINGS):
        log('❌ filter_settings.json нет')
        return

    try:
        data = json.load(open(SETTINGS, encoding='utf-8'))
        settings = data.get('settings', [])
    except Exception as e:
        log(f'❌ {e}')
        return

    if not settings:
        log('ℹ️ нет настроек')
        return

    log(f'Настроек: {len(settings)}')

    # Обновляем v3
    if os.path.exists(V3):
        try:
            cur = json.load(open(V3, encoding='utf-8'))
            backup(V3)
            count = 0
            for s in settings:
                sym = s['symbol']
                strat = s['strategy']
                if sym not in cur.get('per_pair', {}):
                    continue
                cur_strat = cur['per_pair'][sym].get('flat', {}).get('strategy', '')
                if cur_strat != strat:
                    continue
                for reg in ['flat', 'trend_up', 'trend_down']:
                    cur['per_pair'][sym][reg]['obi_threshold'] = s['obi']
                    cur['per_pair'][sym][reg]['funding_min'] = s['funding']
                    cur['per_pair'][sym][reg]['pressure_max'] = s['pressure']
                    cur['per_pair'][sym][reg]['spread_max'] = s['spread']
                count += 1
            cur['source'] = 'auto_apply_filters'
            cur['updated_at'] = datetime.now().isoformat()
            json.dump(cur, open(V3, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            log(f'✅ v3 обновлён (фильтры): {count} пар')
        except Exception as e:
            log(f'⚠️ v3: {e}')

    # Обновляем v4 (только scalp_obi_short)
    if os.path.exists(V4):
        try:
            cur = json.load(open(V4, encoding='utf-8'))
            backup(V4)
            count = 0
            for s in settings:
                if 'obi_short' not in s['strategy']:
                    continue
                sym = s['symbol']
                if sym not in cur.get('per_pair', {}):
                    continue
                cur['per_pair'][sym]['obi_threshold'] = s['obi']
                cur['per_pair'][sym]['funding_min'] = s['funding']
                cur['per_pair'][sym]['pressure_max'] = s['pressure']
                cur['per_pair'][sym]['spread_max'] = s['spread']
                count += 1
            cur['source'] = 'auto_apply_filters'
            cur['updated_at'] = datetime.now().isoformat()
            json.dump(cur, open(V4, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            log(f'✅ v4 обновлён (фильтры): {count} пар')
        except Exception as e:
            log(f'⚠️ v4: {e}')

    log('=== DONE ===')

if __name__ == '__main__':
    main()
