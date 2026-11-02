#!/usr/bin/env python3
"""ml_online_simple.py — online SGD на numpy. Относительные признаки."""
import os, sys, json, sqlite3, time, pickle, random
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))

MARKET_DB  = os.path.join(BASE, 'data/market.db')
OB_DB      = os.path.join(BASE, 'data/orderbook.db')
MODEL_PATH = os.path.join(BASE, 'data/ml_online.pkl')
LOG        = os.path.join(BASE, 'logs/ml_online.log')

PAIRS = ['BTCUSDT','ETHUSDT','XRPUSDT','SOLUSDT','DOGEUSDT']
TP, SL = 0.003, 0.0015

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    try:
        with open(LOG,'a') as f: f.write(line+'\n')
    except Exception: pass

def load_candles(sym, start_ts, end_ts, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute("""SELECT ts,o,h,l,c,v FROM candles
                        WHERE symbol=? AND tf=? AND ts>=? AND ts<? ORDER BY ts""",
                     (sym, tf, start_ts, end_ts)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i,k in enumerate(['ts','o','h','l','c','v'])}

def load_obi(sym, start_ts, end_ts):
    sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    c = sqlite3.connect(OB_DB, timeout=30)
    rows = c.execute("""SELECT ts, imbalance FROM orderbooks
                        WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                     (sym_dash, start_ts, end_ts)).fetchall()
    c.close()
    return {ts: obi for ts, obi in rows if obi is not None}

def rsi_at(c, idx, p=14):
    if idx < p+1: return 50.0
    d = np.diff(c[:idx+1]); g = np.where(d>0,d,0); l = np.where(d<0,-d,0)
    ag, al = np.mean(g[-p:]), np.mean(l[-p:])
    if al == 0: return 100.0
    return 100.0 - 100.0/(1.0 + ag/al)

def atr_pct(h, l, c, idx, p=14):
    if idx < p+1: return 0.0
    hh, ll, cc = h[:idx+1], l[:idx+1], c[:idx+1]
    tr = np.maximum(hh[1:]-ll[1:],
         np.maximum(np.abs(hh[1:]-cc[:-1]), np.abs(ll[1:]-cc[:-1])))
    atr = np.mean(tr[-p:])
    return float(atr / max(cc[-1], 1e-9))

def vwap_diff_pct(o,h,l,c,v,idx,p=20):
    if idx < p: return 0.0
    tp = (h[idx-p+1:idx+1] + l[idx-p+1:idx+1] + c[idx-p+1:idx+1]) / 3.0
    vv = v[idx-p+1:idx+1]; s = np.sum(vv)
    if s == 0: return 0.0
    vwap = np.sum(tp*vv)/s
    return float((c[idx]-vwap)/max(vwap,1e-9))

def build_examples(data, obi_by_ts):
    ex = []
    ts_keys = sorted(obi_by_ts.keys()) if obi_by_ts else []
    for idx in range(60, len(data['c'])-2):
        ts = int(data['ts'][idx]); price = data['c'][idx]
        obi_val = 0.0
        if ts_keys:
            j = np.searchsorted(ts_keys, ts, side='right') - 1
            if j >= 0: obi_val = float(obi_by_ts[ts_keys[j]])
        rsi = rsi_at(data['c'], idx)
        atr = atr_pct(data['h'], data['l'], data['c'], idx)
        vd  = vwap_diff_pct(data['o'],data['h'],data['l'],data['c'],data['v'], idx)
        fut = data['c'][min(idx+2, len(data['c'])-1)]
        move = (fut - price)/price
        if move >= TP: y = 1
        elif move <= -SL: y = 0
        else: continue
        ex.append(([obi_val, rsi/100.0, atr, vd], y))
    return ex

def sigmoid(z):
    return 1.0/(1.0+np.exp(-np.clip(z,-500,500)))

def main():
    log('=== ONLINE SGD (numpy) v2 — relative features ===')
    now = int(time.time()); start = now - 7*86400
    all_ex = []
    for sym in PAIRS:
        data = load_candles(sym, start, now)
        if not data: log(f'{sym}: нет данных'); continue
        obi = load_obi(sym, start, now)
        ex = build_examples(data, obi)
        log(f'{sym}: {len(ex)} примеров')
        all_ex.extend(ex)

    if not all_ex:
        log('❌ нет данных'); return

    random.seed(42); random.shuffle(all_ex)
    X = np.array([x for x,_ in all_ex], dtype=float)
    mean = X.mean(axis=0); std = X.std(axis=0)
    std = np.where(std < 1e-6, 1.0, std)
    log(f'mean={mean.round(3).tolist()}')
    log(f'std ={std.round(3).tolist()}')

    w = np.zeros(5); lr0, l2 = 0.001, 1e-3
    win, total, drift = [], 0, False
    for x_raw, y in all_ex:
        x = (np.array(x_raw)-mean)/std
        xb = np.hstack([1.0, x])
        p = sigmoid(xb @ w)
        lr = lr0/(1.0+total*1e-4)
        w -= lr*((p-y)*xb + l2*w)
        total += 1
        win.append(int(p>0.5)==int(y))
        if len(win) > 200:
            win.pop(0)
            if np.mean(win) < 0.40 and not drift:
                log(f'⚠️ DRIFT acc={np.mean(win):.3f}'); drift=True

    acc = float(np.mean(win)) if win else 0.5
    log(f'✅ примеров: {total}, acc(last200): {acc:.3f}, drift={drift}')
    probe = [sigmoid(np.hstack([1.0,(np.array(x)-mean)/std]) @ w) for x,_ in all_ex[:200]]
    log(f'proba range (first 200): min={min(probe):.3f} max={max(probe):.3f} avg={np.mean(probe):.3f}')
    log(f'w = {w.round(4).tolist()}')

    with open(MODEL_PATH,'wb') as f:
        pickle.dump({'type':'online_sgd_v2','w':w,'mean':mean,'std':std,
                     'accuracy':acc,'drift':drift}, f)
    log(f'✅ модель: {MODEL_PATH}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
