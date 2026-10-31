#!/usr/bin/env python3
"""ml_online.py — River online ML: учится на каждом примере, без переобучения."""
import os, sys, json, sqlite3, time, pickle
import numpy as np
from datetime import datetime
from river import compose, linear_model, preprocessing, metrics
from river import drift

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))

MARKET_DB = os.path.join(BASE, 'data/market.db')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
MODEL_PATH = os.path.join(BASE, 'data/ml_online.pkl')
LOG = os.path.join(BASE, 'logs/ml_online.log')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
TP = 0.003
SL = 0.0015

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def load_candles(sym, start_ts, end_ts, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute("""SELECT ts,o,h,l,c,v FROM candles
                        WHERE symbol=? AND tf=? AND ts>=? AND ts<? ORDER BY ts""",
                     (sym, tf, start_ts, end_ts)).fetchall()
    c.close()
    if not rows: return None
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def load_obi(sym, start_ts, end_ts):
    sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    c = sqlite3.connect(OB_DB, timeout=30)
    obs = c.execute("""SELECT ts, imbalance FROM orderbooks
                       WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                    (sym_dash, start_ts, end_ts)).fetchall()
    c.close()
    return {ts: obi for ts, obi in obs if obi is not None}

def calc_rsi_at(c, idx, period=14):
    if idx < period + 1: return 50
    deltas = np.diff(c[:idx+1])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0: return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_atr_at(h, l, c, idx):
    if idx < 50: return 0
    hh, ll, cc = h[:idx+1], l[:idx+1], c[:idx+1]
    tr = np.maximum(hh[1:] - ll[1:], np.maximum(np.abs(hh[1:] - cc[:-1]), np.abs(ll[1:] - cc[:-1])))
    return np.mean(tr[-14:])

def build_examples(data, obi_by_ts):
    examples = []
    for idx in range(60, len(data['c']) - 2):
        ts = int(data['ts'][idx])
        price = data['c'][idx]

        obi_val = None
        for ots in sorted(obi_by_ts.keys(), reverse=True):
            if ots <= ts: obi_val = obi_by_ts[ots]; break

        rsi = calc_rsi_at(data['c'], idx)
        atr = calc_atr_at(data['h'], data['l'], data['c'], idx)
        vol = data['v'][idx] / (np.mean(data['v'][idx-20:idx]) + 1e-9) if idx > 20 else 1

        future = data['c'][min(idx+2, len(data['c'])-1)]
        move = (future - price) / price
        if move >= TP: target = 1
        elif move <= -SL: target = 0
        else: continue

        examples.append(({'obi': obi_val if obi_val is not None else 0,
                          'rsi': rsi, 'atr': atr, 'vol': vol}, target))
    return examples

def main():
    log('=== RIVER ONLINE ML ===')
    now = int(time.time())
    start = now - 7*86400

    # Модель: StandardScaler + LogisticRegression + ADWIN (drift)
    model = compose.Pipeline(
        preprocessing.StandardScaler(),
        linear_model.LogisticRegression()
    )
    adwin = drift.ADWIN()
    metric = metrics.Accuracy()

    total = 0
    for sym in PAIRS:
        data = load_candles(sym, start, now)
        if not data: continue
        obi_by_ts = load_obi(sym, start, now)
        examples = build_examples(data, obi_by_ts)
        log(f'{sym}: {len(examples)} примеров')

        for x, y in examples:
            y_pred = model.predict_one(x)
            if y_pred is not None:
                metric.update(y, y_pred)
            model.learn_one(x, y)
            adwin.update(y)
            total += 1

    log(f'✅ Online-обучение: {total} примеров, Accuracy={metric.get():.3f}')
    log(f'   Drift detected: {adwin.drift_detected}')

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'model': model, 'adwin': adwin, 'accuracy': metric.get()}, f)
    log(f'✅ Модель сохранена: {MODEL_PATH}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
