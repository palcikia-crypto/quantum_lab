#!/usr/bin/env python3
"""Агент v2: с памятью и обучением на опыте."""
import os, sys, json, sqlite3, subprocess, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory

BASE = os.path.expanduser('~/quantum_lab')
AGENT_DIR = os.path.join(BASE, 'tools/agent')
RULES = os.path.join(AGENT_DIR, 'rules.json')
LOG = os.path.join(BASE, 'logs/agent.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def collect_facts():
    facts = {'ts': int(time.time())}
    for name in ['okx_bot_paper_v4', 'brain_loop', 'oracle.py', 'orderbook_oracle', 'evolve_agent']:
        r = subprocess.run(['pgrep', '-f', name], capture_output=True, text=True)
        facts[f'proc_{name}'] = bool(r.stdout.strip())
    for db, table in [('oracle.db', 'regime'), ('market.db', 'candles'), ('orderbook.db', 'orderbooks')]:
        try:
            c = sqlite3.connect(os.path.join(BASE, 'data', db))
            age = c.execute(f"SELECT (strftime('%s','now') - MAX(ts)) FROM {table}").fetchone()[0]
            c.close()
            facts[f'age_{db}'] = age
        except: facts[f'age_{db}'] = None
    try:
        c = sqlite3.connect(os.path.join(BASE, 'data/okx_paper_v4.db'))
        facts['pnl_total'] = c.execute("SELECT ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        facts['pnl_24h'] = c.execute("SELECT ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED' AND closed_at > strftime('%s','now')-86400").fetchone()[0] or 0
        c.close()
    except: pass
    return facts

def apply_rules(facts, rules):
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

def execute_action(action, facts):
    a = action.get('action')
    rule = action.get('name', '?')
    success = False
    try:
        if a == 'restart':
            proc = action['target']
            subprocess.run(['pkill', '-9', '-f', proc], capture_output=True)
            time.sleep(2)
            cmd = action.get('cmd', f'python3 -u core/{proc}.py')
            subprocess.Popen(cmd.split(), cwd=BASE, stdout=open(os.path.join(BASE, f'logs/{proc}.log'), 'a'), stderr=subprocess.STDOUT)
            log(f'🔧 restart {proc}')
            success = True
        elif a == 'retrain_ml':
            subprocess.Popen(['python3', 'core/ml_online_simple.py'], cwd=BASE, stdout=open(os.path.join(BASE, 'logs/ml_online.log'), 'a'), stderr=subprocess.STDOUT)
            log('🔧 retrain ML')
            success = True
        elif a == 'alert':
            msg = action.get('message', '').format(**facts)
            log(f'🚨 ALERT: {msg}')
            with open(os.path.join(BASE, 'logs/agent_alerts.log'), 'a') as f:
                f.write(f'[{datetime.now()}] {msg}\n')
            success = True
    except Exception as e:
        log(f'❌ action error: {e}')
    memory.save_action(a, action.get('target', rule), 'ok' if success else 'fail', success)
    memory.update_rule_weight(rule, success)
    return success

def main():
    log('=== AGENT v2 RUN ===')
    memory.init()
    facts = collect_facts()
    for k, v in facts.items():
        memory.save_fact(k, v)
    rules = json.load(open(RULES)) if os.path.exists(RULES) else []
    fired = apply_rules(facts, rules)
    for r in fired:
        execute_action(r, facts)
    stats = memory.stats()
    log(f'✅ run: правил {len(fired)}, память: {stats}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
