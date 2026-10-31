#!/usr/bin/env python3
"""okx_strategies.py — стратегии для OKX (скальпинг, пробои, тренд)."""
import numpy as np

def sig_ob_imbalance(o,h,l,c,v, ind):
    """Объёмный скальпинг: большой объём + бычья/медвежья свеча."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    for i in range(20, n):
        vol_ma = np.mean(v[i-20:i])
        if v[i] > vol_ma * 1.5:
            if c[i] > o[i]: up[i] = True
            else: dn[i] = True
    return up, dn

def sig_vol_breakout(o,h,l,c,v, ind):
    """Пробой ATR-канала."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 20: return up, dn
    tr = np.array([max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, n)])
    atr = np.convolve(tr, np.ones(14)/14, 'same')
    for i in range(20, n):
        if c[i] > h[i-1] + atr[i] * 0.5: up[i] = True
        elif c[i] < l[i-1] - atr[i] * 0.5: dn[i] = True
    return up, dn

def sig_ema_cross(o,h,l,c,v, ind):
    """EMA(9) пересекла EMA(21)."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 21: return up, dn
    ema9 = np.convolve(c, np.ones(9)/9, 'same')
    ema21 = np.convolve(c, np.ones(21)/21, 'same')
    for i in range(21, n):
        if ema9[i] > ema21[i] and ema9[i-1] <= ema21[i-1]: up[i] = True
        elif ema9[i] < ema21[i] and ema9[i-1] >= ema21[i-1]: dn[i] = True
    return up, dn

def sig_rsi_volume(o,h,l,c,v, ind):
    """RSI < 30 + объём (покупка), RSI > 70 + объём (продажа)."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 20: return up, dn
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
    ag = np.convolve(gain, np.ones(14)/14, 'same')
    al = np.convolve(loss, np.ones(14)/14, 'same')
    rs = ag / np.maximum(al, 1e-9); rsi = 100 - 100/(1+rs)
    vol_ma = np.convolve(v, np.ones(20)/20, 'same')
    for i in range(20, n):
        if rsi[i] < 30 and v[i] > vol_ma[i]: up[i] = True
        elif rsi[i] > 70 and v[i] > vol_ma[i]: dn[i] = True
    return up, dn

def sig_donchian(o,h,l,c,v, ind):
    """Пробой Donchian (20 свечей)."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 20: return up, dn
    for i in range(20, n):
        hi = max(h[i-20:i]); lo = min(l[i-20:i])
        if c[i] > hi: up[i] = True
        elif c[i] < lo: dn[i] = True
    return up, dn

OKX_STRATEGIES = {
    'okx_ob_imbalance': sig_ob_imbalance,
    'okx_vol_breakout': sig_vol_breakout,
    'okx_ema_cross': sig_ema_cross,
    'okx_rsi_volume': sig_rsi_volume,
    'okx_donchian': sig_donchian,
}
