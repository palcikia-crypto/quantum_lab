#!/usr/bin/env python3
"""holy_grail.py — ищет "грааль": стратегии с устойчивым положительным expectancy
на 3 walk-forward окнах. Берёт кандидатов из active_strategies.json и okx_tpsl_by_regime.json,
проверяет на market.db. Пишет data/holy_grail.json."""
import os, sys, json, sqlite3, time
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE,'core'))
from strategy_pool import STRATEGIES as _POOL
try:
    from okx_mutator import generate_mutants
    STRATEGIES = {**_POOL, **generate_mutants()}
except Exception:
    STRATEGIES = _POOL

MARKET_DB = os.path.join(BASE, 'data/market.db')
ACTIVE = os.path.join(BASE, 'data/active_strategies.json')
OUT = os.path.join(BASE, 'data/holy_grail.json')

FEE = 0.0015
MIN_EXPECTANCY = 0.0003   # 0.03% на сделку
MIN_N = 20
MAX_DD = 30.0
MIN_SHARPE = 0.5
# Walk-forward: (train_start_frac, test_start_frac) — оба с конца
# Например (0.5, 0.75) = train на [50%:75%], test на [75%:100%]
WINDOWS = [
    (0.50, 0.75),  # train 50-75%, test 75-100%
    (0.25, 0.50),  # train 25-50%, test 50-75%
    (0.00, 0.25),  # train 0-25%,  test 25-50%
]


def load_candles(symbol, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? ORDER BY ts", (symbol, tf)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}


def simulate(up, dn, o, c, start=50):
    trades = []; hi = len(c)-2
    for i in range(start, hi):
        if up[i]:
            entry=o[i+1]; exit_p=c[i+2]
            trades.append((exit_p-entry)/entry - FEE)
        elif dn[i]:
            entry=o[i+1]; exit_p=c[i+2]
            trades.append((entry-exit_p)/entry - FEE)
    return trades


def sharpe(pnls):
    if len(pnls)<2: return 0.0
    a=np.array(pnls); s=a.std()
    return float(a.mean()/s*np.sqrt(252)) if s>0 else 0.0


def max_dd(pnls):
    if not pnls: return 0.0
    cum=np.cumsum(pnls); peak=np.maximum.accumulate(cum)
    denom=max(abs(peak.max()),1e-9)
    return float(abs((cum-peak).min())/denom*100)


def evaluate_window(data, up, dn, lo, hi):
    """Симулирует на срезе [lo:hi]. Возвращает метрики."""
    o=data['o'][lo:hi]; c=data['c'][lo:hi]
    if len(c) < 60: return None
    # Сигналы тоже обрезаем, но в пределах окна индексы совпадают
    u = up[lo:hi]; d = dn[lo:hi]
    pnls = simulate(u, d, o, c)
    if len(pnls) < 10: return None
    n=len(pnls); wins=sum(1 for p in pnls if p>0)
    return {
        'n': n, 'wr': round(100*wins/n, 1),
        'expectancy': round(sum(pnls)/n, 5),
        'sharpe': round(sharpe(pnls), 2),
        'max_dd': round(max_dd(pnls), 2),
    }


def check_candidate(pair, tf, name, fn):
    data = load_candles(pair, tf)
    if not data or len(data['c']) < 200: return None
    try:
        up, dn = fn(data['o'], data['h'], data['l'], data['c'], data['v'], {})
    except Exception:
        return None
    n_total = len(data['c'])
    results = []
    for train_start, test_start in WINDOWS:
        # train на [train_start:test_start], test на [test_start:test_start+(test_start-train_start)]
        tr_lo = int(n_total * train_start)
        tr_hi = int(n_total * test_start)
        te_lo = tr_hi
        te_hi = min(te_lo + (tr_hi - tr_lo), n_total)
        if te_hi - te_lo < 100: return None
        # Оцениваем на TEST-окне (out-of-sample)
        r = evaluate_window(data, up, dn, te_lo, te_hi)
        if r is None: return None
        results.append({'window': f'test_{int(test_start*100)}-{int(te_hi/n_total*100)}%', **r})
    # Все 3 окна должны пройти
    ok_all = all(
        w['expectancy'] >= MIN_EXPECTANCY and w['n'] >= MIN_N
        and w['max_dd'] <= MAX_DD and w['sharpe'] >= MIN_SHARPE
        for w in results
    )
    exp_avg = sum(w['expectancy'] for w in results) / len(results)
    sh_avg = sum(w['sharpe'] for w in results) / len(results)
    return {
        'pair': pair, 'tf': tf, 'strategy': name,
        'expectancy_avg': round(exp_avg, 5),
        'sharpe_avg': round(sh_avg, 2),
        'max_dd_max': max(w['max_dd'] for w in results),
        'is_grail': ok_all,
        'windows': results,
    }


def main():
    try:
        load = float(open('/proc/loadavg').read().split()[0])
    except Exception:
        load = 0
    if load > 6:
        print(f'load {load:.1f} > 6, пропуск'); return
    # Кандидаты: из active_strategies и okx_tpsl_by_regime
    candidates = []
    if os.path.exists(ACTIVE):
        d = json.load(open(ACTIVE))
        for k, v in d.get('pairs', {}).items():
            if v.get('verdict') in ('GOLDEN','TRADE_NOW','WATCH'):
                candidates.append((v['symbol'], v['tf'], v['strategy']))
    tpsl_reg = os.path.join(BASE,'data/okx_tpsl_by_regime.json')
    if os.path.exists(tpsl_reg):
        d = json.load(open(tpsl_reg))
        for pair, regs in d.get('per_pair', {}).items():
            sym = pair.replace('-','')
            for reg, b in regs.items():
                candidates.append((sym, '15m', b['strategy']))
    # Дедуп
    seen = set(); uniq = []
    for c in candidates:
        if c not in seen:
            uniq.append(c); seen.add(c)
    print(f'Кандидатов: {len(uniq)}')
    results = []
    for i, (pair, tf, name) in enumerate(uniq, 1):
        if name not in STRATEGIES:
            continue
        r = check_candidate(pair, tf, name, STRATEGIES[name])
        if r:
            mark = '🏆' if r['is_grail'] else '  '
            print(f'{mark} [{i}/{len(uniq)}] {pair:10s} {name:25s} exp={r["expectancy_avg"]:+.4f} '
                  f'sh={r["sharpe_avg"]:+.2f} dd={r["max_dd_max"]:5.1f}% grail={r["is_grail"]}')
            if r['is_grail']:
                results.append(r)
    results.sort(key=lambda x: -x['expectancy_avg'])
    out = {
        'updated_at': datetime.now().isoformat(),
        'params': {'min_expectancy':MIN_EXPECTANCY,'min_n':MIN_N,'max_dd':MAX_DD,'min_sharpe':MIN_SHARPE},
        'candidates_total': len(uniq),
        'grails_found': len(results),
        'grails': results[:20],
    }
    json.dump(out, open(OUT,'w'), indent=2, ensure_ascii=False)
    print(f'\n✅ Записано {OUT}: {len(results)} граалей')


if __name__ == '__main__':
    main()
