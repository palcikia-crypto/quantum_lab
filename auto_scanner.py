#!/usr/bin/env python3
"""auto_scanner.py — автоматический перебор ВСЕХ комбинаций.
Находит лучшие стратегии по PnL (с комиссиями OKX)."""
import os, sys, json, sqlite3
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from strategy_pool import STRATEGIES
from gate_v3 import load_candles, apply_h1_filter, simulate, simulate_okx, sharpe, max_dd

PAIRS = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT','MATICUSDT','ARBUSDT']
TFS = [('5m','current'), ('15m','current'), ('1h','open'), ('4h','open')]
OUT = os.path.join(BASE, 'data/auto_results.json')
LOG = os.path.join(BASE, 'logs/auto_scanner.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')

def check_strategy(symbol, tf, name, fn, model):
    """Полная проверка: L1-L7 + PnL с комиссиями."""
    try:
        data = load_candles(symbol, tf)
        if not data or len(data['c']) < 100: return None
        up, dn = fn(data['o'], data['h'], data['l'], data['c'], data['v'], {})
        up, dn = apply_h1_filter(up, dn, symbol, data['ts'])
        # PnL с комиссиями OKX (taker 0.05% + slippage 0.02%)
        pnls = simulate_okx(up, dn, data['o'], data['c'], model=model, use_maker=False)
        if len(pnls) < 100: return None
        wins = sum(1 for p in pnls if p > 0)
        wr = 100*wins/len(pnls)
        pnl_pct = sum(pnls) * 100
        # L1: WR, n, p
        n = len(pnls)
        from math import sqrt, erf
        se = sqrt(0.25/n); z = (wins/n - 0.5)/se if se > 0 else 0
        pval = 1 - 0.5*(1 + erf(abs(z)/sqrt(2)))
        # Sharpe, max DD
        sh = sharpe(pnls)
        dd = max_dd(pnls)
        # Walk-forward
        cut = int(len(pnls)*0.7)
        tr = pnls[:cut]; te = pnls[cut:]
        if len(tr) >= 10 and len(te) >= 10:
            tr_wr = 100*sum(1 for x in tr if x > 0)/len(tr)
            te_wr = 100*sum(1 for x in te if x > 0)/len(te)
        else:
            tr_wr = te_wr = wr
        # Вердикт
        l1 = wr >= 50 and n >= 100 and pval < 0.05
        l2 = te_wr >= 50 and (tr_wr - te_wr) < 5
        l3 = sh > 0.5
        l4 = dd < 30
        passed = sum([l1, l2, l3, l4])
        verdict = 'GOLDEN' if passed == 4 else ('TRADE_NOW' if passed == 3 else ('WATCH' if passed == 2 else 'SKIP'))
        return {
            'symbol': symbol, 'tf': tf, 'strategy': name, 'model': model,
            'wr': round(wr,1), 'n': n, 'p': round(pval,4), 'pnl_pct': round(pnl_pct,2),
            'sharpe': round(sh,2), 'max_dd': round(dd,1),
            'train_wr': round(tr_wr,1), 'test_wr': round(te_wr,1),
            'passed': passed, 'verdict': verdict
        }
    except Exception as e:
        return None

def main():
    log('=== AUTO SCANNER START ===')
    results = []
    total = len(PAIRS) * len(TFS) * len(STRATEGIES)
    done = 0
    for pair in PAIRS:
        for tf, model in TFS:
            for name, fn in STRATEGIES.items():
                done += 1
                if done % 100 == 0: log(f'прогресс: {done}/{total}')
                r = check_strategy(pair, tf, name, fn, model)
                if r: results.append(r)
    # Сортируем по PnL
    results.sort(key=lambda x: -x['pnl_pct'])
    # Сохраняем
    with open(OUT, 'w') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'total': len(results), 'results': results}, f, indent=2, ensure_ascii=False)
    log(f'ГОТОВО: {len(results)} прогонов')
    log('=== ТОП-20 по PnL ===')
    for r in results[:20]:
        log(f"  {r['symbol']:10} {r['tf']:3} {r['strategy']:15} {r['verdict']:10} WR={r['wr']}% n={r['n']} PnL={r['pnl_pct']}% Sharpe={r['sharpe']}")

if __name__ == '__main__': main()
