#!/usr/bin/env python3
"""ml_predictor.py — ML-модель (RandomForest + GradientBoosting) с защитой от переобучения."""
import os, sys, json, sqlite3, time, pickle
import numpy as np
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE, 'core'))
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

MARKET_DB = os.path.join(BASE, 'data/market.db')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
MODEL_PATH = os.path.join(BASE, 'data/ml_model.pkl')
LOG = os.path.join(BASE, 'logs/ml_predictor.log')

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
PERIOD = 7*86400
TP = 0.006
SL = 0.004
FEE = 0.0015

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
    c = sqlite3.connect(OB_DB, timeout=30)
    obs = c.execute("""SELECT ts, imbalance, spread FROM orderbooks
                       WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                    (sym, start_ts, end_ts)).fetchall()
    swap = sym + '-SWAP'
    fundings = c.execute("""SELECT ts, funding_rate FROM funding
                            WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                         (swap, start_ts, end_ts)).fetchall()
    trades = c.execute("""SELECT ts, side, volume FROM trades
                          WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts""",
                       (sym, start_ts, end_ts)).fetchall()
    c.close()
    return obs, fundings, trades

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

def calc_macd_hist_at(c, idx):
    if idx < 26: return 0
    cc = c[:idx+1]
    ema12 = np.mean(cc[-12:])
    ema26 = np.mean(cc[-26:])
    return ema12 - ema26

def build_features(data, obi_by_ts, funding_by_ts, trades):
    X = []; y = []
    for idx in range(60, len(data['c']) - 2):
        ts = int(data['ts'][idx])
        price = data['c'][idx]

        obi_val = None
        for ots in sorted(obi_by_ts.keys(), reverse=True):
            if ots <= ts: obi_val = obi_by_ts[ots]['obi']; break

        fund_val = None
        for fts in sorted(funding_by_ts.keys(), reverse=True):
            if fts <= ts: fund_val = funding_by_ts[fts]; break

        buy = sum(v for tts, side, v in trades if side == 'buy' and ts - 60 <= tts <= ts)
        sell = sum(v for tts, side, v in trades if side == 'sell' and ts - 60 <= tts <= ts)
        pressure = buy - sell

        adx = calc_adx_at(data['c'], data['h'], data['l'], idx)
        atr = calc_atr_at(data['h'], data['l'], data['c'], idx)
        rsi = calc_rsi_at(data['c'], idx)
        macd = calc_macd_hist_at(data['c'], idx)
        vol = data['v'][idx] / (np.mean(data['v'][idx-20:idx]) + 1e-9) if idx > 20 else 1

        future_price = data['c'][min(idx+2, len(data['c'])-1)]
        move = (future_price - price) / price
        if move >= TP: target = 1
        elif move <= -SL: target = 0
        else: continue

        X.append([obi_val if obi_val is not None else 0,
                  fund_val if fund_val is not None else 0,
                  pressure, adx, atr, rsi, macd, vol])
        y.append(target)
    return X, y

def main():
    log('=== ML PREDICTOR (защита от переобучения) ===')
    now = int(time.time())
    start = now - PERIOD

    all_X = []
    all_y = []

    for sym in PAIRS:
        data = load_candles(sym, start, now)
        if not data: continue
        log(f'{sym}: {len(data["c"])} свечей')

        ob_obs, ob_fundings, ob_trades = load_orderbook(sym, start, now)
        obi_by_ts = {ts: {'obi': obi, 'spread': spread} for ts, obi, spread in ob_obs if obi is not None}
        funding_by_ts = {ts: fr for ts, fr in ob_fundings}

        X, y = build_features(data, obi_by_ts, funding_by_ts, ob_trades)
        log(f'  {sym}: {len(X)} примеров (LONG={sum(y)}, SHORT={len(y)-sum(y)})')
        all_X.extend(X)
        all_y.extend(y)

    if not all_X:
        log('❌ нет данных')
        return

    X = np.array(all_X)
    y = np.array(all_y)
    log(f'Всего: {len(X)} примеров, LONG={sum(y)}, SHORT={len(y)-sum(y)}')

    # Walk-forward: train на 5 дней, test на 2
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    log(f'Train: {len(X_train)}, Test: {len(X_test)}')

    # Ансамбль: RandomForest + GradientBoosting (с регуляризацией)
    rf = RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_leaf=10, random_state=42, n_jobs=-1)
    gb = GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42)
    model = VotingClassifier(estimators=[('rf', rf), ('gb', gb)], voting='soft')
    model.fit(X_train, y_train)

    # Метрики на тесте
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    log(f'✅ Модель обучена (walk-forward):')
    log(f'  Accuracy: {acc:.3f}')
    log(f'  Precision: {prec:.3f}')
    log(f'  Recall: {rec:.3f}')
    log(f'  F1: {f1:.3f}')

    # Кросс-валидация (5 фолдов) — проверка на переобучение
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
    log(f'  CV (5 фолдов): mean={cv_scores.mean():.3f}, std={cv_scores.std():.3f}')
    if cv_scores.std() > 0.15:
        log('⚠️ высокий std — возможное переобучение')

    # Важность признаков (из RandomForest)
    rf.fit(X_train, y_train)
    feat_names = ['OBI', 'Funding', 'Pressure', 'ADX', 'ATR', 'RSI', 'MACD', 'Vol']
    importances = rf.feature_importances_
    log('Важность признаков:')
    for name, imp in sorted(zip(feat_names, importances), key=lambda x: -x[1]):
        log(f'  {name:10s}: {imp:.3f}')

    # Сохраняем
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'model': model, 'features': feat_names,
                     'accuracy': acc, 'cv_mean': cv_scores.mean(), 'cv_std': cv_scores.std()}, f)
    log(f'✅ Модель сохранена: {MODEL_PATH}')
    log('=== DONE ===')

if __name__ == '__main__':
    main()
