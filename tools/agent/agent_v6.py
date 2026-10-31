#!/usr/bin/env python3
"""Агент v6: RAG + ML + все модули вместе."""
import os, sys, json, sqlite3, subprocess, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory, analytics_v2, knowledge_use, self_heal

BASE = os.path.expanduser('~/quantum_lab')
AGENT_DIR = os.path.join(BASE, 'tools/agent')
RULES = os.path.join(AGENT_DIR, 'rules.json')
LOG = os.path.join(BASE, 'logs/agent.log')
STATE = os.path.join(AGENT_DIR, 'state.json')

def log(m):
    print(f'[{datetime.now():%H:%M:%S}] {m}', flush=True)
    with open(LOG, 'a') as f: f.write(f'[{datetime.now():%H:%M:%S}] {m}\n')

def load_state():
    if os.path.exists(STATE):
        try: return json.load(open(STATE))
        except: pass
    return {'last_retrain': 0, 'last_heal': 0}

def save_state(s):
    json.dump(s, open(STATE, 'w'))

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
    ml = analytics_v2.get_ml_state()
    if ml:
        facts['ml_bad'] = [s for s, v in ml.items() if v.get('proba_long', 0.5) < 0.05 or v.get('proba_long', 0.5) > 0.95]
    else:
        facts['ml_bad'] = []
    return facts

def apply_rules(facts, rules):
    actions = []
    for rule in rules:
        cond = rule.get('condition', {})
        ok = True
        for k, v in cond.items():
            if k.endswith('_lt') and not (facts.get(k[:-3]) is not None and facts.get(k[:-3]) < v): ok = False
            elif k.endswith('_gt') and not (facts.get(k[:-3]) is not None and facts.get(k[:-3]) > v): ok = False
            elif k.endswith('_false') and not (facts.get(k[:-6]) is False): ok = False
            elif k.endswith('_true') and not (facts.get(k[:-5]) is True): ok = False
            elif not k.endswith(('_lt','_gt','_false','_true')) and facts.get(k) != v: ok = False
        if ok: actions.append(rule)
    return actions

def execute_action(action, facts, state):
    a = action.get('action')
    rule = action.get('name', action.get('reason', '?'))
    success = False
    try:
        if a == 'restart':
            proc = action['target']
            subprocess.run(['pkill', '-9', '-f', proc], capture_output=True)
            time.sleep(2)
            cmd = action.get('cmd', f'python3 -u core/{proc}.py')
            subprocess.Popen(cmd.split(), cwd=BASE,
                             stdout=open(os.path.join(BASE, f'logs/{proc}.log'), 'a'),
                             stderr=subprocess.STDOUT)
            log(f'🔧 restart {proc}')
            success = True
        elif a == 'retrain_ml':
            subprocess.Popen(['python3', 'core/ml_online_simple.py'], cwd=BASE,
                             stdout=open(os.path.join(BASE, 'logs/ml_online.log'), 'a'),
                             stderr=subprocess.STDOUT)
            log('🔧 retrain ML')
            state['last_retrain'] = int(time.time())
            success = True
        elif a == 'stop_v4':
            subprocess.run(['pkill', '-9', '-f', 'okx_bot_paper_v4'], capture_output=True)
            try:
                rp = os.path.join(AGENT_DIR, 'recovery.json')
                rs = json.load(open(rp)) if os.path.exists(rp) else {}
                rs['stopped_v4_at'] = int(time.time())
                json.dump(rs, open(rp, 'w'))
            except: pass
            log(f'🛑 STOP v4: {action.get("reason")}')
            success = True
        elif a == 'alert':
            msg = action.get('message', action.get('reason', ''))
            log(f'🚨 ALERT: {msg}')
            with open(os.path.join(BASE, 'logs/agent_alerts.log'), 'a') as f:
                f.write(f'[{datetime.now()}] {msg}\n')
            success = True
        elif a == 'log':
            log(f'📝 {action.get("reason", "")}')
            success = True
    except Exception as e:
        log(f'❌ action error: {e}')
    memory.save_action(a, action.get('target', rule), 'ok' if success else 'fail', success)
    memory.update_rule_weight(rule, success)
    # === EXPERIENCE: сохраняем контекст + результат ===
    try:
        context = {k: v for k, v in facts.items() if k.startswith(('proc_', 'age_', 'pnl_', 'ml_'))}
        outcome = 'success' if success else 'fail'
        score = 1.0 if success else (-1.0 if a != 'log' else 0.0)
        memory.save_experience(rule, context, outcome, score)
    except Exception as e:
        log(f'⚠️ experience save error: {e}')
    # === PENDING: отложенная проверка результата ===
    try:
        check_type = None
        check_at = None
        if a == 'restart':
            check_type = 'proc_alive'
            check_at = time.time() + 60  # через 1 мин
        elif a == 'retrain_ml':
            check_type = 'ml_normal'
            check_at = time.time() + 120  # через 2 мин
        elif a == 'stop_v4':
            check_type = 'pnl_up'
            check_at = time.time() + 3600  # через 1 час
        if check_type and action.get('target'):
            memory.add_pending(a, action['target'], rule, context, check_at, check_type)
            log(f'⏳ pending: {a} {action["target"]} → проверить через {int(check_at-time.time())}с ({check_type})')
    except Exception as e:
        log(f'⚠️ pending error: {e}')
    return success

def main():
    log('=== AGENT v6 RUN (RAG + ML) ===')
    memory.init()
    state = load_state()
    facts = collect_facts()
    for k, v in facts.items():
        memory.save_fact(k, v)
    
    # 1. Правила
    rules = json.load(open(RULES)) if os.path.exists(RULES) else []
    fired = apply_rules(facts, rules)
    for r in fired:
        execute_action(r, facts, state)
    
    # 2. Адаптивность (RAG + ML)
    adaptive = analytics_v2.check_adaptive(facts)
    for d in adaptive:
        execute_action(d, facts, state)
    
    # 3. Сигналы знаний
    for sig in knowledge_use.get_signals():
        execute_action({'action': 'alert', 'reason': sig['reason']}, facts, state)
    
    # 4. Self-heal (раз в час)
    if time.time() - state.get('last_heal', 0) > 3600:
        try:
            self_heal.main()
            state['last_heal'] = int(time.time())
        except Exception as e:
            log(f'self_heal error: {e}')
    
    # 5. Автопереобучение ML (раз в 24ч)
    if time.time() - state.get('last_retrain', 0) > 86400:
        execute_action({'action': 'retrain_ml', 'reason': '24ч'}, facts, state)
    
    # 6. PENDING: проверяем отложенные результаты
    try:
        pend = memory.get_pending_ready()
        for pid, pa, pt, pr, pctx, ptype in pend:
            if ptype == 'proc_alive':
                alive = bool(subprocess.run(['pgrep', '-f', pt], capture_output=True).stdout.strip())
                memory.resolve_pending(pid, alive, 1.0 if alive else -1.0)
                log(f'🔍 pending: {pa} {pt} → {"✅ жив" if alive else "❌ мёртв"}')
            elif ptype == 'ml_normal':
                mlp = os.path.join(BASE, 'data/ml_predictions_online.json')
                ok = False
                if os.path.exists(mlp):
                    try:
                        d = json.load(open(mlp))
                        bad = [s for s, v in d.get('predictions', {}).items() if v.get('proba_long', 0.5) < 0.05 or v.get('proba_long', 0.5) > 0.95]
                        ok = len(bad) == 0
                    except: pass
                memory.resolve_pending(pid, ok, 1.0 if ok else -1.0)
                log(f'🔍 pending: {pa} → {"✅ ML норма" if ok else "❌ ML насыщена"}')
            elif ptype == 'pnl_up':
                try:
                    c = sqlite3.connect(os.path.join(BASE, 'data/okx_paper_v4.db'))
                    pnl = c.execute("SELECT ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status='CLOSED' AND closed_at > strftime('%s','now')-3600").fetchone()[0] or 0
                    c.close()
                    ok = pnl > 0
                    memory.resolve_pending(pid, ok, 1.0 if ok else -1.0)
                    log(f'🔍 pending: stop_v4 → PnL за час {pnl} {"✅ растёт" if ok else "❌ не растёт"}')
                except: pass
    except Exception as e:
        log(f'⚠️ pending check error: {e}')

    # 7. Recovery v4
    try:
        subprocess.run(['python3', 'tools/agent/recovery.py'], cwd=BASE, timeout=10)
    except: pass
    
    save_state(state)
    log(f'✅ run: правил {len(fired)+len(adaptive)}, память: {memory.stats()}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
