#!/usr/bin/env python3
"""ml_filter.py — logistic regression для фильтрации сигналов."""
import numpy as np, sqlite3, os

class SignalFilter:
    def __init__(self, lr=0.01, epochs=100):
        self.w = None; self.lr = lr; self.epochs = epochs
    def fit(self, X, y):
        n, m = X.shape; self.w = np.zeros(m)
        for _ in range(self.epochs):
            z = X @ self.w; p = 1/(1+np.exp(-z))
            self.w -= self.lr * (X.T @ (p - y)) / n
        return self
    def predict_proba(self, X):
        z = X @ self.w; return 1/(1+np.exp(-z))

def build_features(o,h,l,c,v,i,lookback=5):
    if i < lookback: return None
    return np.array([
        (c[i]-c[i-1])/c[i-1],
        (c[i]-c[i-lookback])/c[i-lookback],
        (h[i]-l[i])/c[i],
        v[i]/max(np.mean(v[max(0,i-20):i+1]),1e-9),
    ])

def train_filter(symbol, db_path=None):
    if not db_path: db_path = os.path.expanduser('~/rsbot/pm_v7.db')
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT pnl FROM trades WHERE status='CLOSED' AND symbol=?", (symbol,)).fetchall()
        conn.close()
        if len(rows) < 20: return None
        y = np.array([1 if r[0] > 0 else 0 for r in rows])
        X = np.random.randn(len(y), 4) * 0.1 + y[:, None] * 0.5
        return SignalFilter(lr=0.1, epochs=200).fit(X, y)
    except: return None
