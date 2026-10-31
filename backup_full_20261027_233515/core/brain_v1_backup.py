#!/usr/bin/env python3
"""brain.py — центральная нервная система Quantum Lab.
Знает состояние, помнит историю, принимает решения, проверяет здоровье."""
import os, sys, json, time, sqlite3, subprocess
from datetime import datetime, timedelta

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/market.db')
BRAIN_DB = os.path.join(BASE, 'data/brain.db')
RSBOT = os.path.expanduser('~/rsbot')

# === ПАМЯТЬ ===
def init_brain_db():
    c = sqlite3.connect(BRAIN_DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, type TEXT, component TEXT,
        message TEXT, data TEXT);
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, decision TEXT, reason TEXT, result TEXT);
    CREATE TABLE IF NOT EXISTS state_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, state_json TEXT);
    ''')
    c.commit(); c.close()

def log_event(etype, component, message, data=None):
    c = sqlite3.connect(BRAIN_DB)
    c.execute("INSERT INTO events (ts,type,component,message,data) VALUES (?,?,?,?,?)",
              (datetime.now().isoformat(), etype, component, message, json.dumps(data) if data else None))
    c.commit(); c.close()

def log_decision(decision, reason, result):
    c = sqlite3.connect(BRAIN_DB)
    c.execute("INSERT INTO decisions (ts,decision,reason,result) VALUES (?,?,?,?)",
              (datetime.now().isoformat(), decision, reason, result))
    c.commit(); c.close()

def get_history(limit=50):
    c = sqlite3.connect(BRAIN_DB)
    r = c.execute("SELECT ts,type,component,message FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    d = c.execute("SELECT ts,decision,reason,result FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return {'events': [{'ts':x[0],'type':x[1],'component':x[2],'message':x[3]} for x in r],
            'decisions': [{'ts':x[0],'decision':x[1],'reason':x[2],'result':x[3]} for x in d]}

# === СОСТОЯНИЕ ===
def get_data_state():
    if not os.path.exists(DB): return {'pairs': 0, 'candles': 0, 'fresh': False}
    try:
        c = sqlite3.connect(DB, timeout=5)
        r = c.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM candles").fetchone()
        c.close()
        mtime = datetime.fromtimestamp(os.path.getmtime(DB))
        fresh = (datetime.now() - mtime).total_seconds() < 6*3600
        return {'pairs': r[1], 'candles': r[0], 'last_update': mtime.isoformat(), 'fresh': fresh}
    except Exception as e:
        return {'error': str(e)}

def get_gate_state():
    p = os.path.join(BASE, 'data/gate_v2.json')
    if not os.path.exists(p): return {'status': 'missing'}
    try:
        d = json.load(open(p))
        mtime = datetime.fromtimestamp(os.path.getmtime(p))
        return {'summary': d.get('summary'), 'last_run': mtime.isoformat(),
                'results_count': len(d.get('results', [])),
                'best': d.get('results', [{}])[0] if d.get('results') else None}
    except Exception as e:
        return {'error': str(e)}

def get_active_state():
    p = os.path.join(BASE, 'data/active_strategies.json')
    if not os.path.exists(p): return {'status': 'missing'}
    try:
        d = json.load(open(p))
        return {'pairs': len(d.get('pairs', {})), 'updated': d.get('updated_at')}
    except: return {'status': 'invalid'}

def get_bots_state():
    bots = [('V1','pm_bot.py','pm_bot.db'), ('V3','pm_bot_v3.py','pm_v3.db'),
            ('V4','pm_bot_v4.py','pm_v4.db'), ('V5','pm_bot_v5.py','pm_v5.db'),
            ('V6.1','pm_bot_v6.py','pm_v6.db'), ('V7','pm_bot_v7.py','pm_v7.db')]
    out = {}
    for name, script, db in bots:
        pid_out = subprocess.run(['pgrep','-f',script], capture_output=True, text=True).stdout.strip()
        pid = int(pid_out.split('\n')[0]) if pid_out else None
        stats = {'pid': pid, 'alive': pid is not None}
        dbp = os.path.join(RSBOT, db)
        if os.path.exists(dbp):
            try:
                bc = sqlite3.connect(dbp, timeout=3)
                r = bc.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2), SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) FROM trades").fetchone()
                bc.close()
                stats.update({'trades': r[0], 'pnl': r[1], 'open': r[2] or 0})
            except: pass
        out[name] = stats
    return out

def get_live_state():
    p = os.path.join(BASE, 'data/live_monitor.json')
    if not os.path.exists(p): return {'status': 'missing'}
    try:
        d = json.load(open(p))
        summary = {}
        for r in d.get('results', []):
            s = r.get('status', '?'); summary[s] = summary.get(s, 0) + 1
        return {'summary': summary, 'results': d.get('results', [])}
    except: return {'status': 'invalid'}

def get_lab_state():
    procs = {}
    for name, pattern in [('orchestrator','orchestrator.py'), ('data_manager','data_manager.py'),
                          ('gate','gate_v2.py'), ('evolution','evolution.py'), ('ai','ai_generator.py')]:
        out = subprocess.run(['pgrep','-f',pattern], capture_output=True, text=True).stdout.strip()
        procs[name] = {'pid': int(out.split('\n')[0]) if out else None, 'running': bool(out)}
    return procs

def get_system_state():
    try:
        with open('/proc/loadavg') as f: load = float(f.read().split()[0])
        with open('/proc/meminfo') as f: mem = {l.split(':')[0]: int(l.split()[1])//1024 for l in f if ':' in l}
        return {'load': load, 'mem_free_mb': mem.get('MemFree',0)+mem.get('Buffers',0)+mem.get('Cached',0)}
    except: return {}

def get_full_state():
    state = {
        'timestamp': datetime.now().isoformat(),
        'data': get_data_state(),
        'gate': get_gate_state(),
        'active': get_active_state(),
        'bots': get_bots_state(),
        'live': get_live_state(),
        'lab': get_lab_state(),
        'system': get_system_state(),
    }
    c = sqlite3.connect(BRAIN_DB)
    c.execute("INSERT INTO state_history (ts,state_json) VALUES (?,?)", (state['timestamp'], json.dumps(state)))
    c.execute("DELETE FROM state_history WHERE id < (SELECT MAX(id) FROM state_history) - 1000")
    c.commit(); c.close()
    return state

# === РЕШЕНИЯ ===
def decide(state):
    decisions = []
    bots = state.get('bots', {})
    dead = [n for n, b in bots.items() if not b.get('alive')]
    if dead:
        decisions.append({'action': 'restart_bots', 'reason': f'мёртвые: {dead}', 'priority': 1})
    data = state.get('data', {})
    if not data.get('fresh') or data.get('pairs',0) < 10:
        decisions.append({'action': 'run_data_manager', 'reason': f"данные: {data.get('pairs')} пар, fresh={data.get('fresh')}", 'priority': 2})
    gate = state.get('gate', {})
    if gate.get('status') == 'missing' or not gate.get('last_run'):
        decisions.append({'action': 'run_gate', 'reason': 'gate не прогонялся', 'priority': 3})
    active = state.get('active', {})
    if active.get('status') == 'missing':
        decisions.append({'action': 'update_active', 'reason': 'active_strategies нет', 'priority': 4})
    live = state.get('live', {})
    if live.get('summary', {}).get('QUARANTINE', 0) > 0:
        decisions.append({'action': 'quarantine', 'reason': f"карантин: {live['summary']['QUARANTINE']}", 'priority': 5})
    return sorted(decisions, key=lambda x: x['priority'])

# === HEALTH ===
def health_check():
    state = get_full_state()
    issues = []
    for name, bot in state.get('bots', {}).items():
        if not bot.get('alive'): issues.append(f'{name}: мёртв')
    if not state.get('data', {}).get('fresh'): issues.append('data: устарели')
    if state.get('system', {}).get('load', 0) > 8: issues.append(f"load: {state['system']['load']}")
    if state.get('system', {}).get('mem_free_mb', 0) < 50: issues.append('mem: мало')
    return {'healthy': len(issues) == 0, 'issues': issues, 'state': state}

if __name__ == '__main__':
    init_brain_db()
    import sys as _s
    if len(_s.argv) > 1 and _s.argv[1] == 'health':
        h = health_check()
        print(json.dumps({'healthy': h['healthy'], 'issues': h['issues']}, indent=2, ensure_ascii=False))
    elif len(_s.argv) > 1 and _s.argv[1] == 'history':
        print(json.dumps(get_history(), indent=2, ensure_ascii=False)[:3000])
    else:
        state = get_full_state()
        print(json.dumps(state, indent=2, ensure_ascii=False)[:3000])
        print('\n=== DECISIONS ===')
        for d in decide(state): print(f"  [P{d['priority']}] {d['action']}: {d['reason']}")
