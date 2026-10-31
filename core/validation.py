#!/usr/bin/env python3
"""validation.py — расширенные тесты L8-L13: out-of-sample, permutation, PBO, cross-pair, regime."""
import os, sys, json, sqlite3
import numpy as np
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/market.db')
sys.path.insert(0, os.path.join(BASE, 'core'))
from strategy_pool import STRATEGIES
from gate_v3 import load_candles, apply_h1_filter, simulate

def L8_out_of_sample(up, dn, o, c, model='open'):
    """Тест на последних 20% (не было в train)."""
    cut = int(len(c)*0.8)
    te = simulate(up[cut:], dn[cut:], o[cut:], c[cut:], model=model)
    if len(te) < 20: return {'n': len(te), 'pass': False}
    wr = 100*sum(1 for x in te if x>0)/len(te)
    return {'wr': round(wr,1), 'n': len(te), 'pass': wr >= 52}

def L9_permutation(up, dn, o, c, n_iter=200, model='open'):
    """Permutation test: 200 случайных перестановок сигналов."""
    real = simulate(up, dn, o, c, model=model)
    if len(real) < 50: return {'pass': False}
    real_wr = 100*sum(1 for x in real if x>0)/len(real)
    rng = np.random.default_rng(42)
    wrs = []
    for _ in range(n_iter):
        # случайно перемешиваем сигналы
        idx = np.arange(len(c)-2)
        rng.shuffle(idx)
        up_s = np.zeros_like(up); dn_s = np.zeros_like(dn)
        for j, i in enumerate(idx[:sum(up)+sum(dn)]):
            if j < sum(up): up_s[i] = True
            else: dn_s[i] = True
        t = simulate(up_s, dn_s, o, c, model=model)
        if t: wrs.append(100*sum(1 for x in t if x>0)/len(t))
    pval = sum(1 for w in wrs if w >= real_wr) / max(len(wrs),1)
    return {'real_wr': round(real_wr,1), 'pval': round(pval,4), 'pass': pval < 0.05}

def L10_deflated_sharpe(pnls, n_trials=100):
    """Deflated Sharpe: Sharpe с поправкой на множественное тестирование."""
    if len(pnls) < 20: return {'pass': False}
    a = np.array(pnls)
    sr = a.mean()/a.std() if a.std() > 0 else 0
    # поправка: ожидаемый максимум Sharpe из n_trials случайных
    from math import sqrt, log, erf
    e_max = sqrt(2*log(n_trials)) - (log(log(n_trials)) + log(4*3.14))/(2*sqrt(2*log(n_trials)))
    deflated = sr - e_max * (1/sqrt(len(a)))
    return {'sharpe': round(sr,2), 'deflated': round(deflated,2), 'pass': deflated > 0}

def L11_pbo(up, dn, o, c, n_splits=10, model='open'):
    """Probability of Backtest Overfitting: доля сплитов, где test WR < train WR - 3пп."""
    n = len(c); split_size = n // n_splits
    overfit = 0; total = 0
    for i in range(n_splits-1):
        cut = (i+1) * split_size
        tr = simulate(up[:cut], dn[:cut], o[:cut], c[:cut], model=model)
        te = simulate(up[cut:], dn[cut:], o[cut:], c[cut:], model=model)
        if len(tr) < 10 or len(te) < 10: continue
        tr_wr = 100*sum(1 for x in tr if x>0)/len(tr)
        te_wr = 100*sum(1 for x in te if x>0)/len(te)
        if te_wr < tr_wr - 3: overfit += 1
        total += 1
    pbo = overfit/total if total > 0 else 1
    return {'pbo': round(pbo,2), 'pass': pbo < 0.5}

def L12_regime_stability(up, dn, o, c, ts, model='open'):
    """WR в каждом режиме (по месяцам)."""
    from gate_v3 import monthly_stats
    pnls = simulate(up, dn, o, c, model=model)
    entry_ts = [ts[i] for i in range(50, min(len(c)-2, len(c))) if up[i] or dn[i]]
    monthly = monthly_stats(pnls, entry_ts)
    if not monthly: return {'pass': False}
    wrs = [m['wr'] for m in monthly]
    return {'min_wr': min(wrs), 'max_wr': max(wrs), 'months': len(monthly),
            'pass': min(wrs) >= 50 and len(monthly) >= 2}

def L13_cross_pair(strat_name, strat_fn, pairs=('BTCUSDT','ETHUSDT','SOLUSDT'), tf='4h', model='open'):
    """Работает ли стратегия на других парах."""
    wrs = []
    for pair in pairs:
        data = load_candles(pair, tf)
        if not data: continue
        up, dn = strat_fn(data['o'],data['h'],data['l'],data['c'],data['v'],{})
        t = simulate(up, dn, data['o'], data['c'], model=model)
        if len(t) >= 30:
            wrs.append(100*sum(1 for x in t if x>0)/len(t))
    if not wrs: return {'pass': False}
    return {'wrs': [round(w,1) for w in wrs], 'avg': round(sum(wrs)/len(wrs),1), 'pass': sum(wrs)/len(wrs) >= 52}

def run_full(symbol, tf, strat_name, strat_fn, model='open'):
    data = load_candles(symbol, tf)
    if not data: return None
    up, dn = strat_fn(data['o'],data['h'],data['l'],data['c'],data['v'],{})
    up, dn = apply_h1_filter(up, dn, symbol, data['ts'])
    pnls = simulate(up, dn, data['o'], data['c'], model=model)
    if len(pnls) < 50: return None
    return {
        'symbol': symbol, 'tf': tf, 'strategy': strat_name,
        'L8': L8_out_of_sample(up, dn, data['o'], data['c'], model),
        'L9': L9_permutation(up, dn, data['o'], data['c'], 100, model),
        'L10': L10_deflated_sharpe(pnls),
        'L11': L11_pbo(up, dn, data['o'], data['c'], 10, model),
        'L12': L12_regime_stability(up, dn, data['o'], data['c'], data['ts'], model),
        'L13': L13_cross_pair(strat_name, strat_fn, ('BTCUSDT','ETHUSDT','SOLUSDT'), tf, model),
    }

if __name__ == '__main__':
    results = []
    pairs = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT']
    tf_model = {'15m':'current','1h':'open','4h':'open'}
    for pair in pairs:
        for tf, model in tf_model.items():
            for name, fn in STRATEGIES.items():
                try:
                    r = run_full(pair, tf, name, fn, model)
                    if r: results.append(r)
                except: pass
    # оценка: сколько L прошло
    for r in results:
        r['total_pass'] = sum(1 for k in ['L8','L9','L10','L11','L12','L13'] if r[k].get('pass'))
    results.sort(key=lambda x: -x['total_pass'])
    with open(f'{BASE}/data/validation.json','w') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'results': results}, f, indent=2, ensure_ascii=False)
    print('Прогонов: ' + str(len(results)))
    print('=== ТОП-15 (по L8-L13) ===')
    for r in results[:15]:
        print('  ' + r['symbol'].ljust(10) + ' ' + r['tf'].ljust(3) + ' ' + r['strategy'].ljust(15) +
              ' L8-L13: ' + str(r['total_pass']) + '/6')
