#!/usr/bin/env python3
"""okx_strategies_power.py — мощные стратегии для OKX: скальпинг по стакану, P&D, тренд."""
import numpy as np

# ═══ 1. Order Book Imbalance (скальпинг по стакану) ═══
def sig_obi_scalp(o,h,l,c,v, ind):
    """OBI: если объём бидов > асков (по свечному прокси) — лонг."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    for i in range(10, n):
        # Прокси: бычья свеча + объём выше среднего = дисбаланс в биды
        vol_ma = np.mean(v[i-10:i])
        body = (c[i] - o[i]) / o[i]
        if body > 0 and v[i] > vol_ma * 1.5: up[i] = True
        elif body < 0 and v[i] > vol_ma * 1.5: dn[i] = True
    return up, dn

# ═══ 2. Wall Break (пробой стены) ═══
def sig_wall_break(o,h,l,c,v, ind):
    """Если цена пробила максимум за 5 свечей с объёмом — лонг."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    for i in range(10, n):
        vol_ma = np.mean(v[i-10:i])
        if c[i] > max(h[i-5:i]) and v[i] > vol_ma * 2: up[i] = True
        elif c[i] < min(l[i-5:i]) and v[i] > vol_ma * 2: dn[i] = True
    return up, dn

# ═══ 3. Pump & Dump Detector (P&D) ═══
def sig_pd_detector(o,h,l,c,v, ind):
    """После пампа (рост > 5% за 5 свечей) ищем дамп: OBV падает, RSI дивергенция."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 30: return up, dn
    obv = np.zeros(n)
    for i in range(1, n):
        if c[i] > c[i-1]: obv[i] = obv[i-1] + v[i]
        elif c[i] < c[i-1]: obv[i] = obv[i-1] - v[i]
        else: obv[i] = obv[i-1]
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
    ag = np.convolve(gain, np.ones(14)/14, 'same'); al = np.convolve(loss, np.ones(14)/14, 'same')
    rs = ag / np.maximum(al, 1e-9); rsi = 100 - 100/(1+rs)
    for i in range(30, n):
        pump = (c[i] - c[i-5]) / c[i-5] > 0.05  # рост > 5% за 5 свечей
        obv_fall = obv[i] < obv[i-3] and obv[i-1] < obv[i-2]
        rsi_high = rsi[i] > 65
        if pump and obv_fall and rsi_high: dn[i] = True  # шорт после пампа
    return up, dn

# ═══ 4. Supertrend + MACD Squeeze ═══
def sig_supertrend_macd(o,h,l,c,v, ind):
    """Supertrend (10, 3) + MACD гистограмма > 0 — лонг."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 30: return up, dn
    # Supertrend (упрощённо: EMA 10 + ATR)
    ema10 = np.convolve(c, np.ones(10)/10, 'same')
    tr = np.array([max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, n)])
    atr = np.convolve(tr, np.ones(10)/10, 'same')
    upper = ema10 + atr * 3; lower = ema10 - atr * 3
    # MACD
    ema12 = np.convolve(c, np.ones(12)/12, 'same')
    ema26 = np.convolve(c, np.ones(26)/26, 'same')
    macd = ema12 - ema26
    signal = np.convolve(macd, np.ones(9)/9, 'same')
    hist = macd - signal
    for i in range(30, n):
        if c[i] > lower[i] and hist[i] > 0 and hist[i-1] <= 0: up[i] = True
        elif c[i] < upper[i] and hist[i] < 0 and hist[i-1] >= 0: dn[i] = True
    return up, dn

# ═══ 5. EMA200 + VWAP + RSI (тренд) ═══
def sig_ema_vwap_rsi(o,h,l,c,v, ind):
    """Цена > EMA200 и VWAP, RSI пересекает 50 вверх — лонг."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 200: return up, dn
    ema200 = np.convolve(c, np.ones(200)/200, 'same')
    tp = (h + l + c) / 3
    vwap = np.convolve(tp * v, np.ones(20), 'same') / np.maximum(np.convolve(v, np.ones(20), 'same'), 1e-9)
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
    ag = np.convolve(gain, np.ones(14)/14, 'same'); al = np.convolve(loss, np.ones(14)/14, 'same')
    rs = ag / np.maximum(al, 1e-9); rsi = 100 - 100/(1+rs)
    for i in range(200, n):
        if c[i] > ema200[i] and c[i] > vwap[i] and rsi[i] > 50 and rsi[i-1] <= 50: up[i] = True
        elif c[i] < ema200[i] and c[i] < vwap[i] and rsi[i] < 50 and rsi[i-1] >= 50: dn[i] = True
    return up, dn

# ═══ 6. SOL 15M Scalper (мульти-фильтр) ═══
def sig_multifilter_scalp(o,h,l,c,v, ind):
    """9/21 EMA + 50 EMA + 200 EMA + RSI + VWAP + объём."""
    n = len(c); up = np.zeros(n, dtype=bool); dn = np.zeros(n, dtype=bool)
    if n < 200: return up, dn
    ema9 = np.convolve(c, np.ones(9)/9, 'same')
    ema21 = np.convolve(c, np.ones(21)/21, 'same')
    ema50 = np.convolve(c, np.ones(50)/50, 'same')
    ema200 = np.convolve(c, np.ones(200)/200, 'same')
    tp = (h + l + c) / 3
    vwap = np.convolve(tp * v, np.ones(20), 'same') / np.maximum(np.convolve(v, np.ones(20), 'same'), 1e-9)
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0); loss = np.where(delta < 0, -delta, 0)
    ag = np.convolve(gain, np.ones(14)/14, 'same'); al = np.convolve(loss, np.ones(14)/14, 'same')
    rs = ag / np.maximum(al, 1e-9); rsi = 100 - 100/(1+rs)
    vol_ma = np.convolve(v, np.ones(20)/20, 'same')
    for i in range(200, n):
        long_ok = (ema9[i] > ema21[i] and ema9[i-1] <= ema21[i-1] and c[i] > ema50[i] and c[i] > ema200[i]
                   and 45 <= rsi[i] <= 65 and c[i] > vwap[i] and v[i] > vol_ma[i] * 1.3)
        short_ok = (ema9[i] < ema21[i] and ema9[i-1] >= ema21[i-1] and c[i] < ema50[i] and c[i] < ema200[i]
                    and 35 <= rsi[i] <= 55 and c[i] < vwap[i] and v[i] > vol_ma[i] * 1.3)
        if long_ok: up[i] = True
        elif short_ok: dn[i] = True
    return up, dn

OKX_POWER_STRATEGIES = {
    'okx_obi_scalp': sig_obi_scalp,
    'okx_wall_break': sig_wall_break,
    'okx_pd_detector': sig_pd_detector,
    'okx_supertrend_macd': sig_supertrend_macd,
    'okx_ema_vwap_rsi': sig_ema_vwap_rsi,
    'okx_multifilter_scalp': sig_multifilter_scalp,
}
