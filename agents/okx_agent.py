#!/usr/bin/env python3
"""okx_agent.py — тестирует стратегии для OKX (с учётом комиссий)."""
import os, sys, json
sys.path.insert(0, os.path.expanduser('~/quantum_lab/core'))
from strategy_pool import STRATEGIES
from gate_v3 import load_candles, apply_h1_filter, simulate_okx
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
REPORT = os.path.join(BASE, 'data/okx_report.json')
LOG = os.path.join(BASE, 'logs/okx_agent.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')

def main():
    log('=== OKX AGENT ===')
    pairs = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT']
    tfs = [('5m','current'), ('15m','current')]
    results = []
    for pair in pairs:
        for tf, model in tfs:
            for name in ['vwap_ema_scalp', 'pump_dump', 'stoch_20', 'stoch_30', 'mean_rev_3']:
                if name not in STRATEGIES: continue
                try:
                    data = load_candles(pair, tf)
                    if not data: continue
                    up, dn = STRATEGIES[name](data['o'],data['h'],data['l'],data['c'],data['v'],{})
                    up, dn = apply_h1_filter(up, dn, pair, data['ts'])
                    pnls = simulate_okx(up, dn, data['o'], data['c'], model=model)
                    if len(pnls) < 100: continue
                    wins = sum(1 for p in pnls if p > 0)
                    wr = 100*wins/len(pnls)
                    total_pnl = sum(pnls) * 100  # в % от BET
                    results.append({
                        'symbol': pair, 'tf': tf, 'strategy': name,
                        'wr': round(wr,1), 'n': len(pnls),
                        'total_pnl_pct': round(total_pnl,2),
                        'fee': '0.05% taker + 0.02% slippage'
                    })
                except Exception as e:
                    log(f'  {pair} {tf} {name}: {e}')
    results.sort(key=lambda x: -x['total_pnl_pct'])
    with open(REPORT, 'w') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'results': results}, f, indent=2, ensure_ascii=False)
    log(f'Прогонов: {len(results)}')
    for r in results[:10]:
        log(f"  {r['symbol']:10} {r['tf']:3} {r['strategy']:15} WR={r['wr']}% n={r['n']} PnL={r['total_pnl_pct']}%")

if __name__ == '__main__': main()
