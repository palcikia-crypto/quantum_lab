#!/usr/bin/env python3
"""gate_v2.py — 7 уровней + параметр model (current/open).
Для 5m/15m — current (окно = 1-3 свечи).
Для 1h/4h/1d — open (окно = 2+ свечи)."""
import os, json, sqlite3
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/market.db')

def load_candles(symbol, tf):
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf=? ORDER BY ts", (symbol, tf)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def simulate(up, dn, o, c, start=50, model='open'):
    trades = []; ts_list = []
    hi = len(c)-2 if model == 'open' else len(c)-1
    for i in range(start, hi):
        if up[i]:
            entry = o[i+1]; exit_p = c[i+2] if model == 'open' else c[i+1]
            trades.append((exit_p - entry) / entry)
        elif dn[i]:
            entry = o[i+1]; exit_p = c[i+2] if model == 'open' else c[i+1]
            trades.append((entry - exit_p) / entry)
    return trades

def sharpe(pnls):
    if len(pnls) < 2: return 0
    a = np.array(pnls)
    return float(a.mean()/a.std()*np.sqrt(252)) if a.std() > 0 else 0

def max_dd(pnls):
    if not pnls: return 0
    cum = np.cumsum(pnls); peak = np.maximum.accumulate(cum)
    return float(abs((cum-peak).min())/max(abs(peak.max()),1)*100)

def monte_carlo(pnls, n=1000, nt=100):
    if len(pnls) < 10: return {'p95': 0, 'sharpe': 0, 'max_dd': 0}
    a = np.array(pnls); sims = [np.random.choice(a, min(nt,len(a))).sum() for _ in range(n)]
    return {'p95': float(np.percentile(sims,95)), 'sharpe': sharpe(pnls), 'max_dd': max_dd(pnls)}

def walk_forward(up, dn, o, c, split=0.7, model='open'):
    n = len(c); cut = int(n*split)
    tr = simulate(up[:cut], dn[:cut], o[:cut], c[:cut], model=model)
    te = simulate(up[cut:], dn[cut:], o[cut:], c[cut:], model=model)
    return tr, te

def monthly_stats(pnls, entry_ts):
    if not pnls or not entry_ts: return []
    by_m = {}
    for pnl, t in zip(pnls, entry_ts):
        m = datetime.fromtimestamp(int(t)).strftime('%Y-%m')
        by_m.setdefault(m, []).append(pnl)
    out = []
    for m, ps in sorted(by_m.items()):
        wins = sum(1 for p in ps if p > 0)
        out.append({'month': m, 'wr': round(100*wins/len(ps),1), 'n': len(ps), 'pnl': round(sum(ps),4)})
    return out

def check_L1(pnls, min_wr):
    n = len(pnls)
    if n == 0: return {'wr':0,'n':0,'p':1,'ci_lo':0,'pass':False}
    wins = sum(1 for p in pnls if p > 0); wr = 100*wins/n
    from math import sqrt, erf
    se = sqrt(0.25/n); z = (wins/n - 0.5)/se if se > 0 else 0
    pval = 1 - 0.5*(1 + erf(abs(z)/sqrt(2)))
    ci_lo = wr - 1.96*sqrt(wr*(100-wr)/n) if n > 0 else 0
    return {'wr':round(wr,1),'n':n,'p':round(pval,4),'ci_lo':round(ci_lo,1),
            'pass': wr>=min_wr and n>=500 and pval<0.05 and ci_lo>50}

def check_L2(tr, te, min_wr):
    if len(tr) < 10 or len(te) < 10: return {'train_wr':0,'test_wr':0,'delta':0,'pass':False}
    tr_wr = 100*sum(1 for x in tr if x>0)/len(tr)
    te_wr = 100*sum(1 for x in te if x>0)/len(te)
    return {'train_wr':round(tr_wr,1),'test_wr':round(te_wr,1),'delta':round(tr_wr-te_wr,1),
            'pass': tr_wr-te_wr<3 and te_wr>=min_wr-1 and len(te)>=100}

def check_L4(pnls):
    mc = monte_carlo(pnls)
    return {**mc, 'pass': mc['p95']>0 and mc['max_dd']<20 and mc['sharpe']>1.0}

def check_L7(monthly):
    if not monthly: return {'min_month_wr':0,'all_pos':False,'pass':False}
    return {'min_month_wr': min(m['wr'] for m in monthly),
            'all_pos': all(m['pnl']>0 for m in monthly),
            'pass': all(m['wr']>=52 for m in monthly) and all(m['pnl']>0 for m in monthly)}

def run_gate(symbol, tf, strat_name, strat_fn, model='open'):
    data = load_candles(symbol, tf)
    if not data or len(data['c']) < 100: return None
    o,h,l,c,v = data['o'], data['h'], data['l'], data['c'], data['v']
    ind = {}
    up, dn = strat_fn(o,h,l,c,v,ind)
    pnls = simulate(up, dn, o, c, model=model)
    tr, te = walk_forward(up, dn, o, c, model=model)
    entry_ts = [data['ts'][i] for i in range(50, min(len(c)-2, len(c))) if up[i] or dn[i]]
    monthly = monthly_stats(pnls, entry_ts)
    # пороги зависят от модели
    min_wr = 53.0 if model == 'current' else 54.0
    L1 = check_L1(pnls, min_wr)
    L2 = check_L2(tr, te, min_wr)
    L3 = {'trend_wr': round(max(m['wr'] for m in monthly),1) if monthly else 0,
          'flat_wr': round(min(m['wr'] for m in monthly),1) if monthly else 0,
          'pass': all(m['wr'] >= 52 for m in monthly) if monthly else False}
    L4 = check_L4(pnls)
    L7 = check_L7(monthly)
    passes = [L1['pass'], L2['pass'], L3['pass'], L4['pass'], L7['pass']]
    verdict = 'GOLDEN' if all(passes) else ('TRADE_NOW' if all(passes[:4]) else ('WATCH' if passes[0] and passes[1] else 'SKIP'))
    return {'symbol':symbol,'tf':tf,'strategy':strat_name,'model':model,'verdict':verdict,
            'score': round(sum(passes)/5*10,1),
            'L1':L1,'L2':L2,'L3':L3,'L4':L4,'L7':L7}

if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.join(BASE, 'core'))
    from strategy_pool import STRATEGIES
    # модель по ТФ: 5m/15m = current, 1h+ = open
    tf_model = {'5m':'current','15m':'current','1h':'open','4h':'open','1d':'open'}
    results = []
    pairs = ['BTCUSDT','ETHUSDT','SOLUSDT']
    for pair in pairs:
        for tf, model in tf_model.items():
            for name, fn in STRATEGIES.items():
                r = run_gate(pair, tf, name, fn, model=model)
                if r and r['L1']['n'] >= 50:
                    results.append(r)
    results.sort(key=lambda x: (-x['score'], -x['L1']['wr']))
    summary = {v: sum(1 for r in results if r['verdict']==v) for v in ['GOLDEN','TRADE_NOW','WATCH','SKIP']}
    with open(f'{BASE}/data/gate_v2.json','w') as f:
        json.dump({'timestamp':datetime.now().isoformat(),'summary':summary,'results':results}, f, indent=2)
    print(f'Прогонов: {len(results)}')
    print(f'Summary: {summary}')
    print('=== ТОП-15 ===')
    for r in results[:15]:
        print(f"  {r['symbol']:10} {r['tf']:3} {r['strategy']:15} {r['model']:8} {r['verdict']:10} score={r['score']} WR={r['L1']['wr']}% n={r['L1']['n']}")
