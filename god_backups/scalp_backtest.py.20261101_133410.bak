#!/usr/bin/env python3
"""scalp_backtest.py — бэктест скальпинг-стратегий по orderbook.db (тики, не свечи)."""
import os, sys, json, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_scalp_strategies import SCALP_STRATEGIES

DB = os.path.join(BASE, 'data/orderbook.db')
OUT = os.path.join(BASE, 'data/scalp_graals')

# Параметры
TP = 0.001        # 0.1%
SL = 0.0005       # 0.05%
TIMEOUT = 60      # 60 сек
FEE = 0.0005      # 0.05% taker (на вход + выход = 0.1%)
MIN_N = 3         # минимум сделок (мало данных)
MIN_WR = 50.0     # минимальный WR

def q(sql, args=()):
    try:
        c = sqlite3.connect(DB, timeout=10)
        rows = c.execute(sql, args).fetchall()
        c.close()
        return rows
    except Exception as e:
        print(f'⚠️ q error: {e}')
        return []

def get_pairs():
    rows = q("SELECT DISTINCT symbol FROM orderbooks ORDER BY symbol")
    return [r[0] for r in rows]

def load_pair(symbol):
    """Загружает для пары: orderbooks, trades, vwap, выровненные по ts."""
    obs = q("""SELECT ts, best_bid, best_ask, spread, imbalance
               FROM orderbooks WHERE symbol=? ORDER BY ts""", (symbol,))
    trades = q("""SELECT ts, side, price, volume FROM trades
                  WHERE symbol=? ORDER BY ts""", (symbol,))
    vwaps = q("""SELECT ts, vwap_1m FROM vwap WHERE symbol=? ORDER BY ts""", (symbol,))
    return obs, trades, vwaps

def simulate(symbol, strat_name, strat_fn, obs, trades, vwaps):
    """Симуляция одной стратегии на одной паре."""
    if not obs or not trades:
        return {'n': 0, 'wins': 0, 'wr': 0, 'pnl': 0, 'trades': []}

    # Индексы для быстрого поиска
    trades_by_ts = defaultdict(list)
    for t in trades:
        trades_by_ts[t[0]].append(t)

    vwap_by_ts = {v[0]: v[1] for v in vwaps}

    # Pressure: buy_vol - sell_vol за 60 сек назад от ts
    def get_pressure(ts):
        buy = sum(t[3] for t in trades if t[1] == 'buy' and ts - 60 <= t[0] <= ts)
        sell = sum(t[3] for t in trades if t[1] == 'sell' and ts - 60 <= t[0] <= ts)
        return buy - sell

    results = []
    cooldown_until = 0

    for i, ob in enumerate(obs):
        ts, best_bid, best_ask, spread, obi = ob
        if ts < cooldown_until:
            continue
        price = (best_bid + best_ask) / 2
        vwap_1m = vwap_by_ts.get(ts, 0)
        pressure = get_pressure(ts)

        side = strat_fn(obi, pressure, spread, price, vwap_1m)
        if not side:
            continue

        # Вход
        entry = best_ask if side == 'LONG' else best_bid
        tp_p = entry * (1 + TP) if side == 'LONG' else entry * (1 - TP)
        sl_p = entry * (1 - SL) if side == 'LONG' else entry * (1 + SL)

        # Ищем выход по тикам в течение TIMEOUT
        exit_p = None
        exit_ts = None
        for j in range(i + 1, len(obs)):
            o_ts = obs[j][0]
            if o_ts - ts > TIMEOUT:
                # timeout — выход по текущей цене
                exit_p = (obs[j][1] + obs[j][2]) / 2
                exit_ts = o_ts
                break
            # Проверяем тики за этот ts
            for t in trades_by_ts.get(o_ts, []):
                t_price = t[2]
                if side == 'LONG':
                    if t_price <= sl_p:
                        exit_p = sl_p; exit_ts = o_ts; break
                    if t_price >= tp_p:
                        exit_p = tp_p; exit_ts = o_ts; break
                else:
                    if t_price >= sl_p:
                        exit_p = sl_p; exit_ts = o_ts; break
                    if t_price <= tp_p:
                        exit_p = tp_p; exit_ts = o_ts; break
            if exit_p is not None:
                break

        if exit_p is None:
            # не закрылось — пропускаем (не хватает данных)
            continue

        # PnL
        move = (exit_p - entry) / entry if side == 'LONG' else (entry - exit_p) / entry
        pnl = (move - FEE) * 100  # в %

        results.append({
            'ts': ts, 'side': side, 'entry': entry, 'exit': exit_p,
            'pnl': round(pnl, 4), 'reason': 'TP' if pnl > 0 else 'SL',
        })
        cooldown_until = ts + TIMEOUT  # антидубль

    n = len(results)
    wins = sum(1 for r in results if r['pnl'] > 0)
    pnl_sum = sum(r['pnl'] for r in results)
    wr = round(100.0 * wins / n, 1) if n > 0 else 0

    return {'n': n, 'wins': wins, 'wr': wr, 'pnl': round(pnl_sum, 2), 'trades': results[-5:]}

def main():
    print(f'=== SCALP BACKTEST {datetime.now():%Y-%m-%d %H:%M:%S} ===')
    pairs = get_pairs()
    print(f'Пар: {len(pairs)}: {pairs}')

    all_results = {}
    for symbol in pairs:
        obs, trades, vwaps = load_pair(symbol)
        if not obs:
            print(f'  {symbol}: нет данных в orderbooks')
            continue
        print(f'  {symbol}: obs={len(obs)}, trades={len(trades)}, vwaps={len(vwaps)}')

        for strat_name, strat_fn in SCALP_STRATEGIES.items():
            res = simulate(symbol, strat_name, strat_fn, obs, trades, vwaps)
            all_results[(symbol, strat_name)] = res

    # Сводка
    print()
    print('=== РЕЗУЛЬТАТЫ ===')
    stable = []
    for (sym, strat), res in all_results.items():
        if res['n'] >= MIN_N and res['wr'] >= MIN_WR and res['pnl'] > 0:
            stable.append({'symbol': sym, 'strategy': strat,
                           'n': res['n'], 'wr': res['wr'], 'pnl': res['pnl']})

    stable.sort(key=lambda x: -x['pnl'])
    print(f'Устойчивых: {len(stable)}')
    for s in stable[:15]:
        print(f"  {s['symbol']:12s} {s['strategy']:22s} n={s['n']:3d} WR={s['wr']:5.1f}% PnL={s['pnl']:+.2f}%")

    # Сохраняем
    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(OUT, f'scalp_report_{stamp}.json')
    out = {
        'updated_at': datetime.now().isoformat(),
        'params': {'tp': TP, 'sl': SL, 'timeout': TIMEOUT, 'fee': FEE},
        'stable_count': len(stable),
        'stable': stable,
        'all': {f'{k[0]}|{k[1]}': v for k, v in all_results.items()},
    }
    json.dump(out, open(out_file, 'w'), indent=2, ensure_ascii=False)
    print(f'✅ Записано: {out_file}')

if __name__ == '__main__':
    main()
