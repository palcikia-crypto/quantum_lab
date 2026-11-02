import os, json, sqlite3, shutil, time, stat, subprocess
from datetime import datetime

from datetime import datetime

LOG = 'logfile.txt'  # Убедитесь, что вы указали правильный путь к файлу логов

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

import os
import shutil
import time

def backup(path):
    if os.path.exists(path):
        shutil.copy(path, f'{path}.bak.{int(time.time())}')
    else:
        print(f"File {path} does not exist.")

def get_regimes():
    """Текущие режимы из oracle."""
    try:
        c = sqlite3.connect(ORACLE_DB, timeout=5)
        rows = c.execute("""SELECT symbol, regime, adx FROM regime
                            WHERE ts=(SELECT MAX(ts) FROM regime)""").fetchall()
        c.close()
        return {r[0]: {'regime': r[1], 'adx': r[2]} for r in rows}
    except:
        return {}

import sqlite3

def get_wr(db, last_n=10):
    """WR за последние N сделок."""
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("""SELECT pnl FROM trades WHERE status='CLOSED'
                            ORDER BY exit_ts DESC LIMIT ?""", (last_n,)).fetchall()
        c.close()
        if not rows: 
            return None, 0
        wins = sum(1 for r in rows if r[0] is not None and r[0] > 0)
        return 100.0 * wins / len(rows), len(rows)
    except Exception as e:
        print(f"Error: {e}")  # Для отладки, можно убрать в продакшене.
        return None, 0

import json
import os
import stat

V3_CFG = 'path_to_v3_config.json'  # Укажите путь к конфигурационному файлу V3

def log(message):
    print(message)  # Замените на свою реализацию логирования

def backup(file_path):
    # Реализуйте функцию резервного копирования файла
    pass

def adapt_v3(regimes, grail_regime):
    """Адаптирует v3 под текущий режим."""
    if not grail_regime or 'pairs' not in grail_regime:
        return

    try:
        with open(V3_CFG, 'r', encoding='utf-8') as f:
            cur = json.load(f)

        st = os.stat(V3_CFG)
        need_restore = False

        if st.st_mode & stat.S_IWUSR == 0:
            os.chmod(V3_CFG, 0o644)
            need_restore = True

        changed = 0

        for pair, cfg in cur.get('per_pair', {}).items():
            sym = pair.replace('-', '')
            if sym not in regimes:
                continue

            current_regime = regimes[sym]['regime']
            key = 'flat' if current_regime == 'flat' else 'trend'

            if pair in grail_regime['pairs'] and key in grail_regime['pairs'][pair]:
                new_strat = grail_regime['pairs'][pair][key]['strategy']
                for reg in ['flat', 'trend_up', 'trend_down']:
                    if cfg.get(reg, {}).get('strategy') != new_strat:
                        cfg[reg]['strategy'] = new_strat
                        changed += 1

        if changed > 0:
            backup(V3_CFG)
            with open(V3_CFG, 'w', encoding='utf-8') as f:
                json.dump(cur, f, indent=2, ensure_ascii=False)
            log(f'✅ v3: обновлено {changed} стратегий (по режимам)')

        if need_restore:
            os.chmod(V3_CFG, 0o444)
    except Exception as e:
        log(f'⚠️ v3: {e}')

def main():
    log('=== AUTO ADAPT REALTIME ===')

    regimes = get_regimes()
    if not regimes:
        log('⚠️ нет данных из oracle')
        return

    # Загружаем граали по режимам
    grail_regime = None
    if os.path.exists(REGIME):
        try:
            grail_regime = json.load(open(REGIME))
        except: pass

    # Проверяем WR v3
    wr_v3, n_v3 = get_wr(DB_V3, 10)
    log(f'v3: WR={wr_v3:.1f}% ({n_v3} сделок)' if wr_v3 else 'v3: нет данных')
    wr_v4, n_v4 = get_wr(DB_V4, 10)
    log(f'v4: WR={wr_v4:.1f}% ({n_v4} сделок)' if wr_v4 else 'v4: нет данных')

    # Если WR < 40% — запускаем auto_evolve_by_regime немедленно
    if wr_v3 is not None and wr_v3 < 40 and n_v3 >= 10:
        log('❌ v3 WR < 40% → запускаем auto_evolve_by_regime')
        try:
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_evolve_by_regime.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_evolve_by_regime.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
        except Exception as e:
            log(f'⚠️ запуск: {e}')
        # Через 60 сек — проверить holy_grail_regime и применить
        time.sleep(60)
        if os.path.exists(REGIME):
            try:
                d = json.load(open(REGIME))
                if d.get('pairs') and len(d['pairs']) > 0:
                    log(f'✅ holy_grail_regime: {len(d["pairs"])} пар → auto_apply_regime')
                    subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_apply_regime.py')],
                                    stdout=open(os.path.join(BASE,'logs/auto_apply_regime.log'),'a'),
                                    stderr=subprocess.STDOUT, start_new_session=True)
            except Exception as e:
                log(f'⚠️ apply: {e}')

    # АВАРИЙНЫЙ СТОП: если WR < 20% — остановить
    if wr_v3 is not None and wr_v3 < 20 and n_v3 >= 10:
        log('🚨 v3 WR < 20% → останавливаем')
        try:
            subprocess.run(['pkill','-9','-f','okx_bot_paper_v3'], capture_output=True)
        except: pass
    if wr_v4 is not None and wr_v4 < 20 and n_v4 >= 10:
        log('🚨 v4 WR < 20% → останавливаем')
        try:
            subprocess.run(['pkill','-9','-f','okx_bot_paper_v4'], capture_output=True)
        except: pass

    # Адаптируем v3 под режимы (если есть граали)
    if grail_regime:
        adapt_v3(regimes, grail_regime)

    log('=== DONE ===')