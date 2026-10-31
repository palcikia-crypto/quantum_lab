#!/usr/bin/env python3
"""gate_v3.py — gate с H1-тренд-фильтром. Отменяет сигналы против H1."""
import os, sys, json, sqlite3
import numpy as np
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/market.db')
sys.path.insert(0, os.path.join(BASE, 'core'))
from strategy_pool import STRATEGIES

def load_candles(symbol, tf):
    c = sqlite3.connect(DB, timeout=5)
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? ORDER BY ts", (symbol, tf)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def h1_trend(c, p=20):
    n = len(c); out = np.zeros(n, dtype=bool)
    for i in range(p, n):
        out[i] = c[i] > c[i-p+1:i+1].mean()
    return out

def apply_h1_filter(up, dn, symbol, ts):
    h1 = load_candles(symbol, '1h')
    if not h1: return up, dn
    h1_ts = h1['ts']; h1_c = h1['c']
    trend = h1_trend(h1_c)
    trend_map = {}
    for i, t in enumerate(h1_ts):
        trend_map[int(t)] = trend[i] if i < len(trend) else False
    up_f = up.copy(); dn_f = dn.copy()
    for i in range(len(ts)):
        t = int(ts[i])
        h1_t = t - (t % 3600)
        is_up = trend_map.get(h1_t, False)
        if up_f[i] and not is_up: up_f[i] = False
        if dn_f[i] and is_up: dn_f[i] = False
    return up_f, dn_f

OKX_TAKER_FEE = 0.0005  # 0.05% taker
OKX_MAKER_FEE = 0.0002  # 0.02% maker
FEE = 0.0015  # 0.1% вход + 0.1% выход + 0.05% слиппедж
OKX_SLIPPAGE = 0.0002   # 0.02% slippage

def simulate_okx(up, dn, o, c, start=50, model='open', use_maker=False):
    """OKX-симуляция с комиссиями + проскальзыванием."""
    fee = OKX_MAKER_FEE if use_maker else OKX_TAKER_FEE
    total_cost = fee * 2 + OKX_SLIPPAGE  # вход + выход + проскальзывание
    trades = []
    hi = len(c)-2 if model == 'open' else len(c)-1
    for i in range(start, hi):
        if up[i]:
            entry = o[i+1]; exit_p = c[i+2] if model == 'open' else c[i+1]
            gross = (exit_p - entry) / entry
            net = gross - total_cost
            trades.append(net)
        elif dn[i]:
            entry = o[i+1]; exit_p = c[i+2] if model == 'open' else c[i+1]
            gross = (entry - exit_p) / entry
            net = gross - total_cost
            trades.append(net)
    return trades

def simulate(up, dn, o, c, start=50, model='open'):
    trades = []
    hi = len(c)-2 if model == 'open' else len(c)-1
    for i in range(start, hi):
        if up[i]:
            entry = o[i+1]; exit_p = c[i+2] if model == 'open' else c[i+1]
            trades.append((exit_p - entry) / entry - FEE)
        elif dn[i]:
            entry = o[i+1]; exit_p = c[i+2] if model == 'open' else c[i+1]
            trades.append((entry - exit_p) / entry - FEE)
    return trades

def sharpe(pnls):
    if len(pnls) < 2: return 0
    a = np.array(pnls); return float(a.mean()/a.std()*np.sqrt(252)) if a.std() > 0 else 0

def max_dd(pnls):
    if not pnls: return 0
    cum = np.cumsum(pnls); peak = np.maximum.accumulate(cum)
    return float(abs((cum-peak).min())/max(abs(peak.max()),1)*100)

def monthly_stats(pnls, ts):
    if not pnls or not ts: return []
    by_m = {}
    for pnl, t in zip(pnls, ts):
        m = datetime.fromtimestamp(int(t)).strftime('%Y-%m')
        by_m.setdefault(m, []).append(pnl)
    out = []
    for m, ps in sorted(by_m.items()):
        wins = sum(1 for p in ps if p > 0)
        out.append({'month': m, 'wr': round(100*wins/len(ps),1), 'n': len(ps), 'pnl': round(sum(ps),4)})
    return out

def run_gate(symbol, tf, strat_name, strat_fn, model='open', use_h1=False):
    data = load_candles(symbol, tf)
    if not data or len(data['c']) < 100: return None
    o,h,l,c,v = data['o'], data['h'], data['l'], data['c'], data['v']
    ind = {}
    up, dn = strat_fn(o,h,l,c,v,ind)
    if use_h1: up, dn = apply_h1_filter(up, dn, symbol, data['ts'])
    pnls = simulate(up, dn, o, c, model=model)
    if len(pnls) < 50: return None
    n = len(pnls); wins = sum(1 for p in pnls if p > 0); wr = 100*wins/n
    from math import sqrt, erf
    se = sqrt(0.25/n); z = (wins/n - 0.5)/se if se > 0 else 0
    pval = 1 - 0.5*(1 + erf(abs(z)/sqrt(2)))
    ci_lo = wr - 1.96*sqrt(wr*(100-wr)/n) if n > 0 else 0
    min_wr = 53.0 if model == 'current' else 54.0
    L1 = {'wr': round(wr,1), 'n': n, 'p': round(pval,4), 'ci_lo': round(ci_lo,1),
          'pass': wr>=min_wr and n>=500 and pval<0.05 and ci_lo>50}
    cut = int(len(c)*0.7)
    tr = simulate(up[:cut], dn[:cut], o[:cut], c[:cut], model=model)
    te = simulate(up[cut:], dn[cut:], o[cut:], c[cut:], model=model)
    if len(tr) >= 10 and len(te) >= 10:
        tr_wr = 100*sum(1 for x in tr if x>0)/len(tr); te_wr = 100*sum(1 for x in te if x>0)/len(te)
        L2 = {'train_wr': round(tr_wr,1), 'test_wr': round(te_wr,1), 'delta': round(tr_wr-te_wr,1),
              'pass': tr_wr-te_wr<3 and te_wr>=min_wr-1 and len(te)>=100}
    else: L2 = {'pass': False}
    entry_ts = [data['ts'][i] for i in range(50, min(len(c)-2, len(c))) if up[i] or dn[i]]
    monthly = monthly_stats(pnls, entry_ts)
    L3 = {'trend_wr': round(max(m['wr'] for m in monthly),1) if monthly else 0,
          'flat_wr': round(min(m['wr'] for m in monthly),1) if monthly else 0,
          'pass': all(m['wr'] >= 52 for m in monthly) if monthly else False}
    if len(pnls) >= 10:
        a = np.array(pnls); sims = [np.random.choice(a, min(100,len(a))).sum() for _ in range(1000)]
        p95 = float(np.percentile(sims,95))
    else: p95 = 0
    L4 = {'p95': p95, 'sharpe': sharpe(pnls), 'max_dd': max_dd(pnls),
          'pass': p95>0 and max_dd(pnls)<20 and sharpe(pnls)>1.0}
    L7 = {'min_month_wr': min(m['wr'] for m in monthly) if monthly else 0,
          'all_pos': all(m['pnl']>0 for m in monthly) if monthly else False,
          'pass': all(m['wr']>=52 for m in monthly) and all(m['pnl']>0 for m in monthly) if monthly else False}
    passes = [L1['pass'], L2['pass'], L3['pass'], L4['pass'], L7['pass']]
    verdict = 'GOLDEN' if all(passes) else ('TRADE_NOW' if all(passes[:4]) else ('WATCH' if passes[0] and passes[1] else 'SKIP'))
    return {'symbol':symbol,'tf':tf,'strategy':strat_name,'model':model,'h1':use_h1,'verdict':verdict,
            'score': round(sum(passes)/5*10,1), 'L1':L1,'L2':L2,'L3':L3,'L4':L4,'L7':L7}

if __name__ == '__main__':
    results = []
    pairs = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT','ADAUSDT','AVAXUSDT','DOTUSDT','LINKUSDT']
    tf_model = {'5m':'current','15m':'current','1h':'open','4h':'open'}
    for pair in pairs:
        for tf, model in tf_model.items():
            for name, fn in STRATEGIES.items():
                try:
                    r = run_gate(pair, tf, name, fn, model=model, use_h1=True)
                    if r and r['L1']['n'] >= 50: results.append(r)
                except: pass
    results.sort(key=lambda x: (-x['score'], -x['L1']['wr']))
    summary = {v: sum(1 for r in results if r['verdict']==v) for v in ['GOLDEN','TRADE_NOW','WATCH','SKIP']}
    with open(f'{BASE}/data/gate_v3.json','w') as f:
        json.dump({'timestamp':datetime.now().isoformat(),'summary':summary,'results':results}, f, indent=2, ensure_ascii=False)
    print('Прогонов: ' + str(len(results)))
    print('Summary: ' + str(summary))
    for r in results[:15]:
        print('  ' + r['symbol'].ljust(10) + ' ' + r['tf'].ljust(3) + ' ' + r['strategy'].ljust(15) + ' ' + r['model'].ljust(8) + ' h1=' + str(r['h1']).ljust(5) + ' ' + r['verdict'].ljust(10) + ' WR=' + str(r['L1']['wr']) + '% n=' + str(r['L1']['n']))
