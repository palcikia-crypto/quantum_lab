#!/usr/bin/env python3
"""live_monitor.py — сравнение live vs backtest.
Если live WR < backtest - 5пп на 20+ сделках -> карантин.
Если live WR > backtest -> усилить BET."""
import os, json, sqlite3
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
ACTIVE = os.path.join(BASE, 'data/active_strategies.json')
DB = os.path.join(BASE, 'data/market.db')
OUT = os.path.join(BASE, 'data/live_monitor.json')
RSBOT = os.path.expanduser('~/rsbot')

LIVE_DBS = {
    'pm_bot.db': 'V1', 'pm_v3.db': 'V3', 'pm_v4.db': 'V4',
    'pm_v5.db': 'V5', 'pm_v6.db': 'V6.1', 'pm_v7.db': 'V7',
}

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/live_monitor.log'), 'a') as f: f.write(line+'\n')

def get_live_stats(db_path, strategy):
    if not os.path.exists(db_path): return None
    try:
        c = sqlite3.connect(db_path)
        r = c.execute("""SELECT COUNT(*), SUM(CASE WHEN win_flag=1 THEN 1 ELSE 0 END),
                        ROUND(SUM(pnl),2) FROM trades
                        WHERE strategy=? AND win_flag IS NOT NULL""", (strategy,)).fetchone()
        c.close()
        n = r[0] or 0; wins = r[1] or 0; pnl = r[2] or 0
        wr = 100.0*wins/n if n else 0
        return {'n': n, 'wins': wins, 'wr': round(wr,1), 'pnl': pnl}
    except: return None

def main():
    log('=== LIVE MONITOR START ===')
    if not os.path.exists(ACTIVE):
        log('active_strategies.json нет'); return
    active = json.load(open(ACTIVE))
    pairs = active.get('pairs', {})
    results = []
    for key, cfg in pairs.items():
        strat = cfg.get('strategy'); backtest_wr = cfg.get('wr', 0)
        symbol = cfg.get('symbol')
        # ищем в какой БД торгуется эта пара
        live = None; bot = None
        for db, name in LIVE_DBS.items():
            s = get_live_stats(os.path.join(RSBOT, db), strat)
            if s and s['n'] > 0:
                live = s; bot = name; break
        if not live:
            results.append({'key': key, 'symbol': symbol, 'strategy': strat,
                            'backtest_wr': backtest_wr, 'live_wr': 0, 'n': 0,
                            'status': 'no_live_data'})
            continue
        delta = live['wr'] - backtest_wr
        if live['n'] >= 20 and delta < -5:
            status = 'QUARANTINE'
        elif delta > 2:
            status = 'STRENGTHEN'
        elif live['n'] < 20:
            status = 'waiting'
        else:
            status = 'OK'
        results.append({'key': key, 'symbol': symbol, 'strategy': strat, 'bot': bot,
                        'backtest_wr': backtest_wr, 'live_wr': live['wr'],
                        'delta': round(delta,1), 'n': live['n'], 'pnl': live['pnl'],
                        'status': status})
        log(f"  {symbol} {strat}: bt={backtest_wr}% live={live['wr']}% n={live['n']} -> {status}")
    with open(OUT, 'w') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'results': results}, f, indent=2, ensure_ascii=False)
    summary = {}
    for r in results: summary[r['status']] = summary.get(r['status'], 0) + 1
    log(f'Summary: {summary}')
    log(f'Сохранено: {OUT}')

if __name__ == '__main__':
    main()
