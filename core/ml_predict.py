#!/usr/bin/env python3
"""ml_predict.py — предсказание направления (LONG/SHORT) по ML-модели."""
import os, sys, json, sqlite3, time, pickle
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))

MARKET_DB = os.path.join(BASE, 'data/market.db')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
MODEL_PATH = os.path.join(BASE, 'data/ml_model.pkl')
OUT = os.path.join(BASE, 'data/ml_predictions.json')
LOG = os.path.join(BASE, 'logs/ml_predict.log')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def load_candles(sym, limit=100, tf='15m'):
    c = sqlite3.connect(MARKET_DB, timeout=30)
    rows = c.execute("""SELECT ts,o,h,l,c,v FROM candles
                        WHERE symbol=? AND tf=? ORDER BY ts DESC LIMIT ?""",
                     (sym, tf, limit)).fetchall()
    c.close()
    if not rows: return None
    rows = rows[::-1]
    return {k: np.array([r[i] for r in rows]) for i, k in enumerate(['ts','o','h','l','c','v'])}

def load_recent_obi(sym):
    sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    c = sqlite3.connect(OB_DB, timeout=5)
    r = c.execute("""SELECT imbalance FROM orderbooks
                     WHERE symbol=? ORDER BY ts DESC LIMIT 1""", (sym_dash,)).fetchone()
    c.close()
    return r[0] if r else None

def load_recent_funding(sym):
    sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    swap = sym_dash + '-SWAP'
    c = sqlite3.connect(OB_DB, timeout=5)
    r = c.execute("""SELECT funding_rate FROM funding
                     WHERE symbol=? ORDER BY ts DESC LIMIT 1""", (swap,)).fetchone()
    c.close()
    return r[0] if r else None

def load_recent_pressure(sym, window=60):
    sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    now = int(time.time())
    c = sqlite3.connect(OB_DB, timeout=5)
    r = c.execute("""SELECT
                        SUM(CASE WHEN side='buy' THEN volume ELSE 0 END),
                        SUM(CASE WHEN side='sell' THEN volume ELSE 0 END)
                     FROM trades WHERE symbol=? AND ts > ?""", (sym_dash, now-window)).fetchone()
    c.close()
    if r and (r[0] or r[1]):
        return (r[0] or 0) - (r[1] or 0)
    return 0

def calc_adx_at(c, h, l, idx):
    if idx < 50: return 0
    cc = c[:idx+1]; hh = h[:idx+1]; ll = l[:idx+1]
    plus_dm = np.maximum(np.diff(hh), 0)
    minus_dm = np.maximum(-np.diff(ll), 0)
    tr = np.maximum(hh[1:] - ll[1:], np.maximum(np.abs(hh[1:] - cc[:-1]), np.abs(ll[1:] - cc[:-1])))
    if len(tr) < 14: return 0
    plus_di = 100 * np.mean(plus_dm[-14:]) / (np.mean(tr[-14:]) + 1e-9)
    minus_di = 100 * np.mean(minus_dm[-14:]) / (np.mean(tr[-14:]) + 1e-9)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    return dx

def calc_atr_at(h, l, c, idx):
    if idx < 50: return 0
    hh = h[:idx+1]; ll = l[:idx+1]; cc = c[:idx+1]
    tr = np.maximum(hh[1:] - ll[1:], np.maximum(np.abs(hh[1:] - cc[:-1]), np.abs(ll[1:] - cc[:-1])))
    return np.mean(tr[-14:])

def calc_rsi_at(c, idx, period=14):
    if idx < period + 1: return 50
    deltas = np.diff(c[:idx+1])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd_at(c, idx):
    if idx < 26: return 0
    cc = c[:idx+1]
    return np.mean(cc[-12:]) - np.mean(cc[-26:])

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

def predict(w, mean, std, X):
    Xn = (X - mean) / std
    Xb = np.hstack([np.ones((Xn.shape[0], 1)), Xn])
    return sigmoid(Xb @ w)

def main():
    log('=== ML PREDICT ===')
    if not os.path.exists(MODEL_PATH):
        log('❌ модель не найдена')
        return

    with open(MODEL_PATH, 'rb') as f:
        md = pickle.load(f)
    w = md['w']; mean = md['mean']; std = md['std']
    log(f'Модель: accuracy={md.get("accuracy", 0):.3f}, cv={md.get("cv_mean", 0):.3f}')

    preds = {}
    for sym in PAIRS:
        data = load_candles(sym, limit=100)
        if not data:
            log(f'{sym}: нет данных')
            continue
        idx = len(data['c']) - 1
        price = data['c'][idx]

        obi = load_recent_obi(sym)
        funding = load_recent_funding(sym)
        pressure = load_recent_pressure(sym)

        adx = calc_adx_at(data['c'], data['h'], data['l'], idx)
        atr = calc_atr_at(data['h'], data['l'], data['c'], idx)
        rsi = calc_rsi_at(data['c'], idx)
        macd = calc_macd_at(data['c'], idx)
        vol = data['v'][idx] / (np.mean(data['v'][idx-20:idx]) + 1e-9) if idx > 20 else 1

        features = np.array([[obi if obi is not None else 0,
                              funding if funding is not None else 0,
                              pressure, adx, atr, rsi, macd, vol]])
        proba = predict(w, mean, std, features)[0]
        side = 'LONG' if proba > 0.6 else ('SHORT' if proba < 0.4 else 'WAIT')

        preds[sym] = {'price': float(price), 'proba_long': round(float(proba), 3),
                      'side': side, 'obi': obi, 'funding': funding, 'pressure': pressure,
                      'adx': round(float(adx), 1), 'rsi': round(float(rsi), 1)}
        log(f'{sym}: price={price:.4f}, proba_long={proba:.3f}, side={side} (OBI={obi}, ADX={adx:.1f}, RSI={rsi:.1f})')

    out = {'updated_at': datetime.now().isoformat(), 'predictions': preds}
    json.dump(out, open(OUT, 'w'), indent=2, ensure_ascii=False)
    log(f'✅ predictions: {OUT}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
