#!/usr/bin/env python3
"""online_learning.py — переобучение граалей каждый час на свежих данных."""
import os, sys, json, sqlite3, time, re
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.expanduser('~/quantum_lab'), 'core'))
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/online_learning.log')
ACTIVE = os.path.join(BASE, 'data/okx_active.json')
MARKET = os.path.join(BASE, 'data/market.db')
FEE = 0.0015
SLIPPAGE = 0.0005
DAYS = 30  # окно online-learning

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line + '\n')

def get_fn(name):
    import sys as _sys
    _sys.path.insert(0, os.path.join(BASE, 'core'))
    from okx_mutator import okx_vwap_rev, ema_cross
    from okx_grid import okx_grid_sma
    from okx_new_strategies import okx_rsi_rev, okx_boll_rev, okx_ichimoku, okx_breakout
    nums = [float(x) for x in re.findall(r'\d+\.?\d*', name)]
    if name.startswith('okx_vwap_rev_') and nums: return okx_vwap_rev(int(nums[0]))
    if name.startswith('okx_grid_sma_') and nums: return okx_grid_sma(int(nums[0]))
    if name.startswith('okx_ema_') and len(nums) >= 2: return ema_cross(int(nums[0]), int(nums[1]))
    if name.startswith('okx_rsi_rev_') and nums: return okx_rsi_rev(int(nums[0]))
    if name.startswith('okx_boll_rev_') and nums: return okx_boll_rev(int(nums[0]))
    if name.startswith('okx_ichimoku_') and nums: return okx_ichimoku(int(nums[0]))
    if name.startswith('okx_breakout_') and nums: return okx_breakout(int(nums[0]))
    return None

def simulate(o,h,l,c,v,fn,tp,sl,timeout,start=30):
    try: up, dn = fn(o,h,l,c,v,{})
    except: return None
    wins=n=0; pnl=0.0
    for i in range(start, len(c)-1):
        for side, sig in [('LONG', up[i]), ('SHORT', dn[i])]:
            if not sig: continue
            ep = c[i]
            for j in range(i+1, min(i+1+timeout, len(c))):
                move = (c[j]-ep)/ep if side=='LONG' else (ep-c[j])/ep
                if move >= tp: pnl += tp-(2*FEE+SLIPPAGE); wins+=1; n+=1; break
                elif move <= -sl: pnl += -sl-(2*FEE+SLIPPAGE); n+=1; break
            else:
                move = (c[min(i+timeout,len(c)-1)]-ep)/ep if side=='LONG' else (ep-c[min(i+timeout,len(c)-1)])/ep
                pnl += move-(2*FEE+SLIPPAGE); n+=1
                if move>0: wins+=1
    if n==0: return None
    return {'n':n, 'wr':100*wins/n, 'pnl':pnl}

def main():
    log('=== ONLINE LEARNING ===')
    if not os.path.exists(ACTIVE): log('нет okx_active.json'); return
    d = json.load(open(ACTIVE))
    pairs = d.get('pairs', {})
    c = sqlite3.connect(MARKET, timeout=10)
    cutoff = int(time.time()) - DAYS*86400
    updated = 0
    for key, v in pairs.items():
        sym = v['symbol'].replace('-', '')
        strat = v['strategy']; tp=v['tp']; sl=v['sl']; timeout=v['timeout']
        rows = c.execute("SELECT o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' AND ts>? ORDER BY ts",
                         (sym, cutoff)).fetchall()
        if not rows or len(rows) < 100: continue
        o=np.array([r[0] for r in rows]); h=np.array([r[1] for r in rows])
        l=np.array([r[2] for r in rows]); cl=np.array([r[3] for r in rows]); vv=np.array([r[4] for r in rows])
        fn = get_fn(strat)
        if not fn: continue
        r = simulate(o,h,l,cl,vv,fn,tp,sl,timeout)
        if r and r['n'] >= 20:
            v['online_wr'] = round(r['wr'],1)
            v['online_pnl'] = round(r['pnl'],2)
            v['online_n'] = r['n']
            v['online_updated'] = datetime.now().isoformat()
            updated += 1
            if r['pnl'] < 0:
                log(f'  ⚠️ {sym} {strat}: online PnL={r["pnl"]:+.2f} (WR={r["wr"]:.1f}%)')
    c.close()
    if updated:
        d['online_updated_at'] = datetime.now().isoformat()
        json.dump(d, open(ACTIVE, 'w'), indent=2)
        log(f'  ✅ обновлено {updated} пар (online WR/PnL)')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
