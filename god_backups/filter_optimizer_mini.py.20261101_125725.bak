#!/usr/bin/env python3
"""filter_optimizer_mini.py — мини-тест: 1 пара, 1 стратегия, 1 период."""
import os, sys, json, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_scalp_strategies import SCALP_STRATEGIES

OB_DB = os.path.join(BASE, 'data/orderbook.db')
OUT = os.path.join(BASE, 'data/filter_settings.json')

SYMBOL = 'SOL-USDT'
STRAT_NAME = 'scalp_obi_short'
STRAT_FN = SCALP_STRATEGIES[STRAT_NAME]
PERIOD = 3600  # 1ч

OBI_GRID = [-0.3, -0.4, -0.5]
TPSL_GRID = [(0.0005, 0.0005, 60), (0.001, 0.0005, 60), (0.0015, 0.00075, 60), (0.001, 0.001, 120), (0.0015, 0.001, 120)]
FUNDING_GRID = [0.00005, 0.0001]
PRESSURE_GRID = [0]  # не используется (фильтр: pressure > 0)
SPREAD_GRID = [0.0005, 0.001]

TP, SL, TIMEOUT, FEE = 0.0015, 0.00075, 60, 0.0005

def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)

def load_data(symbol, start_ts, end_ts):
    c = sqlite3.connect(OB_DB, timeout=10)
    obs = c.execute("""SELECT ts, best_bid, best_ask, spread, imbalance
                       FROM orderbooks WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                    (symbol, start_ts, end_ts)).fetchall()
    trades = c.execute("""SELECT ts, side, price, volume FROM trades
                          WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                       (symbol, start_ts, end_ts)).fetchall()
    swap = symbol + '-SWAP'
    fundings = c.execute("""SELECT ts, funding_rate FROM funding
                            WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                         (swap, start_ts-3600, end_ts)).fetchall()
    c.close()
    return obs, trades, fundings

def simulate(obs, trades, fundings, obi_th, fund_th, press_th, spread_max, tp=0.0015, sl=0.00075, timeout=60):
    if not obs: return {'n': 0, 'wins': 0, 'wr': 0, 'pnl': 0}
    trades_by_ts = defaultdict(list)
    for t in trades:
        trades_by_ts[t[0]].append(t)
    funding_by_ts = {f[0]: f[1] for f in fundings}

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
        if spread is None or spread > spread_max: continue
        if obi is None: continue
        if obi > obi_th: continue  # SHORT только если obi < -0.4 (т.е. obi_th = -0.4)
        price = (bid + ask) / 2
        buy = sum(t[3] for t in trades if t[1]=='buy' and ts-60 <= t[0] <= ts)
        sell = sum(t[3] for t in trades if t[1]=='sell' and ts-60 <= t[0] <= ts)
        pressure = buy - sell
        funding = get_funding(ts)
        if funding is not None and funding < fund_th: continue  # SHORT: skip если funding < fund_th (шорты не получают)
        if pressure > 0: continue  # SHORT: skip если pressure > 0 (buy доминирует)

        entry = bid
        tp_p = entry * (1 - tp)
        sl_p = entry * (1 + sl)
        exit_p = None
        for j in range(i + 1, len(obs)):
            o_ts, o_bid, o_ask = obs[j][0], obs[j][1], obs[j][2]
            if o_ts - ts > timeout:
                exit_p = (o_bid + o_ask) / 2
                break
            # Проверяем SL по o_ask (для SHORT — покупка по ask)
            if o_ask >= sl_p: exit_p = sl_p; break
            # Проверяем TP по o_bid (для SHORT — продажа по bid)
            if o_bid <= tp_p: exit_p = tp_p; break
        if exit_p is None: continue
        move = (entry - exit_p) / entry
        pnl = (move - FEE) * 100
        results.append({'pnl': pnl})
        cooldown = ts + timeout

    n = len(results)
    wins = sum(1 for r in results if r['pnl'] > 0)
    pnl = sum(r['pnl'] for r in results)
    return {'n': n, 'wins': wins, 'wr': round(100.0*wins/n, 1) if n else 0, 'pnl': round(pnl, 2)}

def main():
    log('=== MINI FILTER OPTIMIZER ===')
    now = int(time.time())
    start = now - PERIOD
    obs, trades, fundings = load_data(SYMBOL, start, now)
    log(f'Данные: obs={len(obs)}, trades={len(trades)}, fundings={len(fundings)}')

    results = []
    for obi_th in OBI_GRID:
        for fund_th in FUNDING_GRID:
            for press_th in PRESSURE_GRID:
                for spread_max in SPREAD_GRID:
                    for tp, sl, timeout in TPSL_GRID:
                        res = simulate(obs, trades, fundings, obi_th, fund_th, press_th, spread_max, tp, sl, timeout)
                        if res['n'] >= 3 and res['pnl'] > 0:
                            results.append({
                                'symbol': SYMBOL, 'strategy': STRAT_NAME,
                                'obi': obi_th, 'funding': fund_th,
                                'pressure': press_th, 'spread': spread_max,
                                'tp': tp, 'sl': sl, 'timeout': timeout,
                                'n': res['n'], 'wr': res['wr'], 'pnl': res['pnl']
                            })

    results.sort(key=lambda x: -x['pnl'])
    log(f'Найдено: {len(results)}')
    for r in results[:10]:
        log(f"  OBI={r['obi']:.2f} fund={r['funding']:.5f} press={r['pressure']} spread={r['spread']:.4f} → WR={r['wr']:.1f}% PnL={r['pnl']:+.2f}% n={r['n']}")

    # Сохраняем
    out = {
        'updated_at': datetime.now().isoformat(),
        'total_combinations': len(OBI_GRID)*len(FUNDING_GRID)*len(PRESSURE_GRID)*len(SPREAD_GRID),
        'best_count': len(results),
        'settings': results
    }
    json.dump(out, open(OUT, 'w'), indent=2, ensure_ascii=False)
    log(f'✅ filter_settings.json: {len(results)} настроек')

if __name__ == '__main__':
    main()
