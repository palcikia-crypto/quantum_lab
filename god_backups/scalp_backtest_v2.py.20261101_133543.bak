#!/usr/bin/env python3
"""scalp_backtest_v2.py — глубокий бэктест скальпинга по периодам."""
import os, sys, json, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from scalp_strategies_v2 import SCALP_STRATEGIES_V2

DB = os.path.join(BASE, 'data/orderbook.db')
OUT = os.path.join(BASE, 'data/scalp_graals_v2')

# Периоды
PERIODS = [
    ('1h', 3600),
    ('6h', 6*3600),
    ('24h', 24*3600),
    ('7d', 7*86400),
]

# Варианты TP/SL
TPSL_VARIANTS = [
    (0.001, 0.0005, 60),   # 0.1% / 0.05% / 60s
    (0.0015, 0.00075, 60), # 0.15% / 0.075% / 60s
    (0.0005, 0.0005, 30),  # 0.05% / 0.05% / 30s (1:1)
]

FEE = 0.0005

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
    vwaps = q("SELECT ts, vwap_1m FROM vwap WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
              (symbol, start_ts, end_ts))
    # funding (SWAP)
    swap = symbol + '-SWAP'
    fundings = q("SELECT ts, funding_rate FROM funding WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
                 (swap, start_ts - 3600, end_ts))
    return obs, trades, vwaps, fundings

def simulate(strat_fn, obs, trades, vwaps, fundings, tp, sl, timeout, start_ts):
    if not obs: return {'n': 0, 'wins': 0, 'wr': 0, 'pnl': 0}

    trades_by_ts = defaultdict(list)
    for t in trades:
        trades_by_ts[t[0]].append(t)
    vwap_by_ts = {v[0]: v[1] for v in vwaps}
    # funding: последний перед ts
    funding_by_ts = {}
    for f in fundings:
        funding_by_ts[f[0]] = f[1]

    def get_funding(ts):
        prev = None
        for fts in sorted(funding_by_ts):
            if fts <= ts: prev = funding_by_ts[fts]
            else: break
        return prev

    results = []
    cooldown = 0

    for i, ob in enumerate(obs):
        ts, bid, ask, spread, obi = ob
        if ts < cooldown: continue
        price = (bid + ask) / 2
        vwap = vwap_by_ts.get(ts, 0)
        # pressure
        buy = sum(t[3] for t in trades if t[1]=='buy' and ts-60 <= t[0] <= ts)
        sell = sum(t[3] for t in trades if t[1]=='sell' and ts-60 <= t[0] <= ts)
        pressure = buy - sell
        funding = get_funding(ts)

        side = strat_fn(obi, pressure, spread, price, vwap, funding)
        if not side: continue

        entry = ask if side == 'LONG' else bid
        tp_p = entry * (1 + tp) if side == 'LONG' else entry * (1 - tp)
        sl_p = entry * (1 - sl) if side == 'LONG' else entry * (1 + sl)

        exit_p = None
        for j in range(i + 1, len(obs)):
            o_ts = obs[j][0]
            if o_ts - ts > timeout:
                exit_p = (obs[j][1] + obs[j][2]) / 2
                break
            for t in trades_by_ts.get(o_ts, []):
                p = t[2]
                if side == 'LONG':
                    if p <= sl_p: exit_p = sl_p; break
                    if p >= tp_p: exit_p = tp_p; break
                else:
                    if p >= sl_p: exit_p = sl_p; break
                    if p <= tp_p: exit_p = tp_p; break
            if exit_p is not None: break

        if exit_p is None: continue

        move = (exit_p - entry) / entry if side == 'LONG' else (entry - exit_p) / entry
        pnl = (move - FEE) * 100

        results.append({'ts': ts, 'side': side, 'pnl': round(pnl, 4)})
        cooldown = ts + timeout

    n = len(results)
    wins = sum(1 for r in results if r['pnl'] > 0)
    pnl_sum = sum(r['pnl'] for r in results)
    wr = round(100.0 * wins / n, 1) if n > 0 else 0
    return {'n': n, 'wins': wins, 'wr': wr, 'pnl': round(pnl_sum, 2)}

def main():
    print(f'=== SCALP BACKTEST v2 {datetime.now():%Y-%m-%d %H:%M:%S} ===')
    now = int(time.time())
    pairs = get_pairs()
    print(f'Пар: {len(pairs)}')

    all_results = {}
    for p_name, p_sec in PERIODS:
        start = now - p_sec
        print(f'\n--- Период: {p_name} ({p_sec}s) ---')
        for symbol in pairs:
            obs, trades, vwaps, fundings = load_pair(symbol, start, now)
            if not obs: continue
            for strat_name, strat_fn in SCALP_STRATEGIES_V2.items():
                for tp, sl, timeout in TPSL_VARIANTS:
                    key = (p_name, symbol, strat_name, tp, sl, timeout)
                    res = simulate(strat_fn, obs, trades, vwaps, fundings, tp, sl, timeout, start)
                    if res['n'] >= 5:
                        all_results[key] = res

    # Фильтр устойчивости: в плюсе на ВСЕХ периодах, WR>=55%, n>=5
    print('\n=== ПОИСК УСТОЙЧИВЫХ ===')
    stable = []
    for (p_name, sym, strat, tp, sl, timeout), res in all_results.items():
        pass  # группируем по (sym, strat, tp, sl, timeout)

    # Группировка
    grouped = defaultdict(dict)
    for (p_name, sym, strat, tp, sl, timeout), res in all_results.items():
        grouped[(sym, strat, tp, sl, timeout)][p_name] = res

    for key, periods in grouped.items():
        if len(periods) < 2: continue  # нужно минимум 2 периода
        if all(r['pnl'] > 0 and r['wr'] >= 55 for r in periods.values()):
            total_pnl = sum(r['pnl'] for r in periods.values())
            total_n = sum(r['n'] for r in periods.values())
            avg_wr = sum(r['wr'] for r in periods.values()) / len(periods)
            stable.append({
                'symbol': key[0], 'strategy': key[1],
                'tp': key[2], 'sl': key[3], 'timeout': key[4],
                'periods': len(periods), 'total_n': total_n,
                'avg_wr': round(avg_wr, 1), 'total_pnl': round(total_pnl, 2),
            })

    stable.sort(key=lambda x: -x['total_pnl'])
    print(f'Устойчивых: {len(stable)}')
    for s in stable[:20]:
        print(f"  {s['symbol']:12s} {s['strategy']:22s} TP={s['tp']*100:.2f}% SL={s['sl']*100:.2f}% "
              f"n={s['total_n']:4d} WR={s['avg_wr']:5.1f}% PnL={s['total_pnl']:+.2f}%")

    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(OUT, f'scalp_v2_{stamp}.json')
    out = {
        'updated_at': datetime.now().isoformat(),
        'periods': [p[0] for p in PERIODS],
        'tpsl_variants': [{'tp': t[0], 'sl': t[1], 'timeout': t[2]} for t in TPSL_VARIANTS],
        'total_combinations': len(all_results),
        'stable_count': len(stable),
        'stable': stable,
    }
    json.dump(out, open(out_file, 'w'), indent=2, ensure_ascii=False)
    print(f'\n✅ Записано: {out_file}')

if __name__ == '__main__':
    main()
