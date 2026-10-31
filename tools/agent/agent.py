#!/usr/bin/env python3
"""Обучаемый агент для quantum_lab. Без API, без LLM. Работает на armv7l."""
import os, sys, json, sqlite3, subprocess, time, hashlib
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
AGENT_DIR = os.path.join(BASE, 'tools/agent')
RULES = os.path.join(AGENT_DIR, 'rules.json')
MEMORY = os.path.join(AGENT_DIR, 'memory.json')
INCIDENTS = os.path.join(AGENT_DIR, 'incidents.log')
LOG = os.path.join(BASE, 'logs/agent.log')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def load_json(path, default):
    if os.path.exists(path):
        try: return json.load(open(path))
        except: pass
    return default

def save_json(path, data):
    json.dump(data, open(path, 'w'), indent=2, ensure_ascii=False)

def collect_facts():
    """Собирает всё состояние системы."""
    facts = {'ts': int(time.time())}
    # процессы
    for name in ['okx_bot_paper_v4', 'brain_loop', 'oracle.py', 'orderbook_oracle', 'evolve_agent']:
        r = subprocess.run(['pgrep', '-f', name], capture_output=True, text=True)
        facts[f'proc_{name}'] = bool(r.stdout.strip())
    # свежесть
    for db, table in [('oracle.db', 'regime'), ('market.db', 'candles'), ('orderbook.db', 'orderbooks')]:
        try:
            c = sqlite3.connect(os.path.join(BASE, 'data', db))
            age = c.execute(f"SELECT (strftime('%s','now') - MAX(ts)) FROM {table}").fetchone()[0]
            c.close()
            facts[f'age_{db}'] = age
        except: facts[f'age_{db}'] = None
    # PnL
    try:
        c = sqlite3.connect(os.path.join(BASE, 'data/okx_paper_v4.db'))
        facts['pnl_total'] = c.execute("SELECT ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        facts['pnl_24h'] = c.execute("SELECT ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED' AND closed_at > strftime('%s','now')-86400").fetchone()[0] or 0
        # свежие ERROR за последние 5 минут
        import re
        from datetime import datetime, timedelta
        log_path = os.path.join(BASE, 'logs/okx_bot_paper_v4.log')
        recent_errors = 0
        cutoff = datetime.now() - timedelta(minutes=5)
        if os.path.exists(log_path):
            for line in open(log_path):
                if 'ERROR' in line and line.startswith('['):
                    try:
                        t = datetime.strptime(line[1:9], '%H:%M:%S')
                        t = t.replace(year=cutoff.year, month=cutoff.month, day=cutoff.day)
                        if t > cutoff: recent_errors += 1
                    except: pass
        facts['v4_errors_recent'] = recent_errors
        facts['v4_error'] = recent_errors
        c.close()
    except: pass
    # ML
    ml_path = os.path.join(BASE, 'data/ml_predictions_online.json')
    if os.path.exists(ml_path):
        try:
            d = json.load(open(ml_path))
            facts['ml_bad'] = [s for s, v in d.get('predictions', {}).items() if v['proba_long'] < 0.05 or v['proba_long'] > 0.95]
        except: facts['ml_bad'] = []
    return facts

def apply_rules(facts, rules):
    """Применяет правила, возвращает список действий."""
    actions = []
    for rule in rules:
        cond = rule.get('condition', {})
        ok = True
        for k, v in cond.items():
            if k.endswith('_lt') and not (facts.get(k[:-3]) is not None and facts.get(k[:-3]) < v): ok = False
            elif k.endswith('_gt') and not (facts.get(k[:-3]) is not None and facts.get(k[:-3]) > v): ok = False
            elif k.endswith('_false') and facts.get(k[:-6]) is not False: ok = False
            elif k.endswith('_true') and facts.get(k[:-5]) is not True: ok = False
            elif not k.endswith(('_lt','_gt','_false','_true')) and facts.get(k) != v: ok = False
        if ok:
            actions.append(rule)
    return actions

def execute_action(action, facts, memory):
    """Выполняет действие из правила."""
    a = action.get('action')
    if a == 'restart':
        proc = action['target']
        subprocess.run(['pkill', '-9', '-f', proc], capture_output=True)
        time.sleep(2)
        cmd = action.get('cmd', f'python3 -u core/{proc}.py')
        subprocess.Popen(cmd.split(), cwd=BASE, stdout=open(os.path.join(BASE, f'logs/{proc}.log'), 'a'), stderr=subprocess.STDOUT)
        log(f'🔧 restart {proc}')
        return True
    elif a == 'retrain_ml':
        subprocess.Popen(['python3', 'core/ml_online_simple.py'], cwd=BASE, stdout=open(os.path.join(BASE, 'logs/ml_online.log'), 'a'), stderr=subprocess.STDOUT)
        log('🔧 retrain ML')
        return True
    elif a == 'alert':
        msg = action.get('message', '').format(**facts)
        log(f'🚨 ALERT: {msg}')
        with open(os.path.join(BASE, 'logs/agent_alerts.log'), 'a') as f:
            f.write(f'[{datetime.now()}] {msg}\n')
        return True
    elif a == 'log':
        log(f'📝 {action.get("message", "").format(**facts)}')
        return True
    return False

def main():
    log('=== AGENT RUN ===')
    facts = collect_facts()
    rules = load_json(RULES, [])
    memory = load_json(MEMORY, {'runs': 0, 'actions': [], 'patterns': {}})
    memory['runs'] += 1

    fired = apply_rules(facts, rules)
    for r in fired:
        execute_action(r, facts, memory)
        memory['actions'].append({'ts': facts['ts'], 'rule': r.get('name', '?')})

    # самообучение: копим паттерны
    for k, v in facts.items():
        if k.startswith('age_') and v is not None and v > 300:
            memory['patterns'][k] = memory['patterns'].get(k, 0) + 1

    save_json(MEMORY, memory)
    log(f'✅ run #{memory["runs"]}, правил сработало: {len(fired)}')

if __name__ == '__main__':
    main()
