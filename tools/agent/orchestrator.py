#!/usr/bin/env python3
"""orchestrator.py — ЕДИНАЯ экосистема: данные → оптимизатор → конфиг → боты."""
import os, sys, json, sqlite3, subprocess, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/orchestrator.log')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
ACTIVE_V3 = os.path.join(BASE, 'data/okx_active_v3.json')
ACTIVE_REGIME = os.path.join(BASE, 'data/okx_active_regime.json')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] [orch] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def sync_configs():
    """ЕДИНЫЙ источник: okx_active.json → копии."""
    if not os.path.exists(ACTIVE): return
    d = json.load(open(ACTIVE))
    pairs = d.get('pairs', {})
    if not pairs: return
    # Копия для v3
    json.dump(d, open(ACTIVE_V3, 'w'), indent=2)
    # Копия для regime_switcher
    per_pair = {}
    for k, v in pairs.items():
        sym = v['symbol']
        strat = v['strategy']
        per_pair[sym] = {
            'flat': [{'strategy': strat, 'tp': v.get('tp',0.008), 'sl': v.get('sl',0.005), 'timeout_bars': v.get('timeout',3)}],
            'trend_up': [{'strategy': strat, 'tp': v.get('tp',0.008), 'sl': v.get('sl',0.005), 'timeout_bars': v.get('timeout',3)}],
            'trend_down': [{'strategy': strat, 'tp': v.get('tp',0.008), 'sl': v.get('sl',0.005), 'timeout_bars': v.get('timeout',3)}]
        }
    json.dump({'per_pair': per_pair}, open(ACTIVE_REGIME, 'w'), indent=2)
    log(f'✅ синхронизировано: {len(pairs)} пар → okx_active_v3.json + okx_active_regime.json')

def check_data():
    """Данные свежие?"""
    c = sqlite3.connect(os.path.join(BASE, 'data/market.db'))
    age = c.execute("SELECT (strftime('%s','now') - MAX(ts)) FROM candles WHERE tf='15m'").fetchone()[0]
    c.close()
    if age and age > 1800:
        log(f'⚠️ данные stale: {age} сек — докачиваю')
        subprocess.run(['python3', 'core/data_manager.py'], cwd=BASE, timeout=60)
    return age

def check_processes():
    """Все процессы живы?"""
    procs = ['okx_bot_paper_v2', 'okx_bot_paper_v3', 'okx_bot_paper_v4',
             'oracle.py', 'orderbook_oracle', 'brain_loop', 'strategy_bot']
    dead = []
    for p in procs:
        r = subprocess.run(['pgrep', '-f', p], capture_output=True)
        if not r.stdout.strip():
            dead.append(p)
    return dead

def restart_bots():
    """Перезапустить ботов (чтобы прочитали новый конфиг)."""
    for v in [2, 3]:
        subprocess.run(['pkill', '-9', '-f', f'okx_bot_paper_v{v}'], capture_output=True)
        time.sleep(1)
        logfile = f'logs/okx_bot_paper{"" if v==2 else "_v"+str(v)}.log'
        subprocess.Popen(['python3', '-u', f'core/okx_bot_paper_v{v}.py'],
                         cwd=BASE, stdout=open(os.path.join(BASE, logfile), 'w'),
                         stderr=subprocess.STDOUT, start_new_session=True)
    log('✅ боты перезапущены')

def main():
    log('=== ORCHESTRATOR RUN ===')
    # 1. Данные
    age = check_data()
    # 2. Синхронизация конфигов
    sync_configs()
    # 3. Процессы
    dead = check_processes()
    if dead:
        log(f'⚠️ упали: {dead} — перезапуск')
        for p in dead:
            subprocess.Popen(['python3', '-u', f'core/{p}.py' if '.py' not in p else f'core/{p}'],
                             cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    # 4. Sanity check
    r = subprocess.run(['python3', 'tools/agent/sanity_check.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode != 0:
        log(f'⚠️ sanity_check: ошибки')
    # 5. PnL
    for db in ['okx_paper.db:v2', 'okx_paper_v3.db:v3', 'okx_paper_v4.db:v4']:
        f, n = db.split(':')
        c = sqlite3.connect(os.path.join(BASE, 'data', f))
        row = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED'").fetchone()
        c.close()
        log(f'  📊 {n}: {row[0]} сделок, PnL={row[1]}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
