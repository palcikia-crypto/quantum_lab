#!/usr/bin/env python3
"""autopilot.py — полная автономия: данные, процессы, сигналы, PnL."""
import os, sys, json, sqlite3, subprocess, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/autopilot.log')
MARKET = os.path.join(BASE, 'data/market.db')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] [auto] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def q(db, sql, params=()):
    try:
        c = sqlite3.connect(db, timeout=5)
        r = c.execute(sql, params).fetchone()
        c.close()
        return r
    except: return None

# === 1. ДАННЫЕ ===
def check_data():
    """Свежесть 15m, 1h, 4h."""
    issues = []
    for tf in ['15m', '1h', '4h']:
        r = q(MARKET, "SELECT (strftime('%s','now') - MAX(ts)) FROM candles WHERE tf=?", (tf,))
        age = r[0] if r else None
        if age is None or age > 1800:  # 30 мин
            issues.append((tf, age))
            log(f'⚠️ {tf}: {age} сек (stale)')
    return issues

def fix_data(issues):
    """Докачивает stale TF."""
    if not issues: return
    log(f'🔧 докачиваем: {[i[0] for i in issues]}')
    try:
        sys.path.insert(0, os.path.join(BASE, 'core'))
        from data_manager import update_all
        # Обновляем все TF
        for tf, _ in issues:
            update_all(only_tf=tf)
    except Exception as e:
        log(f'❌ data fix: {e}')

# === 2. ПРОЦЕССЫ ===
PROCS = {
    'okx_bot_paper_v2': 'core/okx_bot_paper_v2.py',
    'okx_bot_paper_v3': 'core/okx_bot_paper_v3.py',
    'okx_bot_paper_v4': 'core/okx_bot_paper_v4.py',
    'brain_loop': 'core/brain_loop.py',
    'oracle.py': 'core/oracle.py',
    'orderbook_oracle': 'core/orderbook_oracle.py',
    'strategy_bot': 'core/strategy_bot.py',
    'evolve_agent': 'agents/evolve_agent.py',
}

def check_procs():
    """Проверяет, живы ли процессы."""
    dead = []
    for name, path in PROCS.items():
        r = subprocess.run(['pgrep', '-f', name], capture_output=True)
        if not r.stdout.strip():
            dead.append((name, path))
            log(f'❌ {name} — не работает')
    return dead

def fix_procs(dead):
    """Перезапускает упавшие."""
    for name, path in dead:
        log(f'🔧 перезапуск {name}')
        try:
            logfile = os.path.join(BASE, f'logs/{name.replace(".", "_")}.log')
            subprocess.Popen(['python3', '-u', path], cwd=BASE,
                            stdout=open(logfile, 'a'), stderr=subprocess.STDOUT,
                            start_new_session=True)
        except Exception as e:
            log(f'❌ {name}: {e}')

# === 3. СИГНАЛЫ (v2/v3) ===
def check_signals():
    """Есть ли сделки за последний час?"""
    for name, db in [('v2', 'data/okx_paper.db'), ('v3', 'data/okx_paper_v3.db')]:
        r = q(os.path.join(BASE, db), """
            SELECT COUNT(*) FROM trades
            WHERE status='CLOSED' AND closed_at > strftime('%s','now')-3600
        """)
        cnt = r[0] if r else 0
        if cnt == 0:
            log(f'⚠️ {name}: 0 сделок за час')
    return True

# === 4. PnL ===
def check_pnl():
    """Проверяет PnL за 24ч."""
    for name, db in [('v2', 'data/okx_paper.db'), ('v3', 'data/okx_paper_v3.db'), ('v4', 'data/okx_paper_v4.db')]:
        r = q(os.path.join(BASE, db), """
            SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2) FROM trades
            WHERE status='CLOSED' AND closed_at > strftime('%s','now')-86400
        """)
        if r:
            n, pnl = r
            if pnl < -10:
                log(f'🚨 {name}: PnL {pnl} (24ч) < -10')
            elif n > 0:
                log(f'📊 {name}: {n} сделок, PnL={pnl}')

# === 5. ВЕБ ===
def check_web():
    """Проверяет веб-панели."""
    for name, port in [('dashboard.py', 5000), ('strategy_panel.py', 5001)]:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'http://127.0.0.1:{port}'], capture_output=True, text=True)
        if r.stdout.strip() != '200':
            log(f'⚠️ {name} (порт {port}) — HTTP {r.stdout.strip()}')

def main():
    log('=== AUTOPILOT RUN ===')
    # 1. Данные
    data_issues = check_data()
    if data_issues:
        fix_data(data_issues)
    # 2. Процессы
    dead = check_procs()
    if dead:
        fix_procs(dead)
    # 3. Сигналы
    check_signals()
    # 4. PnL
    check_pnl()
    # 5. Веб
    check_web()
    log('=== DONE ===')

if __name__ == '__main__':
    main()
