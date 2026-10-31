#!/usr/bin/env python3
"""scalp_backtest_fast.py — быстрый бэктест: только OBI SHORT."""
import os, sys, json, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from scalp_strategies_v2 import SCALP_STRATEGIES_V2

DB = os.path.join(BASE, 'data/orderbook.db')
OUT = os.path.join(BASE, 'data/scalp_graals_v2')

PERIODS = [('1h', 3600), ('6h', 6*3600), ('24h', 24*3600)]
TPSL = [(0.0015, 0.00075, 60), (0.001, 0.0005, 60)]
FEE = 0.0005

# Только OBI SHORT стратегии
STRATS = {k: v for k, v in SCALP_STRATEGIES_V2.items() if 'obi_short' in k}

def q(sql, args=()):
    try:
        c = sqlite3.connect(DB, timeout=10)
        rows = c.execute(sql, args).fetchall()
        c.close()
        return rows
    except:
        return []

def get_pairs():
    return [r[0] for r in q("SELECT DISTINCT symbol FROM orderbooks ORDER BY symbol")]

def load_pair(symbol, start_ts, end_ts):
    obs = q("SELECT ts, best_bid, best_ask, spread, imbalance FROM orderbooks WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
            (symbol, start_ts, end_ts))
    trades = q("SELECT ts, side, price, volume FROM trades WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
               (symbol, start_ts, end_ts))
    return obs, trades

def simulate(strat_fn, obs, trades, tp, sl, timeout):
    if not obs: return {'n': 0, 'wins': 0, 'wr': 0, 'pnl': 0}
    trades_by_ts = defaultdict(list)
    for t in trades:
        trades_by_ts[t[0]].append(t)
    results = []
    cooldown = 0
    for i, ob in enumerate(obs):
        ts, bid, ask, spread, obi = ob
        if ts < cooldown: continue
        price = (bid + ask) / 2
        # pressure
        buy = sum(t[3] for t in trades if t[1]=='buy' and ts-60 <= t[0] <= ts)
        sell = sum(t[3] for t in trades if t[1]=='sell' and ts-60 <= t[0] <= ts)
        pressure = buy - sell
        side = strat_fn(obi, pressure, spread, price, 0, None)
        if not side: continue
        entry = bid if side == 'SHORT' else ask
        tp_p = entry * (1 - tp) if side == 'SHORT' else entry * (1 + tp)
        sl_p = entry * (1 + sl) if side == 'SHORT' else entry * (1 - sl)
        exit_p = None
        for j in range(i + 1, len(obs)):
            o_ts = obs[j][0]
            if o_ts - ts > timeout:
                exit_p = (obs[j][1] + obs[j][2]) / 2
                break
            for t in trades_by_ts.get(o_ts, []):
                p = t[2]
                if side == 'SHORT':
                    if p >= sl_p: exit_p = sl_p; break
                    if p <= tp_p: exit_p = tp_p; break
            if exit_p is not None: break
        if exit_p is None: continue
        move = (entry - exit_p) / entry if side == 'SHORT' else (exit_p - entry) / entry
        pnl = (move - FEE) * 100
        results.append({'pnl': round(pnl, 4)})
        cooldown = ts + timeout
    n = len(results)
    wins = sum(1 for r in results if r['pnl'] > 0)
    pnl_sum = sum(r['pnl'] for r in results)
    wr = round(100.0 * wins / n, 1) if n > 0 else 0
    return {'n': n, 'wins': wins, 'wr': wr, 'pnl': round(pnl_sum, 2)}

def main():
    print(f'=== FAST SCALP BACKTEST (OBI SHORT) {datetime.now():%Y-%m-%d %H:%M:%S} ===')
    now = int(time.time())
    pairs = get_pairs()
    print(f'Пар: {len(pairs)}, стратегий: {len(STRATS)}')

    all_results = {}
    for p_name, p_sec in PERIODS:
        start = now - p_sec
        for symbol in pairs:
            obs, trades = load_pair(symbol, start, now)
            if not obs: continue
            for strat_name, strat_fn in STRATS.items():
                for tp, sl, timeout in TPSL:
                    key = (p_name, symbol, strat_name, tp, sl)
                    res = simulate(strat_fn, obs, trades, tp, sl, timeout)
                    if res['n'] >= 3:
                        all_results[key] = res

    grouped = defaultdict(dict)
    for (p_name, sym, strat, tp, sl), res in all_results.items():
        grouped[(sym, strat, tp, sl)][p_name] = res

    stable = []
    for key, periods in grouped.items():
        if len(periods) < 2: continue
        if all(r['pnl'] > 0 for r in periods.values()):
            total_pnl = sum(r['pnl'] for r in periods.values())
            total_n = sum(r['n'] for r in periods.values())
            avg_wr = sum(r['wr'] for r in periods.values()) / len(periods)
            stable.append({'symbol': key[0], 'strategy': key[1],
                          'tp': key[2], 'sl': key[3],
                          'periods': len(periods), 'total_n': total_n,
                          'avg_wr': round(avg_wr, 1), 'total_pnl': round(total_pnl, 2)})

    stable.sort(key=lambda x: -x['total_pnl'])
    print(f'\nУстойчивых (в плюсе на {len(PERIODS)} периодах): {len(stable)}')
    for s in stable[:15]:
        print(f"  {s['symbol']:12s} {s['strategy']:20s} TP={s['tp']*100:.2f}% SL={s['sl']*100:.2f}% "
              f"n={s['total_n']:3d} WR={s['avg_wr']:5.1f}% PnL={s['total_pnl']:+.2f}%")

    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(OUT, f'scalp_fast_{stamp}.json')
    json.dump({'updated_at': datetime.now().isoformat(),
               'stable_count': len(stable), 'stable': stable},
              open(out_file, 'w'), indent=2, ensure_ascii=False)
    print(f'\n✅ Записано: {out_file}')

if __name__ == '__main__':
    main()
