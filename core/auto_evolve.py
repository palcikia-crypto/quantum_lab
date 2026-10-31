#!/usr/bin/env python3
"""auto_evolve.py — саморазвитие стратегий: генерация, тест, устойчивость, обновление."""
import os, sys, json, sqlite3, time
from collections import defaultdict
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from okx_mutator import generate_mutants
from strategy_mutations import generate_mutations

MARKET_DB = os.path.join(BASE, 'data/market.db')
OUT = os.path.join(BASE, 'data/holy_grail.json')
GRAALS_DIR = os.path.join(BASE, 'data/graals')
BY_REGIME = os.path.join(BASE, 'data/okx_tpsl_by_regime.json')
STATE = os.path.join(BASE, 'data/auto_state.json')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
PERIODS = [('2d', 2*86400), ('7d', 7*86400), ('30d', 30*86400)]
TP, SL, TIMEOUT, FEE = 0.006, 0.004, 2, 0.0015
MIN_N = 5
MIN_PNL = 0.1
MIN_WR = 55.0

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/auto_evolve.log'), 'a') as f:
        f.write(line + '\n')

def load_candles(sym, start_ts, end_ts, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? AND ts>=? AND ts<? ORDER BY ts",
                     (sym, tf, start_ts, end_ts)).fetchall()
    c.close()
    if not rows: return None
    import numpy as np
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def sim_trades(up, dn, o, h, l, c, ts, tp=TP, sl=SL, timeout=TIMEOUT, start=50):
    trades = []
    n = len(c)
    if n < start+2: return trades
    i = start; last_i = -1
    while i < n - 1:
        if i <= last_i: i += 1; continue
        side = None
        if up[i]: side = 'LONG'
        elif dn[i]: side = 'SHORT'
        if not side: i += 1; continue
        entry = c[i]
        tp_p = entry*(1+tp) if side=='LONG' else entry*(1-tp)
        sl_p = entry*(1-sl) if side=='LONG' else entry*(1+sl)
        end = min(i+1+timeout, n); exit_p = None
        for j in range(i+1, end):
            if side == 'LONG':
                if l[j] <= sl_p: exit_p = sl_p; break
                if h[j] >= tp_p: exit_p = tp_p; break
            else:
                if h[j] >= sl_p: exit_p = sl_p; break
                if l[j] <= tp_p: exit_p = tp_p; break
        if exit_p is None:
            jj = min(i+timeout, n-1); exit_p = c[jj]; last_i = jj
        else:
            last_i = i
        move = (exit_p - entry)/entry if side=='LONG' else (entry - exit_p)/entry
        pnl = (move - FEE) * 100
        trades.append({'pnl': float(pnl)})
        i += 1
    return trades

def main():
    log('=== AUTO EVOLVE START ===')
    muts = generate_mutants()
    mutations = generate_mutations()
    # Объединяем: базовые + мутанты
    all_muts = dict(muts)
    for name, fn in mutations.items():
        if name not in all_muts:
            all_muts[name] = fn
    muts = all_muts
    log(f'Стратегий: базовых {len(generate_mutants())}, мутантов {len(mutations)}, всего {len(muts)}')
    now = int(time.time())

    all_res = defaultdict(dict)
    for p_name, p_sec in PERIODS:
        start_ts = now - p_sec
        for sym in PAIRS:
            data = load_candles(sym, start_ts, now)
            if not data: continue
            for strat_name, strat_fn in muts.items():
                try:
                    up, dn = strat_fn(data['o'], data['h'], data['l'], data['c'], data['v'], {})
                except:
                    continue
                trades = sim_trades(up, dn, data['o'], data['h'], data['l'], data['c'], data['ts'])
                if not trades: continue
                n = len(trades)
                wins = sum(1 for t in trades if t['pnl'] > 0)
                pnl = sum(t['pnl'] for t in trades)
                wr = 100*wins/n if n else 0
                all_res[(sym, strat_name)][p_name] = {'n': n, 'wr': wr, 'pnl': pnl}

    stable = []
    for (sym, strat), periods in all_res.items():
        if len(periods) < 3: continue
        if all(r['n'] >= MIN_N and r['pnl'] >= MIN_PNL and r['wr'] >= MIN_WR for r in periods.values()):
            min_pnl = min(r['pnl'] for r in periods.values())
            stable.append({'sym': sym, 'strat': strat, 'min_pnl': min_pnl,
                          'avg_wr': sum(r['wr'] for r in periods.values())/3})

    stable.sort(key=lambda x: -x['min_pnl'])
    log(f'Устойчивых: {len(stable)}')

    # Сохраняем holy_grail
    out = {
        'updated_at': datetime.now().isoformat(),
        'source': 'auto_evolve',
        'stable_count': len(stable),
        'stable': stable[:50],
    }
    json.dump(out, open(OUT, 'w'), indent=2, ensure_ascii=False)
    log(f'✅ holy_grail: {len(stable)} устойчивых')

    # Копия в graals
    os.makedirs(GRAALS_DIR, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json.dump(out, open(os.path.join(GRAALS_DIR, f'auto_{stamp}.json'), 'w'), indent=2, ensure_ascii=False)

    # Автообновление by_regime (ТОЛЬКО если source != manual_optimize)
    try:
        cur = json.load(open(BY_REGIME))
        if cur.get('source') == 'manual_optimize':
            log('⏸️ by_regime = manual_optimize — не трогаем')
        else:
            # Обновляем: ТОП-1 на пару
            by_pair = defaultdict(list)
            for s in stable:
                by_pair[s['sym']].append(s)
            new_pp = {}
            for sym, items in by_pair.items():
                items.sort(key=lambda x: -x['min_pnl'])
                top = items[0]
                sym_dash = sym[:-4] + '-USDT'
                new_pp[sym_dash] = {
                    reg: {'strategy': top['strat'], 'tp': TP, 'sl': SL, 'timeout_bars': TIMEOUT}
                    for reg in ['flat', 'trend_up', 'trend_down']
                }
            cur['per_pair'] = new_pp
            cur['source'] = 'auto_evolve'
            cur['updated_at'] = datetime.now().isoformat()
            json.dump(cur, open(BY_REGIME, 'w'), indent=2, ensure_ascii=False)
            log(f'✅ by_regime обновлён: {len(new_pp)} пар')
    except Exception as e:
        log(f'⚠️ by_regime: {e}')

    log('=== AUTO EVOLVE DONE ===')

if __name__ == '__main__':
    main()
