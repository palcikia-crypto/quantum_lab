#!/usr/bin/env python3
"""ml_predictor_scalp_v3.py — ML для скальпинга (без неважных + VWAP)."""
import os, sys, json, sqlite3, time, pickle
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))

MARKET_DB = os.path.join(BASE, 'data/market.db')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
MODEL_PATH = os.path.join(BASE, 'data/ml_model_scalp_v3.pkl')
LOG = os.path.join(BASE, 'logs/ml_predictor_scalp_v3.log')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
PERIOD = 7*86400
TP = 0.003
SL = 0.0015
FEE = 0.0005

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

def load_orderbook(sym, start_ts, end_ts):
    sym_dash = sym[:-4] + '-USDT' if sym.endswith('USDT') else sym
    c = sqlite3.connect(OB_DB, timeout=30)
    obs = c.execute("""SELECT ts, imbalance, spread FROM orderbooks
                       WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                    (sym_dash, start_ts, end_ts)).fetchall()
    swap = sym_dash + '-SWAP'
    fundings = c.execute("""SELECT ts, funding_rate FROM funding
                            WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                         (swap, start_ts, end_ts)).fetchall()
    c.close()
    return obs, fundings

def calc_adx_at(c, h, l, idx):
    if idx < 50: return 0
    cc = c[:idx+1]; hh = h[:idx+1]; ll = l[:idx+1]
    plus_dm = np.maximum(np.diff(hh), 0)
    minus_dm = np.maximum(-np.diff(ll), 0)
    tr = np.maximum(hh[1:] - ll[1:], np.maximum(np.abs(hh[1:] - cc[:-1]), np.abs(ll[1:] - cc[:-1])))
    if len(tr) < 14: return 0
    plus_di = 100 * np.mean(plus_dm[-14:]) / (np.mean(tr[-14:]) + 1e-9)
    minus_di = 100 * np.mean(minus_dm[-14:]) / (np.mean(tr[-14:]) + 1e-9)
    return 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)

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

def calc_vwap_at(o, h, l, c, v, idx, period=20):
    if idx < period: return c[idx]
    tp = (h[idx-period+1:idx+1] + l[idx-period+1:idx+1] + c[idx-period+1:idx+1]) / 3
    vv = v[idx-period+1:idx+1]
    total = np.sum(vv)
    if total == 0: return c[idx]
    return np.sum(tp * vv) / total

def build_features(data, obi_by_ts, funding_by_ts):
    X = []; y = []
    for idx in range(60, len(data['c']) - 2):
        ts = int(data['ts'][idx])
        price = data['c'][idx]

        obi_val = None
        for ots in sorted(obi_by_ts.keys(), reverse=True):
            if ots <= ts: obi_val = obi_by_ts[ots]; break

        fund_val = None
        for fts in sorted(funding_by_ts.keys(), reverse=True):
            if fts <= ts: fund_val = funding_by_ts[fts]; break

        adx = calc_adx_at(data['c'], data['h'], data['l'], idx)
        atr = calc_atr_at(data['h'], data['l'], data['c'], idx)
        rsi = calc_rsi_at(data['c'], idx)
        vwap = calc_vwap_at(data['o'], data['h'], data['l'], data['c'], data['v'], idx)
        vwap_diff = (price - vwap) / vwap if vwap > 0 else 0
        vol = data['v'][idx] / (np.mean(data['v'][idx-20:idx]) + 1e-9) if idx > 20 else 1

        future_price = data['c'][min(idx+2, len(data['c'])-1)]
        move = (future_price - price) / price
        if move >= TP: target = 1
        elif move <= -SL: target = 0
        else: continue

        # Только важные: RSI, Funding, ATR, OBI, ADX, Vol, VWAP
        X.append([obi_val if obi_val is not None else 0,
                  fund_val if fund_val is not None else 0,
                  adx, atr, rsi, vwap_diff, vol])
        y.append(target)
    return X, y

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

def train_logreg(X, y, lr=0.01, epochs=1000, reg=0.01):
    n, m = X.shape
    mean = X.mean(axis=0); std = X.std(axis=0) + 1e-9
    Xn = (X - mean) / std
    Xb = np.hstack([np.ones((n, 1)), Xn])
    w = np.zeros(Xb.shape[1])
    for _ in range(epochs):
        z = Xb @ w
        p = sigmoid(z)
        grad = (Xb.T @ (p - y)) / n
        grad[1:] += reg * w[1:]
        w -= lr * grad
    return w, mean, std

def predict(w, mean, std, X):
    Xn = (X - mean) / std
    Xb = np.hstack([np.ones((Xn.shape[0], 1)), Xn])
    return sigmoid(Xb @ w)

def main():
    log('=== ML SCALP v3 (RSI, Funding, ATR, OBI, ADX, Vol, VWAP) ===')
    now = int(time.time()); start = now - PERIOD

    all_X = []; all_y = []
    for sym in PAIRS:
        data = load_candles(sym, start, now)
        if not data: continue
        ob_obs, ob_fundings = load_orderbook(sym, start, now)
        obi_by_ts = {ts: obi for ts, obi, spread in ob_obs if obi is not None}
        funding_by_ts = {ts: fr for ts, fr in ob_fundings}
        X, y = build_features(data, obi_by_ts, funding_by_ts)
        log(f'{sym}: {len(X)} примеров (LONG={sum(y)}, SHORT={len(y)-sum(y)})')
        all_X.extend(X); all_y.extend(y)

    if not all_X:
        log('❌ нет данных'); return

    X = np.array(all_X); y = np.array(all_y, dtype=float)
    log(f'Всего: {len(X)}, LONG={int(sum(y))}, SHORT={int(len(y)-sum(y))}')

    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    long_idx = np.where(y_train == 1)[0]; short_idx = np.where(y_train == 0)[0]
    if len(long_idx) > 0 and len(short_idx) > 0:
        n_min = min(len(long_idx), len(short_idx))
        ls = np.random.choice(long_idx, n_min, replace=False)
        ss = np.random.choice(short_idx, n_min, replace=False)
        bidx = np.concatenate([ls, ss])
        X_train = X_train[bidx]; y_train = y_train[bidx]
        log(f'Балансировка: LONG={n_min}, SHORT={n_min}, всего={len(X_train)}')

    w, mean, std = train_logreg(X_train, y_train)
    y_proba = predict(w, mean, std, X_test)
    y_pred = (y_proba > 0.5).astype(int)

    acc = np.mean(y_pred == y_test)
    tp = np.sum((y_pred == 1) & (y_test == 1))
    fp = np.sum((y_pred == 1) & (y_test == 0))
    fn = np.sum((y_pred == 0) & (y_test == 1))
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    log(f'✅ Модель обучена (scalp v3):')
    log(f'  Accuracy: {acc:.3f}')
    log(f'  Precision: {prec:.3f}')
    log(f'  Recall: {rec:.3f}')
    log(f'  F1: {f1:.3f}')

    feat_names = ['OBI', 'Funding', 'ADX', 'ATR', 'RSI', 'VWAP_diff', 'Vol']
    importances = np.abs(w[1:])
    importances = importances / (importances.sum() + 1e-9)
    log('Важность признаков:')
    for name, imp in sorted(zip(feat_names, importances), key=lambda x: -x[1]):
        log(f'  {name:10s}: {imp:.3f}')

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'type': 'logreg_scalp_v3', 'w': w, 'mean': mean, 'std': std,
                     'features': feat_names, 'accuracy': acc,
                     'precision': prec, 'recall': rec, 'f1': f1}, f)
    log(f'✅ Модель сохранена: {MODEL_PATH}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
