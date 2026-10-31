#!/usr/bin/env python3
"""brain.py v2 — полный мозг: STATE + MEMORY + DECISION + EXECUTOR.
Сам решает, что делать, и сам исполняет."""
import os, sys, json, time, sqlite3, subprocess
from datetime import datetime, timedelta

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/market.db')
ORACLE_DB = os.path.join(BASE, 'data/oracle.db')
BRAIN_DB = os.path.join(BASE, 'data/brain.db')
RSBOT = os.path.expanduser('~/rsbot')

PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT']
TFS_FOR_GATE = [('15m','current'), ('4h','open')]
BOTS = [('V1','pm_bot.py','pm_bot.db'),('V4','pm_bot_v4.py','pm_v4.db'),
        ('V5','pm_bot_v5.py','pm_v5.db'),('V6.1','pm_bot_v6.py','pm_v6.db'),('V7','pm_bot_v7.py','pm_v7.db')]

# ═══ ПАМЯТЬ ═══
def init_db():
    c = sqlite3.connect(BRAIN_DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, type TEXT, component TEXT, message TEXT, data TEXT);
    CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, decision TEXT, reason TEXT, result TEXT);
    CREATE TABLE IF NOT EXISTS action_history (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, action TEXT, success INTEGER, duration REAL);
    CREATE TABLE IF NOT EXISTS state_history (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, state_json TEXT);
    ''')
    c.commit(); c.close()

def log_event(etype, component, message, data=None):
    try:
        c = sqlite3.connect(BRAIN_DB)
        c.execute("INSERT INTO events (ts,type,component,message,data) VALUES (?,?,?,?,?)",
                  (datetime.now().isoformat(), etype, component, message, json.dumps(data) if data else None))
        c.commit(); c.close()
    except: pass

def log_decision(decision, reason, result):
    try:
        c = sqlite3.connect(BRAIN_DB)
        c.execute("INSERT INTO decisions (ts,decision,reason,result) VALUES (?,?,?,?)",
                  (datetime.now().isoformat(), decision, reason, result))
        c.commit(); c.close()
    except: pass

def log_action(action, success, duration):
    try:
        c = sqlite3.connect(BRAIN_DB)
        c.execute("INSERT INTO action_history (ts,action,success,duration) VALUES (?,?,?,?)",
                  (datetime.now().isoformat(), action, int(success), duration))
        c.commit(); c.close()
    except: pass

def last_action_time(action):
    try:
        c = sqlite3.connect(BRAIN_DB)
        r = c.execute("SELECT ts FROM action_history WHERE action=? ORDER BY id DESC LIMIT 1", (action,)).fetchone()
        c.close()
        if not r: return None
        return datetime.fromisoformat(r[0])
    except: return None

def get_history(limit=100):
    try:
        c = sqlite3.connect(BRAIN_DB)
        ev = c.execute("SELECT ts,type,component,message FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        de = c.execute("SELECT ts,decision,reason,result FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        ac = c.execute("SELECT ts,action,success,duration FROM action_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        c.close()
        return {'events': [{'ts':x[0],'type':x[1],'component':x[2],'message':x[3]} for x in ev],
                'decisions': [{'ts':x[0],'decision':x[1],'reason':x[2],'result':x[3]} for x in de],
                'actions': [{'ts':x[0],'action':x[1],'success':bool(x[2]),'duration':x[3]} for x in ac]}
    except: return {'events':[],'decisions':[],'actions':[]}

# ═══ СОСТОЯНИЕ ═══
def pgrep(pattern):
    r = subprocess.run(['pgrep','-f',pattern], capture_output=True, text=True)
    out = r.stdout.strip()
    return int(out.split('\n')[0]) if out else None

def get_data_state():
    if not os.path.exists(DB): return {'pairs':0,'candles':0,'fresh':False,'missing_tfs':[]}
    try:
        c = sqlite3.connect(DB, timeout=5)
        pairs = c.execute("SELECT COUNT(DISTINCT symbol) FROM candles").fetchone()[0]
        candles = c.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        # какие пары имеют < 6 ТФ
        rows = c.execute("SELECT symbol, COUNT(DISTINCT tf) FROM candles GROUP BY symbol").fetchall()
        c.close()
        missing = [r[0] for r in rows if r[1] < 6]
        mtime = datetime.fromtimestamp(os.path.getmtime(DB))
        fresh = (datetime.now()-mtime).total_seconds() < 6*3600
        return {'pairs':pairs,'candles':candles,'fresh':fresh,'missing_tfs':missing,
                'last_update':mtime.isoformat()}
    except Exception as e: return {'error':str(e)}

def get_oracle_state():
    if not os.path.exists(ORACLE_DB): return {'status':'missing'}
    try:
        c = sqlite3.connect(ORACLE_DB, timeout=3)
        rows = c.execute("""SELECT p.symbol, p.price, r.regime, r.atr, r.adx, r.vol_z
                           FROM prices p JOIN regime r ON p.symbol=r.symbol AND p.ts=r.ts
                           WHERE p.ts = (SELECT MAX(ts) FROM prices)""").fetchall()
        c.close()
        return [{'symbol':x[0],'price':x[1],'regime':x[2],'atr':x[3],'adx':x[4],'vol_z':x[5]} for x in rows]
    except: return []

def get_gate_state():
    p = os.path.join(BASE, 'data/gate_all.json')
    if not os.path.exists(p): return {'status':'missing'}
    try:
        d = json.load(open(p))
        mtime = datetime.fromtimestamp(os.path.getmtime(p))
        return {'summary':d.get('summary'),'last_run':mtime.isoformat(),'best':d.get('results',[{}])[0] if d.get('results') else None}
    except: return {'status':'invalid'}

def get_active_state():
    p = os.path.join(BASE, 'data/active_strategies.json')
    if not os.path.exists(p): return {'status':'missing','pairs':0}
    try:
        d = json.load(open(p)); pairs = d.get('pairs',{})
        return {'pairs':len(pairs),'trades':sum(1 for v in pairs.values() if v.get('trade')),
                'updated':d.get('updated_at')}
    except: return {'status':'invalid'}

def get_bots_state():
    out = {}
    for name, script, db in BOTS:
        pid = pgrep(script)
        s = {'pid':pid,'alive':pid is not None}
        p = os.path.join(RSBOT, db)
        if os.path.exists(p):
            try:
                c = sqlite3.connect(p, timeout=3)
                r = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2), SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) FROM trades").fetchone()
                c.close()
                s.update({'trades':r[0],'pnl':r[1],'open':r[2] or 0})
            except: pass
        out[name] = s
    return out

def get_live_state():
    p = os.path.join(BASE, 'data/live_monitor.json')
    if not os.path.exists(p): return {'status':'missing'}
    try:
        d = json.load(open(p))
        summary = {}
        for r in d.get('results',[]):
            s = r.get('status','?'); summary[s] = summary.get(s,0)+1
        return {'summary':summary,'results':d.get('results',[])}
    except: return {'status':'invalid'}

def get_lab_state():
    return {name: {'pid': pgrep(pattern), 'running': pgrep(pattern) is not None}
            for name, pattern in [('brain_loop','brain_loop.py'),('oracle','oracle.py loop'),
                                   ('data_manager','data_manager.py'),('gate','gate_v3.py'),
                                   ('brain_api','brain_api.py')]}

def get_system_state():
    try:
        mem = {}
        with open('/proc/meminfo') as f:
            for line in f:
                if ':' in line:
                    parts = line.split()
                    try: mem[parts[0].rstrip(':')] = int(parts[1])//1024
                    except: pass
        free = mem.get('MemAvailable', mem.get('MemFree', 100))
        # loadavg недоступен в Termux — используем 0
        load = 0
        try:
            with open('/proc/loadavg') as f: load = float(f.read().split()[0])
        except: pass
        return {'load': load, 'mem_free_mb': free}
    except Exception as e:
        return {'load': 0, 'mem_free_mb': 100}

def check_live_performance():
    """Live WR vs backtest → карантин/усиление."""
    import sqlite3, json as _j, os as _o
    active_path = _o.path.join(BASE, 'data/active_strategies.json')
    if not _o.path.exists(active_path): return []
    active = _j.load(open(active_path))
    results = []
    for key, cfg in active.get('pairs', {}).items():
        if not cfg.get('trade'): continue
        sym = cfg['symbol']; strat = cfg['strategy']; bt_wr = cfg['wr']
        # Ищем в БД ботов
        for db in ['pm_v6.db', 'pm_v7.db']:
            dbp = _o.path.join(RSBOT, db)
            if not _o.path.exists(dbp): continue
            try:
                c = sqlite3.connect(dbp, timeout=3)
                r = c.execute("SELECT COUNT(*), SUM(CASE WHEN win_flag=1 THEN 1 ELSE 0 END) FROM trades WHERE strategy=? AND win_flag IS NOT NULL", (strat,)).fetchone()
                c.close()
                n = r[0] or 0; wins = r[1] or 0
                if n >= 20:
                    live_wr = 100.0*wins/n
                    delta = live_wr - bt_wr
                    if delta < -5: results.append({'action': 'quarantine', 'key': key, 'reason': f'live WR {live_wr:.1f}% < bt {bt_wr:.1f}%'})
                    elif delta > 5: results.append({'action': 'strengthen', 'key': key, 'reason': f'live WR {live_wr:.1f}% > bt {bt_wr:.1f}%'})
            except: pass
    return results

def get_full_state():
    state = {
        'timestamp': datetime.now().isoformat(),
        'data': get_data_state(), 'oracle': get_oracle_state(),
        'gate': get_gate_state(), 'active': get_active_state(),
        'bots': get_bots_state(), 'live': get_live_state(),
        'lab': get_lab_state(), 'system': get_system_state(),
    }
    try:
        c = sqlite3.connect(BRAIN_DB)
        c.execute("INSERT INTO state_history (ts,state_json) VALUES (?,?)", (state['timestamp'], json.dumps(state)))
        c.execute("DELETE FROM state_history WHERE id < (SELECT MAX(id) FROM state_history) - 1000")
        c.commit(); c.close()
    except: pass
    return state

# ═══ РЕШЕНИЯ ═══
def _update_state(key):
    """Обновляет auto_state.json (последние запуски P18/P19/P20)."""
    state_path = os.path.join(BASE, 'data/auto_state.json')
    try:
        d = json.load(open(state_path)) if os.path.exists(state_path) else {}
    except:
        d = {}
    d[key] = int(time.time())
    try:
        json.dump(d, open(state_path, 'w'), indent=2, ensure_ascii=False)
    except:
        pass

def decide(state):
    # Эволюция каждые 6 часов (всегда)
    import time as _t
    if not hasattr(_decide_inner, '_last_evo') or _t.time() - _decide_inner._last_evo > 21600:
        _decide_inner._last_evo = _t.time()
        pass  # evolution: только через sequential_runner

    return _decide_inner(state)

def _decide_inner(state):
    ae_state = os.path.join(BASE, 'data/auto_state.json')  # для P18-P24
    # STOP_BOT: не GOLDEN + WR<45% на 20+
    try:
        import sqlite3 as _sq, os as _os, json as _js
        active_path = _os.path.join(BASE, 'data/active_strategies.json')
        if _os.path.exists(active_path):
            active = _js.load(open(active_path))
            for bot_db, bot_script in [('pm_v3.db', 'pm_bot_v3_disabled.py'), ('pm_v5.db', 'pm_bot_v5.py')]:
                dbp = _os.path.join(RSBOT, bot_db)
                if not _os.path.exists(dbp): continue
                try:
                    c = _sq.connect(dbp, timeout=3)
                    r = c.execute("SELECT COUNT(*), SUM(CASE WHEN win_flag=1 THEN 1 ELSE 0 END) FROM trades WHERE win_flag IS NOT NULL").fetchone()
                    c.close()
                    n = r[0] or 0; wins = r[1] or 0
                    if n >= 20:
                        wr = 100.0*wins/n
                        if wr < 45:
                            decisions.append({'action': 'stop_bot', 'reason': f'{bot_script}: WR={wr:.1f}% на {n} (не GOLDEN)', 'priority': 3, 'bot': bot_script})
                except: pass
    except: pass
    # АГЕНТЫ (каждые 5 мин)
    import time as _t
    decisions = []
    if not hasattr(_decide_inner, '_last_agents') or _t.time() - _decide_inner._last_agents > 300:
        _decide_inner._last_agents = _t.time()
        decisions.append({'action': 'run_agents', 'reason': 'прошло 5 мин', 'priority': 5})
    # P1: боты мертвы
    dead = [n for n,b in state.get('bots',{}).items() if not b.get('alive')]
    if dead:
        decisions.append({'action':'restart_bots','reason':f'мёртвые: {dead}','priority':1})
    # P2: данные устарели
    data = state.get('data',{})
    if not data.get('fresh'):
        decisions.append({'action':'run_data_manager','reason':f"данные устарели: {data.get('last_update')}",'priority':2})
    # P3: данных мало
    elif data.get('pairs',0) < 10:
        decisions.append({'action':'run_data_manager','reason':f"мало пар: {data.get('pairs')}",'priority':3})
    # P4: gate не прогонялся
    gate = state.get('gate',{})
    if gate.get('status') == 'missing':
        pass  # gate: только через sequential_runner
    else:
        # P6: active устарел относительно gate
        active = state.get('active',{})
        gate_mtime = gate.get('last_run','')
        active_mtime = active.get('updated','')
        if gate_mtime and active_mtime and gate_mtime > active_mtime:
            decisions.append({'action':'update_active','reason':'gate новее active','priority':6})
        # P7: есть GOLDEN, но не в active
        summary = gate.get('summary',{})
        if summary.get('GOLDEN',0) > 0 and active.get('trades',0) == 0:
            decisions.append({'action':'update_active','reason':'GOLDEN не в active','priority':7})
    # P8: карантин
    live = state.get('live',{})
    if live.get('summary',{}).get('QUARANTINE',0) > 0:
        decisions.append({'action':'quarantine','reason':f"карантин: {live['summary']['QUARANTINE']}",'priority':8})
    # P11: память
    sys_state = state.get('system',{})
    if sys_state.get('mem_free_mb',0) < 50:
        decisions.append({'action':'kill_heavy','reason':f"память: {sys_state.get('mem_free_mb')} МБ",'priority':11})

    # P17: cleanup (раз в 1 час)
    cl_path = os.path.join(BASE, 'data/okx_paper.db')
    if os.path.exists(cl_path) and (time.time() - os.path.getmtime(cl_path)) > 3600:
        decisions.append({'action':'run_cleanup_trades','reason':'очистка старых сделок (1ч)','priority':17})

    # P21: auto_data (раз в 1 час)
    ad_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            ad_last = _ae.get('last_data', 0)
        except: pass
    if time.time() - ad_last > 3600:
        decisions.append({'action':'run_auto_data','reason':'автодокачка (1ч)','priority':21})

    # P22: auto_apply_graals (раз в 6 часов)
    ag_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            ag_last = _ae.get('last_apply', 0)
        except: pass
    if time.time() - ag_last > 6*3600:
        decisions.append({'action':'run_auto_apply','reason':'авто-граали (6ч)','priority':22})

    # P23: auto_stop_losers (раз в 1 час)
    as_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            as_last = _ae.get('last_stop', 0)
        except: pass
    if time.time() - as_last > 3600:
        decisions.append({'action':'run_auto_stop','reason':'авто-стоп (1ч)','priority':23})

    # P24: auto_compare (раз в 2 часа)
    ac2_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            ac2_last = _ae.get('last_compare2', 0)
        except: pass
    if time.time() - ac2_last > 2*3600:
        decisions.append({'action':'run_auto_compare','reason':'сравнение (2ч)','priority':24})

    # P25: auto_filter_optimizer (раз в 6 часов)
    afo_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            afo_last = _ae.get('last_filter_opt', 0)
        except: pass
    if time.time() - afo_last > 6*3600:
        decisions.append({'action':'run_auto_filter_opt','reason':'авто-фильтры (6ч)','priority':25})

    # P26: auto_apply_filters (раз в 6 часов)
    aaf_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            aaf_last = _ae.get('last_filter_apply', 0)
        except: pass
    if time.time() - aaf_last > 6*3600:
        decisions.append({'action':'run_auto_filter_apply','reason':'внедрение фильтров (6ч)','priority':26})

    # P27: auto_evolve_by_regime (раз в 6 часов)
    aer_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            aer_last = _ae.get('last_evolve_regime', 0)
        except: pass
    if time.time() - aer_last > 6*3600:
        decisions.append({'action':'run_auto_evolve_regime','reason':'авто-эволюция по режимам (6ч)','priority':27})

    # P28: auto_apply_regime (раз в 6 часов)
    aar_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            aar_last = _ae.get('last_apply_regime', 0)
        except: pass
    if time.time() - aar_last > 6*3600:
        decisions.append({'action':'run_auto_apply_regime','reason':'внедрение по режимам (6ч)','priority':28})

    # P29: auto_obi_tuner (раз в 6 часов)
    aot_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            aot_last = _ae.get('last_obi_tuner', 0)
        except: pass
    if time.time() - aot_last > 6*3600:
        decisions.append({'action':'run_auto_obi_tuner','reason':'авто-OBI (6ч)','priority':29})

    # P30: auto_tpsl_tuner (раз в 6 часов)
    att_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            att_last = _ae.get('last_tpsl_tuner', 0)
        except: pass
    if time.time() - att_last > 6*3600:
        decisions.append({'action':'run_auto_tpsl_tuner','reason':'авто-TP/SL (6ч)','priority':30})

    # P31: auto_adapt_realtime (каждые 15 мин)
    aar_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            aar_last = _ae.get('last_adapt', 0)
        except: pass
    if time.time() - aar_last > 15*60:
        decisions.append({'action':'run_auto_adapt','reason':'адаптация (15мин)','priority':31})

    # P32: ml_predict (каждые 15 мин)
    mlp_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            mlp_last = _ae.get('last_ml_predict', 0)
        except: pass
    if time.time() - mlp_last > 15*60:
        decisions.append({'action':'run_ml_predict','reason':'ML предсказание (15мин)','priority':32})

    # P33: ml_predict_online (каждые 15 мин)
    mlpo_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            mlpo_last = _ae.get('last_ml_predict_online', 0)
        except: pass
    if time.time() - mlpo_last > 15*60:
        decisions.append({'action':'run_ml_predict_online','reason':'ML online (15мин)','priority':33})

# [DISABLED]     # P36: data_manager (каждые 5 мин)
# [DISABLED]     dm_last = 0
# [DISABLED]     if os.path.exists(ae_state):
# [DISABLED]         try: dm_last = json.load(open(ae_state)).get('last_data_manager', 0)
# [DISABLED]         except: pass
# [DISABLED]     if time.time() - dm_last > 5*60:
# [DISABLED]         decisions.append({'action':'run_data_manager','reason':'data update (5мин)','priority':36})
# [DISABLED] 
    # P34: ml_online_simple retrain (24ч, в 03:00)
    mr_last = 0
    if os.path.exists(ae_state):
        try: mr_last = json.load(open(ae_state)).get('last_ml_retrain', 0)
        except: pass
    if (time.time() - mr_last > 24*3600) and (datetime.now().hour == 3):
        decisions.append({'action':'run_ml_retrain','reason':'ML retrain (24ч, 03:00)','priority':34})

    # P35: ml_health_check (6ч)
    mh_last = 0
    if os.path.exists(ae_state):
        try: mh_last = json.load(open(ae_state)).get('last_ml_health_check', 0)
        except: pass
    if time.time() - mh_last > 6*3600:
        decisions.append({'action':'run_ml_health_check','reason':'ML health (6ч)','priority':35})

    # P18: auto_evolve (раз в 6 часов)
    ae_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            ae_last = _ae.get('last_evolve', 0)
        except: pass
    if time.time() - ae_last > 6*3600:
        decisions.append({'action':'run_auto_evolve','reason':'авто-эволюция (6ч)','priority':18})

    # P19: auto_filter (раз в 2 часа)
    af_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            af_last = _ae.get('last_filter', 0)
        except: pass
    if time.time() - af_last > 2*3600:
        decisions.append({'action':'run_auto_filter','reason':'авто-фильтр (2ч)','priority':19})

    # P20: auto_compare (раз в 1 час)
    ac_last = 0
    if os.path.exists(ae_state):
        try:
            _ae = json.load(open(ae_state))
            ac_last = _ae.get('last_compare', 0)
        except: pass
    if time.time() - ac_last > 3600:
        decisions.append({'action':'run_auto_compare','reason':'сравнение ботов (1ч)','priority':20})

    # P12: multi_backtest (раз в 4 часа) — смотрим на holy_grail, не by_regime (защищён 444)
    mb_path = os.path.join(BASE, 'data/holy_grail.json')
    if not os.path.exists(mb_path) or (time.time() - os.path.getmtime(mb_path)) > 4*3600:
        decisions.append({'action':'run_multi_backtest','reason':'многоуровневый бэктест (4ч)','priority':12})
    # P13: holy_grail (раз в 4 часа)
    hg_path = os.path.join(BASE, 'data/holy_grail.json')
    if not os.path.exists(hg_path) or (time.time() - os.path.getmtime(hg_path)) > 4*3600:
        decisions.append({'action':'run_holy_grail','reason':'поиск граалей (4ч)','priority':13})

    # P14: sync_grails — ТОЛЬКО если by_regime НЕТ (multi_backtest приоритет)
    tp_path2 = os.path.join(BASE, 'data/okx_tpsl_by_regime.json')
    if not os.path.exists(tp_path2):
        decisions.append({'action':'run_sync_grails','reason':'by_regime нет — sync','priority':14})

    # P16: filter_adjust (раз в 1 час)
    pol_path2 = os.path.join(BASE, 'data/okx_policy.json')
    if not os.path.exists(pol_path2) or (time.time() - os.path.getmtime(pol_path2)) > 3600:
        decisions.append({'action':'run_filter_adjust','reason':'авто-настройка фильтра (1ч)','priority':16})

    # P2b: data_manager по age_hours (раз в 1 час)
    dr_path = os.path.join(BASE, 'data/data_report.json')
    if os.path.exists(dr_path):
        try:
            _dr = __import__('json').load(open(dr_path))
            _age = _dr.get('result',{}).get('age_hours', 0)
            if _age > 1:
                decisions.append({'action':'run_data_manager','reason':f'данные {_age:.1f}ч','priority':2})
        except: pass
    return sorted(decisions, key=lambda x: x['priority'])

# ═══ ИСПОЛНИТЕЛЬ ═══
def _adjust_filter_policy():
    """Анализирует последние сделки OKX-бота и решает: включать ли фильтр.
    Пишет data/okx_policy.json."""
    import sqlite3, json
    DB = os.path.join(BASE, 'data/okx_paper.db')
    POLICY = os.path.join(BASE, 'data/okx_policy.json')
    try:
        c = sqlite3.connect(DB, timeout=10)
        rows = c.execute(
            "SELECT pnl FROM trades WHERE status='CLOSED' AND tp IS NOT NULL "
            "ORDER BY exit_ts DESC LIMIT 20"
        ).fetchall()
        c.close()
    except Exception as e:
        print(f'⚠️ _adjust_filter_policy: {e}')
        return
    # Дефолт, если policy нет
    pol = {'filter': {'enabled': False, 'adx_threshold': 50},
           'updated_at': '', 'source': 'default'}
    if os.path.exists(POLICY):
        try:
            pol = json.load(open(POLICY))
        except: pass
    if len(rows) < 10:
        pol['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        pol['source'] = 'brain_filter_adjust'
        json.dump(pol, open(POLICY, 'w'), indent=2, ensure_ascii=False)
        print(f'ℹ️ filter_adjust: мало сделок ({len(rows)}), жду')
        return
    pnls = [r[0] for r in rows if r[0] is not None]
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(pnls) if pnls else 0
    total = sum(pnls)
    current = pol.get('filter', {}).get('enabled', False)
    if wr < 0.45 and total < 0 and not current:
        pol['filter']['enabled'] = True
        pol['filter']['adx_threshold'] = 40
        print(f'✅ filter_adjust: ВКЛ (WR={wr:.1%} PnL={total:+.2f})')
    elif wr >= 0.50 and total >= 0 and current:
        pol['filter']['enabled'] = False
        print(f'✅ filter_adjust: ВЫКЛ (WR={wr:.1%} PnL={total:+.2f})')
    else:
        print(f'ℹ️ filter_adjust: без изменений (WR={wr:.1%} PnL={total:+.2f} enabled={current})')
    pol['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    pol['source'] = 'brain_filter_adjust'
    json.dump(pol, open(POLICY, 'w'), indent=2, ensure_ascii=False)


def _cleanup_old_trades():
    """Удаляет закрытые сделки старше 3 дней, чтобы база не пухла."""
    import sqlite3, os
    DB = os.path.join(BASE, 'data/okx_paper.db')
    try:
        c = sqlite3.connect(DB, timeout=10)
        # Удаляем CLOSED сделки, которые закрылись более 3 дней (259200 сек) назад
        c.execute("DELETE FROM trades WHERE status='CLOSED' AND exit_ts < ?", (int(time.time()) - 259200,))
        c.commit()
        c.close()
    except Exception as e:
        print(f'⚠️ _cleanup_old_trades: {e}')


def execute(decision):
    action = decision['action']
    start = time.time()
    success = False
    try:
        if action == 'restart_bots':
            for name, script, db in BOTS:
                pid = pgrep(script)
                if not pid:
                    subprocess.Popen(['python3','-u',os.path.join(RSBOT,script)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            success = True
        elif action == 'run_data_manager':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/data_manager.py')],
                            stdout=open(os.path.join(BASE,'logs/data_manager.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            success = True
        elif action == 'run_holy_grail':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'holy_grail.py')],
                            stdout=open(os.path.join(BASE,'logs/holy_grail.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)

        elif action == 'run_auto_data':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_data.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_data.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_data')
            success = True
        elif action == 'run_auto_apply':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_apply_graals.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_apply_graals.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_apply')
            success = True
        elif action == 'run_auto_stop':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_stop_losers.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_stop_losers.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_stop')
            success = True
        elif action == 'run_auto_filter_opt':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_filter_optimizer.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_filter_optimizer.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_filter_opt')
            success = True
        elif action == 'run_auto_filter_apply':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_apply_filters.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_apply_filters.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_filter_apply')
            success = True
        elif action == 'run_auto_evolve_regime':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_evolve_by_regime.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_evolve_by_regime.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_evolve_regime')
            success = True
        elif action == 'run_auto_apply_regime':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_apply_regime.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_apply_regime.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_apply_regime')
            success = True
        elif action == 'run_auto_obi_tuner':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_obi_tuner.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_obi_tuner.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_obi_tuner')
            success = True
        elif action == 'run_auto_tpsl_tuner':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_tpsl_tuner.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_tpsl_tuner.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_tpsl_tuner')
            success = True
        elif action == 'run_auto_adapt':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_adapt_realtime.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_adapt_realtime.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_adapt')
            success = True
        elif action == 'run_ml_predict':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/ml_predict.py')],
                            stdout=open(os.path.join(BASE,'logs/ml_predict.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_ml_predict')
            success = True
        elif action == 'run_ml_predict_online':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/ml_predict_online.py')],
                            stdout=open(os.path.join(BASE,'logs/ml_predict_online.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_ml_predict_online')
            success = True
        elif action == 'run_ml_retrain':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/ml_online_simple.py')],
                            stdout=open(os.path.join(BASE,'logs/ml_online.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_ml_retrain')
            success = True
        elif action == 'run_ml_health_check':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/ml_health_check.py')],
                            stdout=open(os.path.join(BASE,'logs/ml_health_check.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_ml_health_check')
            success = True
        elif action == 'run_auto_evolve':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_evolve.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_evolve.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_evolve')
            success = True
        elif action == 'run_auto_filter':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_filter.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_filter.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_filter')
            success = True
        elif action == 'run_auto_compare':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'core/auto_compare.py')],
                            stdout=open(os.path.join(BASE,'logs/auto_compare.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            _update_state('last_compare')
            success = True
        elif action == 'run_multi_backtest':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'multi_backtest.py')],
                            stdout=open(os.path.join(BASE,'logs/multi_backtest.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            success = True
        elif action == 'run_gate_all_disabled':
            pass  # отключено (только sequential_runner)
        elif action == 'update_active':
            subprocess.run(['python3', os.path.join(BASE,'update_active.py')], cwd=BASE, capture_output=True, timeout=60)
            success = True
        elif action == 'quarantine':
            log_event('quarantine', 'brain', f"карантин: {decision['reason']}")
            success = True

        elif action == 'run_evolution_disabled':
            pass  # отключено (только sequential_runner)
        elif action == 'run_sync_grails':
            subprocess.Popen(['nice','-n','19','python3', os.path.join(BASE,'sync_grails_to_tpsl.py')],
                            stdout=open(os.path.join(BASE,'logs/sync_grails.log'),'a'),
                            stderr=subprocess.STDOUT, start_new_session=True)
            success = True
        elif action == 'run_filter_adjust':
            _adjust_filter_policy()
            success = True
        elif action == 'run_cleanup_trades':
            _cleanup_old_trades()
            success = True
        elif action == 'run_agents':
            import subprocess as _sp
            for agent in ['data_agent','gate_agent','evolve_agent','live_agent','risk_agent','report_agent']:
                path = os.path.join(BASE, 'agents', agent + '.py')
                if os.path.exists(path):
                    if pgrep(agent + '.py'):
                        print(f'  {agent} уже работает, skip')
                        continue
                    _sp.Popen(['python3', path],
                             stdout=open(os.path.join(BASE,'logs',agent+'.log'),'a'),
                             stderr=_sp.STDOUT, start_new_session=True)
            success = True
        elif action == 'stop_bot':
            import subprocess as _sp
            _sp.run(['pkill','-f',decision.get('bot','')], capture_output=True)
            log_event('stop_bot', 'brain', f"остановлен {decision.get('bot')}: {decision.get('reason')}")
            success = True
        elif action == 'kill_heavy':
            # убиваем зависшие gate > 15 мин
            for p in ['run_gate_', 'gate_v3.py']:
                r = subprocess.run(['pgrep','-f',p], capture_output=True, text=True)
                for pid in r.stdout.strip().split('\n'):
                    if pid:
                        try:
                            st = subprocess.run(['ps','-o','etime=','-p',pid], capture_output=True, text=True).stdout.strip()
                            if ':' in st and len(st.split(':')[0]) >= 2:  # > 1 часа
                                subprocess.run(['kill','-9',pid])
                        except: pass
            success = True
    except Exception as e:
        log_event('error', 'executor', f'{action}: {e}')
    duration = time.time() - start
    log_action(action, success, duration)
    log_decision(action, decision['reason'], 'ok' if success else 'fail')

# ═══ HEALTH ═══
def health_check():
    state = get_full_state()
    issues = []
    for name, bot in state.get('bots',{}).items():
        if not bot.get('alive'): issues.append(f'{name}: мёртв')
    if not state.get('data',{}).get('fresh'): issues.append('data: устарели')
    if state.get('system',{}).get('load',0) > 8: issues.append(f"load: {state['system']['load']}")
    if state.get('system',{}).get('mem_free_mb',0) < 50: issues.append('mem: мало')
    return {'healthy': len(issues)==0, 'issues': issues, 'state': state}

if __name__ == '__main__':
    init_db()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'state'
    if cmd == 'health':
        h = health_check()
        print(json.dumps({'healthy':h['healthy'],'issues':h['issues']}, indent=2, ensure_ascii=False))
    elif cmd == 'history':
        print(json.dumps(get_history(), indent=2, ensure_ascii=False)[:5000])
    elif cmd == 'decide':
        s = get_full_state()
        print(json.dumps(decide(s), indent=2, ensure_ascii=False))
    elif cmd == 'execute':
        s = get_full_state()
        for d in decide(s):
            execute(d)
            print(f"executed: {d['action']} — {d['reason']}")
    else:
        s = get_full_state()
        print(json.dumps(s, indent=2, ensure_ascii=False)[:5000])
        print('\n=== DECISIONS ===')
        for d in decide(s): print(f"  [P{d['priority']}] {d['action']}: {d['reason']}")
