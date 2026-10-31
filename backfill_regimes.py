#!/usr/bin/env python3
"""backfill_regimes.py — вычисляет режимы (trend_up/trend_down/flat) по истории market.db
и пишет в oracle.db таблицу regime_history.
Режим: ADX(14) + EMA(50) + vol_z.
- trend_up: close > EMA50 и ADX > 25
- trend_down: close < EMA50 и ADX > 25
- flat: иначе
"""
import os, sys, sqlite3, time
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
MARKET_DB = os.path.join(BASE, 'data/market.db')
ORACLE_DB = os.path.join(BASE, 'data/oracle.db')

def ema(arr, period):
    out = np.full(len(arr), np.nan)
    if len(arr) < period: return out
    k = 2/(period+1)
    out[period-1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = arr[i]*k + out[i-1]*(1-k)
    return out

def atr(h, l, c, period=14):
    n = len(c)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    out = np.full(n, np.nan)
    if n < period: return out
    out[period-1] = tr[1:period].mean()
    for i in range(period, n):
        out[i] = (out[i-1]*(period-1) + tr[i]) / period
    return out

def adx(h, l, c, period=14):
    n = len(c)
    if n < period+1: return np.full(n, np.nan)
    up = h[1:] - h[:-1]
    dn = l[:-1] - l[1:]
    plus_dm = np.where((up>dn) & (up>0), up, 0.0)
    minus_dm = np.where((dn>up) & (dn>0), dn, 0.0)
    a = atr(h, l, c, period)[1:]
    plus_di = 100 * np.convolve(plus_dm, np.ones(period)/period, 'same') / np.maximum(a, 1e-9)
    minus_di = 100 * np.convolve(minus_dm, np.ones(period)/period, 'same') / np.maximum(a, 1e-9)
    dx = 100 * np.abs(plus_di - minus_di) / np.maximum(plus_di + minus_di, 1e-9)
    adx_vals = np.full(n, np.nan)
    adx_vals[period:] = np.convolve(dx, np.ones(period)/period, 'same')[:n-period]
    return adx_vals

def main():
    mc = sqlite3.connect(MARKET_DB)
    symbols = [r[0] for r in mc.execute("SELECT DISTINCT symbol FROM candles WHERE tf='15m'").fetchall()]
    oc = sqlite3.connect(ORACLE_DB, timeout=30)
    oc.execute("PRAGMA busy_timeout=30000")
    oc.execute("PRAGMA journal_mode=WAL")
    oc.execute("""CREATE TABLE IF NOT EXISTS regime_history (
        symbol TEXT, ts INTEGER, regime TEXT, adx REAL, atr REAL,
        PRIMARY KEY (symbol, ts))""")
    total = 0
    for sym in symbols:
        rows = mc.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' ORDER BY ts ASC", (sym,)).fetchall()
        if len(rows) < 100: continue
        ts = np.array([r[0] for r in rows], dtype=np.int64)
        h = np.array([r[2] for r in rows], dtype=float)
        l = np.array([r[3] for r in rows], dtype=float)
        c = np.array([r[4] for r in rows], dtype=float)
        ema50 = ema(c, 50)
        adx_v = adx(h, l, c, 14)
        atr_v = atr(h, l, c, 14)
        regimes = np.full(len(c), 'flat', dtype=object)
        for i in range(50, len(c)):
            if np.isnan(ema50[i]) or np.isnan(adx_v[i]): continue
            if c[i] > ema50[i] and adx_v[i] > 25: regimes[i] = 'trend_up'
            elif c[i] < ema50[i] and adx_v[i] > 25: regimes[i] = 'trend_down'
            else: regimes[i] = 'flat'
        batch = [(sym, int(ts[i]), regimes[i], float(adx_v[i]) if not np.isnan(adx_v[i]) else 0.0,
                  float(atr_v[i]) if not np.isnan(atr_v[i]) else 0.0) for i in range(50, len(c))]
        oc.executemany("INSERT OR REPLACE INTO regime_history (symbol,ts,regime,adx,atr) VALUES (?,?,?,?,?)", batch)
        oc.commit()
        from collections import Counter
        cnt = Counter(batch[i][2] for i in range(len(batch)))
        print(f'  {sym}: {len(batch)} свечей | {dict(cnt)}')
        total += len(batch)
    mc.close(); oc.close()
    print(f'✅ Записано {total} строк в regime_history')

if __name__ == '__main__':
    main()
