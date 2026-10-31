#!/usr/bin/env python3
"""kill_switch.py — выключает стратегии, которые сливают 3 дня подряд."""
import os, json, sqlite3, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/kill_switch.log')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
ACTIVE_V3 = os.path.join(BASE, 'data/okx_active_v3.json')
DBS = {'v2': 'data/okx_paper.db', 'v3': 'data/okx_paper_v3.db', 'v4': 'data/okx_paper_v4.db'}

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def check_strategy(bot, sym, strat, days=3):
    db = os.path.join(BASE, DBS[bot])
    if not os.path.exists(db): return None
    c = sqlite3.connect(db, timeout=10)
    cutoff = int(time.time()) - days*86400
    r = c.execute("""SELECT COUNT(*) n, ROUND(COALESCE(SUM(pnl),0),2) pnl,
                     ROUND(100.0*SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)/MAX(COUNT(*),1),1) wr
                     FROM trades WHERE symbol=? AND strategy=? AND status='CLOSED' AND exit_ts>?""",
                  (sym, strat, cutoff)).fetchone()
    c.close()
    if not r or r[0] < 5: return None
    return {'n': r[0], 'pnl': r[1], 'wr': r[2]}

def main():
    log('=== KILL SWITCH RUN ===')
    killed = []
    for active_file in [ACTIVE, ACTIVE_V3]:
        if not os.path.exists(active_file): continue
        d = json.load(open(active_file))
        pairs = d.get('pairs', {})
        new_pairs = {}
        for key, v in pairs.items():
            sym = v['symbol']; strat = v['strategy']
            # проверяем v2/v3/v4
            bad = False
            for bot in ['v2', 'v3', 'v4']:
                r = check_strategy(bot, sym, strat, days=3)
                if r and r['pnl'] < -5 and r['n'] >= 10:
                    log(f'  💀 KILL {bot} {sym} {strat}: PnL={r["pnl"]}, n={r["n"]}')
                    bad = True
                    break
            if not bad:
                new_pairs[key] = v
            else:
                killed.append((sym, strat))
        if killed:
            d['pairs'] = new_pairs
            d['killed_at'] = datetime.now().isoformat()
            json.dump(d, open(active_file, 'w'), indent=2)
            log(f'  ✅ {active_file}: {len(new_pairs)} пар (убито {len(pairs)-len(new_pairs)})')
    if not killed:
        log('  ✅ нет стратегий для kill')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
