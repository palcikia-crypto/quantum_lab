#!/usr/bin/env python3
"""strategy_pool.py — стратегии для Quantum Lab.
База из rslab2 + новые (VWAP, OBI, funding, vol_breakout).
Каждая стратегия: fn(o,h,l,c,v,ind) -> (up, dn) — массивы bool.
"""
import numpy as np

def calc_sma(c, p):
    n = len(c); out = np.full(n, np.nan)
    for i in range(p-1, n): out[i] = c[i-p+1:i+1].mean()
    return out

def calc_ema(c, p):
    n = len(c); out = np.full(n, np.nan); k = 2/(p+1); out[p-1] = c[:p].mean()
    for i in range(p, n): out[i] = c[i]*k + out[i-1]*(1-k)
    return out

def calc_rsi(c, p=14):
    n = len(c); out = np.full(n, 50.0)
    for i in range(p, n):
        g = sum(max(0, c[j]-c[j-1]) for j in range(i-p+1, i+1))
        l = sum(max(0, c[j-1]-c[j]) for j in range(i-p+1, i+1))
        out[i] = 100 if l == 0 else 100 - 100/(1 + g/l)
    return out

def calc_stoch(h, l, c, p=14):
    n = len(c); out = np.full(n, 50.0)
    for i in range(p, n):
        hh = h[i-p+1:i+1].max(); ll = l[i-p+1:i+1].min()
        if hh > ll: out[i] = (c[i]-ll)/(hh-ll)*100
    return out

def calc_atr(h, l, c, p=14):
    n = len(c); tr = np.zeros(n)
    for i in range(1, n): tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    atr = np.full(n, np.nan)
    for i in range(p, n): atr[i] = tr[i-p+1:i+1].mean()
    return atr

def calc_vwap(h, l, c, v):
    n = len(c); out = np.full(n, np.nan); cum_pv = 0; cum_v = 0
    for i in range(n):
        tp = (h[i]+l[i]+c[i])/3
        cum_pv += tp*v[i]; cum_v += v[i]
        if cum_v > 0: out[i] = cum_pv/cum_v
    return out

def calc_vol_zscore(v, p=20):
    n = len(v); out = np.full(n, 0.0)
    for i in range(p, n):
        m = v[i-p+1:i+1].mean(); s = v[i-p+1:i+1].std()
        if s > 0: out[i] = (v[i]-m)/s
    return out

# === БАЗОВЫЕ СТРАТЕГИИ (из rslab2) ===
def sig_mean_rev_2(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    for i in range(2, len(c)):
        if c[i-1] < c[i-2] and c[i] > c[i-1]: up[i] = True
        if c[i-1] > c[i-2] and c[i] < c[i-1]: dn[i] = True
    return up, dn

def sig_mean_rev_3(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    for i in range(3, len(c)):
        if c[i-1] < c[i-3] and c[i] > c[i-1]: up[i] = True
        if c[i-1] > c[i-3] and c[i] < c[i-1]: dn[i] = True
    return up, dn

def sig_stoch_20(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'stoch' not in ind: ind['stoch'] = calc_stoch(h,l,c,14)
    st = ind['stoch']
    for i in range(1, len(c)):
        if st[i-1] < 20 and st[i] >= 20: up[i] = True
        if st[i-1] > 80 and st[i] <= 80: dn[i] = True
    return up, dn

def sig_stoch_30(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'stoch' not in ind: ind['stoch'] = calc_stoch(h,l,c,14)
    st = ind['stoch']
    for i in range(1, len(c)):
        if st[i-1] < 30 and st[i] >= 30: up[i] = True
        if st[i-1] > 70 and st[i] <= 70: dn[i] = True
    return up, dn

def sig_rsi_25_up(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'rsi' not in ind: ind['rsi'] = calc_rsi(c,14)
    r = ind['rsi']
    for i in range(1, len(c)):
        if r[i-1] < 25 and r[i] >= 25: up[i] = True
    return up, dn

def sig_rsi_30_up(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'rsi' not in ind: ind['rsi'] = calc_rsi(c,14)
    r = ind['rsi']
    for i in range(1, len(c)):
        if r[i-1] < 30 and r[i] >= 30: up[i] = True
    return up, dn

def sig_rsi_70_down(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'rsi' not in ind: ind['rsi'] = calc_rsi(c,14)
    r = ind['rsi']
    for i in range(1, len(c)):
        if r[i-1] > 70 and r[i] <= 70: dn[i] = True
    return up, dn

def sig_ema_9_21(o,h,l,c,v,ind):
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'ema9' not in ind: ind['ema9'] = calc_ema(c,9)
    if 'ema21' not in ind: ind['ema21'] = calc_ema(c,21)
    e9, e21 = ind['ema9'], ind['ema21']
    for i in range(1, len(c)):
        if not np.isnan(e9[i]) and not np.isnan(e21[i]) and not np.isnan(e9[i-1]) and not np.isnan(e21[i-1]):
            if e9[i-1] < e21[i-1] and e9[i] > e21[i]: up[i] = True
            if e9[i-1] > e21[i-1] and e9[i] < e21[i]: dn[i] = True
    return up, dn

# === НОВЫЕ СТРАТЕГИИ ===
def sig_vwap_rev(o,h,l,c,v,ind):
    """Возврат к VWAP: цена отклонилась на 2% — ждём возврат."""
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'vwap' not in ind: ind['vwap'] = calc_vwap(h,l,c,v)
    vw = ind['vwap']
    for i in range(1, len(c)):
        if np.isnan(vw[i]): continue
        dev = (c[i] - vw[i]) / vw[i]
        if dev < -0.02 and c[i] > c[i-1]: up[i] = True
        if dev > 0.02 and c[i] < c[i-1]: dn[i] = True
    return up, dn

def sig_vol_breakout(o,h,l,c,v,ind):
    """Пробой по ATR: цена пробила high + 1.5*ATR."""
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'atr' not in ind: ind['atr'] = calc_atr(h,l,c,14)
    atr = ind['atr']
    for i in range(1, len(c)):
        if np.isnan(atr[i]): continue
        if c[i] > h[i-1] + 1.5*atr[i]: up[i] = True
        if c[i] < l[i-1] - 1.5*atr[i]: dn[i] = True
    return up, dn

def sig_vol_spike(o,h,l,c,v,ind):
    """Всплеск объёма: vol_z > 2 + цена растёт."""
    up = np.zeros(len(c), dtype=bool); dn = np.zeros(len(c), dtype=bool)
    if 'vz' not in ind: ind['vz'] = calc_vol_zscore(v,20)
    vz = ind['vz']
    for i in range(1, len(c)):
        if vz[i] > 2 and c[i] > c[i-1]: up[i] = True
        if vz[i] > 2 and c[i] < c[i-1]: dn[i] = True
    return up, dn


def sig_vwap_ema_scalp(o,h,l,c,v,ind):
    """5m скальпинг: VWAP + EMA 9/21."""
    up = np.zeros(len(c), dtype=bool)
    dn = np.zeros(len(c), dtype=bool)
    if 'vwap' not in ind: ind['vwap'] = calc_vwap(h,l,c,v)
    if 'ema9' not in ind: ind['ema9'] = calc_ema(c,9)
    if 'ema21' not in ind: ind['ema21'] = calc_ema(c,21)
    vw = ind['vwap']; e9 = ind['ema9']; e21 = ind['ema21']
    for i in range(1, len(c)):
        if np.isnan(vw[i]) or np.isnan(e9[i]) or np.isnan(e21[i]): continue
        if c[i] > vw[i] and e9[i-1] < e21[i-1] and e9[i] > e21[i]: up[i] = True
        if c[i] < vw[i] and e9[i-1] > e21[i-1] and e9[i] < e21[i]: dn[i] = True
    return up, dn

def sig_pump_dump(o,h,l,c,v,ind):
    """Памп/дамп: vol_z > 2 + price change > 1%."""
    up = np.zeros(len(c), dtype=bool)
    dn = np.zeros(len(c), dtype=bool)
    if 'vz' not in ind: ind['vz'] = calc_vol_zscore(v,20)
    vz = ind['vz']
    for i in range(1, len(c)):
        change = (c[i] - c[i-1]) / c[i-1]
        if vz[i] > 2 and change > 0.01: up[i] = True
        if vz[i] > 2 and change < -0.01: dn[i] = True
    return up, dn

STRATEGIES = {
    'mean_rev_2': sig_mean_rev_2, 'mean_rev_3': sig_mean_rev_3,
    'stoch_20': sig_stoch_20, 'stoch_30': sig_stoch_30,
    'rsi_25_up': sig_rsi_25_up, 'rsi_30_up': sig_rsi_30_up, 'rsi_70_down': sig_rsi_70_down,
    'ema_9_21': sig_ema_9_21,
    'vwap_rev': sig_vwap_rev, 'vol_breakout': sig_vol_breakout, 'vol_spike': sig_vol_spike, 'vwap_ema_scalp': sig_vwap_ema_scalp, 'pump_dump': sig_pump_dump,
}

if __name__ == '__main__':
    print(f'Стратегий: {len(STRATEGIES)}')
    for name in STRATEGIES: print(f'  {name}')


# ═══ ADVANCED (новые индикаторы) ═══
try:
    from strategy_pool_advanced import ADVANCED_STRATEGIES
    STRATEGIES.update(ADVANCED_STRATEGIES)
    print(f'Advanced: {len(ADVANCED_STRATEGIES)} стратегий')
except Exception as e:
    print(f'Advanced: {e}')

# ═══ МУТАНТЫ (из strategy_mutator.py) ═══
try:
    from strategy_mutator import generate_mutations
    _MUTS = generate_mutations(max_mutants=40)
    STRATEGIES.update(_MUTS)
except Exception as e:
    print(f'⚠️ мутанты не загружены: {e}')

# ═══ АВТО-ДОБАВЛЕННЫЕ (из auto_add) ═══
try:
    from strategy_mutator import mutate_bb, mutate_mean_rev
    # bb мутанты
    for p in [15, 20, 30]:
        for k in [1.5, 2.0, 2.5]:
            name = f'bb_{p}_{k}'
            if name not in STRATEGIES:
                STRATEGIES[name] = mutate_bb(p, k)
    # mean_rev мутанты
    for p in [15, 20, 30]:
        for th in [1.5, 2.0, 2.5]:
            name = f'mean_rev_{p}_{th}'
            if name not in STRATEGIES:
                STRATEGIES[name] = mutate_mean_rev(p, th)
except Exception as e:
    print(f'⚠️ bb/mean_rev мутанты не загружены: {e}')
