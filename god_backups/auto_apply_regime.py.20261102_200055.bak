#!/usr/bin/env python3
"""auto_apply_regime.py — внедрение стратегий по режимам в v3 (с защитой 444)."""
import os, json, shutil, time, stat
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
REGIME = os.path.join(BASE, 'data/holy_grail_regime.json')
V3 = os.path.join(BASE, 'data/okx_tpsl_v3.json')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/auto_apply_regime.log'), 'a') as f:
        f.write(line + '\n')

def backup(path):
    if os.path.exists(path):
        shutil.copy(path, f'{path}.bak.{int(time.time())}')

def main():
    log('=== AUTO APPLY REGIME ===')
    if not os.path.exists(REGIME):
        log('❌ holy_grail_regime.json нет')
        return

    try:
        data = json.load(open(REGIME))
        pairs = data.get('pairs', {})
    except Exception as e:
        log(f'❌ {e}')
        return

    if not pairs:
        log('ℹ️ нет данных')
        return

    log(f'Пар: {len(pairs)}')

    # Проверяем защиту v3 (444)
    try:
        st = os.stat(V3)
        if st.st_mode & stat.S_IWUSR == 0:
            log('⏸️ v3 = 444 (защита) — снимаем для записи')
            os.chmod(V3, 0o644)
            need_restore = True
        else:
            need_restore = False
    except Exception as e:
        log(f'⚠️ stat v3: {e}')
        need_restore = False

    try:
        cur = json.load(open(V3))
        backup(V3)
        count = 0
        for sym, regs in pairs.items():
            if sym not in cur.get('per_pair', {}):
                continue
            for regime, cfg in regs.items():
                if regime == 'flat':
                    if 'flat' in cur['per_pair'][sym]:
                        cur['per_pair'][sym]['flat']['strategy'] = cfg['strategy']
                        count += 1
                elif regime == 'trend':
                    # trend → trend_up + trend_down
                    for r in ['trend_up', 'trend_down']:
                        if r in cur['per_pair'][sym]:
                            cur['per_pair'][sym][r]['strategy'] = cfg['strategy']
                            count += 1
        cur['source'] = 'auto_apply_regime'
        cur['updated_at'] = datetime.now().isoformat()
        json.dump(cur, open(V3, 'w'), indent=2, ensure_ascii=False)
        log(f'✅ v3 обновлён (по режимам): {count} настроек')
    except Exception as e:
        log(f'⚠️ v3: {e}')
    finally:
        if need_restore:
            os.chmod(V3, 0o444)
            log('✅ v3: 444 восстановлен')

    log('=== DONE ===')

if __name__ == '__main__':
    main()
