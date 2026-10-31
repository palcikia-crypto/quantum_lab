#!/usr/bin/env python3
"""okx_new_strategies.py — новые семейства стратегий для grail_optimizer."""
import numpy as np

def okx_rsi_rev(period=14, oversold=30, overbought=70):
    def fn(o, h, l, c, v, ind):
        n = len(c)
        if n < period + 2: return np.zeros(n, bool), np.zeros(n, bool)
        delta = np.diff(c, prepend=c[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.zeros(n); avg_loss = np.zeros(n)
        for i in range(period, n):
            avg_gain[i] = np.mean(gain[i-period+1:i+1])
            avg_loss[i] = np.mean(loss[i-period+1:i+1])
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - 100/(1+rs)
        up = rsi < oversold
        dn = rsi > overbought
        return up, dn
    return fn

def okx_boll_rev(period=20, k=2.0):
    def fn(o, h, l, c, v, ind):
        n = len(c)
        if n < period: return np.zeros(n, bool), np.zeros(n, bool)
        sma = np.convolve(c, np.ones(period)/period, mode='same')
        std = np.array([np.std(c[max(0,i-period+1):i+1]) for i in range(n)])
        upper = sma + k*std
        lower = sma - k*std
        up = c < lower
        dn = c > upper
        return up, dn
    return fn

def okx_ichimoku(tenkan=9, kijun=26):
    def fn(o, h, l, c, v, ind):
        n = len(c)
        if n < kijun + 2: return np.zeros(n, bool), np.zeros(n, bool)
        tenkan_line = np.array([(np.max(h[max(0,i-tenkan+1):i+1]) + np.min(l[max(0,i-tenkan+1):i+1]))/2 for i in range(n)])
        kijun_line = np.array([(np.max(h[max(0,i-kijun+1):i+1]) + np.min(l[max(0,i-kijun+1):i+1]))/2 for i in range(n)])
        up = (c > tenkan_line) & (tenkan_line > kijun_line)
        dn = (c < tenkan_line) & (tenkan_line < kijun_line)
        return up, dn
    return fn

def okx_ensemble(strategies, min_votes=2):
    """Ансамбль: голосование нескольких стратегий."""
    def fn(o, h, l, c, v, ind):
        n = len(c)
        up_votes = np.zeros(n); dn_votes = np.zeros(n)
        for s in strategies:
            try:
                u, d = s(o, h, l, c, v, ind)
                up_votes += u.astype(int); dn_votes += d.astype(int)
            except: pass
        up = up_votes >= min_votes
        dn = dn_votes >= min_votes
        return up, dn
    return fn

def okx_breakout(period=20, atr_mult=1.5):
    def fn(o, h, l, c, v, ind):
        n = len(c)
        if n < period + 2: return np.zeros(n, bool), np.zeros(n, bool)
        hh = np.array([np.max(h[max(0,i-period+1):i+1]) for i in range(n)])
        ll = np.array([np.min(l[max(0,i-period+1):i+1]) for i in range(n)])
        tr = np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
        tr = np.concatenate([[h[0]-l[0]], tr])
        atr = np.array([np.mean(tr[max(0,i-period+1):i+1]) for i in range(n)])
        up = c > hh.shift(1) if hasattr(hh,'shift') else np.r_[False, c[1:] > hh[:-1]]
        up = np.r_[False, c[1:] > hh[:-1] + atr[1:]*atr_mult*0]
        dn = np.r_[False, c[1:] < ll[:-1] - atr[1:]*atr_mult*0]
        return up, dn
    return fn
