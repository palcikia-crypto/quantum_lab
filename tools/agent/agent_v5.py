#!/usr/bin/env python3
import os, sys, json, sqlite3, subprocess, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory, analytics, knowledge_use, self_heal
BASE = os.path.expanduser('~/quantum_lab')
AGENT_DIR = os.path.join(BASE, 'tools/agent')
RULES = os.path.join(AGENT_DIR, 'rules.json')
LOG = os.path.join(BASE, 'logs/agent.log')
STATE = os.path.join(AGENT_DIR, 'state.json')
def log(m):
    with open(LOG, 'a') as f: f.write(f'[{datetime.now():%H:%M:%S}] {m}\n')
def load_state():
    if os.path.exists(STATE):
        try: return json.load(open(STATE))
        except: pass
    return {'last_retrain':0, 'last_heal':0}
def save_state(s): json.dump(s, open(STATE, 'w'))
def collect_facts():
    facts = {'ts': int(time.time())}
    for name in ['okx_bot_paper_v4','brain_loop','oracle.py','orderbook_oracle','evolve_agent']:
        r = subprocess.run(['pgrep','-f',name], capture_output=True, text=True)
        facts[f'proc_{name}'] = bool(r.stdout.strip())
    for db, table in [('oracle.db','regime'),('market.db','candles'),('orderbook.db','orderbooks')]:
        try:
            c = sqlite3.connect(os.path.join(BASE,'data',db))
            facts[f'age_{db}'] = c.execute(f"SELECT (strftime('%s','now') - MAX(ts)) FROM {table}").fetchone()[0]
            c.close()
        except: facts[f'age_{db}'] = None
    try:
        c = sqlite3.connect(os.path.join(BASE,'data/okx_paper_v4.db'))
        facts['pnl_total'] = c.execute("SELECT ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        facts['pnl_24h'] = c.execute("SELECT ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED' AND closed_at > strftime('%s','now')-86400").fetchone()[0] or 0
        c.close()
    except: pass
    p = os.path.join(BASE,'data/ml_predictions_online.json')
    if os.path.exists(p):
        try:
            d = json.load(open(p))
            facts['ml_bad'] = [s for s,v in d.get('predictions',{}).items() if v['proba_long']<0.05 or v['proba_long']>0.95]
        except: facts['ml_bad'] = []
    return facts
def apply_rules(facts, rules):
    a = []
    for r in rules:
        ok = True
        for k, v in r.get('condition',{}).items():
            if k.endswith('_lt') and not (facts.get(k[:-3]) is not None and facts.get(k[:-3]) < v): ok = False
            elif k.endswith('_gt') and not (facts.get(k[:-3]) is not None and facts.get(k[:-3]) > v): ok = False
            elif k.endswith('_false') and facts.get(k[:-6]) is not False: ok = False
            elif k.endswith('_true') and facts.get(k[:-5]) is not True: ok = False
            elif not k.endswith(('_lt','_gt','_false','_true')) and facts.get(k) != v: ok = False
        if ok: a.append(r)
    return a
def execute(action, facts, state):
    a = action.get('action'); rule = action.get('name', action.get('reason','?')); ok = False
    try:
        if a == 'restart':
            subprocess.run(['pkill','-9','-f',action['target']], capture_output=True); time.sleep(2)
            subprocess.Popen(action.get('cmd', f'python3 -u core/{action["target"]}.py').split(), cwd=BASE,
                             stdout=open(os.path.join(BASE,f'logs/{action["target"]}.log'),'a'), stderr=subprocess.STDOUT)
            log(f'🔧 restart {action["target"]}'); ok = True
        elif a == 'retrain_ml':
            subprocess.Popen(['python3','core/ml_online_simple.py'], cwd=BASE,
                             stdout=open(os.path.join(BASE,'logs/ml_online.log'),'a'), stderr=subprocess.STDOUT)
            log('🔧 retrain ML'); state['last_retrain'] = int(time.time()); ok = True
        elif a == 'stop_v4':
            subprocess.run(['pkill','-9','-f','okx_bot_paper_v4'], capture_output=True)
            rp = os.path.join(AGENT_DIR,'recovery.json')
            rs = json.load(open(rp)) if os.path.exists(rp) else {}
            rs['stopped_v4_at'] = int(time.time()); json.dump(rs, open(rp,'w'))
            log(f'🛑 STOP v4'); ok = True
        elif a == 'alert':
            msg = action.get('message', action.get('reason',''))
            log(f'🚨 ALERT: {msg}')
            with open(os.path.join(BASE,'logs/agent_alerts.log'),'a') as f:
                f.write(f'[{datetime.now()}] {msg}\n')
            ok = True
        elif a == 'log':
            log(f'📝 {action.get("reason","")}'); ok = True
    except Exception as e:
        log(f'❌ {e}')
    memory.save_action(a, action.get('target', rule), 'ok' if ok else 'fail', ok)
    memory.update_rule_weight(rule, ok)
    return ok
def main():
    log('=== AGENT v5 RUN ===')
    memory.init(); state = load_state(); facts = collect_facts()
    for k,v in facts.items(): memory.save_fact(k,v)
    rules = json.load(open(RULES)) if os.path.exists(RULES) else []
    fired = apply_rules(facts, rules)
    for r in fired: execute(r, facts, state)
    adaptive = analytics.check_adaptive()
    for d in adaptive: execute(d, facts, state)
    for sig in knowledge_use.get_signals():
        execute({'action':'alert','reason':sig['reason']}, facts, state)
    if time.time() - state.get('last_heal',0) > 3600:
        try: self_heal.main(); state['last_heal'] = int(time.time())
        except: pass
    if time.time() - state.get('last_retrain',0) > 86400:
        execute({'action':'retrain_ml','reason':'24ч'}, facts, state)
    try: subprocess.run(['python3','tools/agent/recovery.py'], cwd=BASE, timeout=10)
    except: pass
    save_state(state)
    log(f'✅ run: {len(fired)+len(adaptive)}, память: {memory.stats()}')
    log('=== DONE ===')
if __name__ == '__main__': main()
