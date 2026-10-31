#!/usr/bin/env python3
"""strategy_mutations.py — мутации стратегий (новые параметры из базовых)."""
import numpy as np

def _ema(data, n):
    """EMA."""
    alpha = 2.0 / (n + 1)
    ema = np.zeros_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
    return ema

def _sma(data, n):
    """SMA."""
    sma = np.zeros_like(data)
    for i in range(len(data)):
        if i < n:
            sma[i] = data[i]
        else:
            sma[i] = np.mean(data[i-n+1:i+1])
    return sma

def _vwap(o, h, l, c, v, period):
    """VWAP за period."""
    tp = (h + l + c) / 3
    vwap = np.zeros_like(c)
    for i in range(len(c)):
        start = max(0, i - period + 1)
        pv = np.sum(tp[start:i+1] * v[start:i+1])
        vv = np.sum(v[start:i+1])
        vwap[i] = pv / vv if vv > 0 else c[i]
    return vwap

# ===== МУТАЦИИ =====

def make_ema_mutation(fast, slow):
    """EMA пересечение: fast > slow → LONG, fast < slow → SHORT."""
    def fn(o, h, l, c, v, params):
        ef = _ema(c, fast)
        es = _ema(c, slow)
        up = np.zeros(len(c), dtype=bool)
        dn = np.zeros(len(c), dtype=bool)
        for i in range(1, len(c)):
            if ef[i] > es[i] and ef[i-1] <= es[i-1]:
                up[i] = True
            elif ef[i] < es[i] and ef[i-1] >= es[i-1]:
                dn[i] = True
        return up, dn
    fn.__name__ = f'ema_{fast}_{slow}'
    return fn

def make_vwap_mutation(period):
    """VWAP откат: цена < VWAP → LONG, цена > VWAP → SHORT."""
    def fn(o, h, l, c, v, params):
        vw = _vwap(o, h, l, c, v, period)
        up = np.zeros(len(c), dtype=bool)
        dn = np.zeros(len(c), dtype=bool)
        for i in range(1, len(c)):
            if c[i] < vw[i] and c[i-1] >= vw[i-1]:
                up[i] = True
            elif c[i] > vw[i] and c[i-1] <= vw[i-1]:
                dn[i] = True
        return up, dn
    fn.__name__ = f'vwap_rev_{period}'
    return fn

def make_sma_mutation(fast, slow):
    """SMA пересечение."""
    def fn(o, h, l, c, v, params):
        sf = _sma(c, fast)
        ss = _sma(c, slow)
        up = np.zeros(len(c), dtype=bool)
        dn = np.zeros(len(c), dtype=bool)
        for i in range(1, len(c)):
            if sf[i] > ss[i] and sf[i-1] <= ss[i-1]:
                up[i] = True
            elif sf[i] < ss[i] and sf[i-1] >= ss[i-1]:
                dn[i] = True
        return up, dn
    fn.__name__ = f'sma_{fast}_{slow}'
    return fn

# ===== ГЕНЕРАЦИЯ МУТАНТОВ =====

def generate_mutations(base_strategies=None):
    """Генерирует мутантов: EMA, VWAP, SMA с разными параметрами."""
    muts = {}

    # EMA мутации: все комбинации fast 3-12, slow 15-30
    for fast in [3, 4, 5, 6, 7, 8, 9, 10, 12]:
        for slow in [15, 18, 20, 22, 24, 25, 26, 28, 30]:
            if slow > fast + 5:
                name = f'okx_ema_{fast}_{slow}'
                muts[name] = make_ema_mutation(fast, slow)

    # VWAP мутации: периоды 10, 15, 20, 25, 30, 40
    for period in [10, 15, 20, 25, 30, 40]:
        name = f'okx_vwap_rev_{period}'
        muts[name] = make_vwap_mutation(period)

    # SMA мутации: fast 5-15, slow 20-40
    for fast in [5, 8, 10, 12, 15]:
        for slow in [20, 25, 30, 35, 40]:
            if slow > fast + 5:
                name = f'okx_sma_{fast}_{slow}'
                muts[name] = make_sma_mutation(fast, slow)

    return muts

if __name__ == '__main__':
    m = generate_mutations()
    print(f'Сгенерировано мутантов: {len(m)}')
    for name in list(m.keys())[:10]:
        print(f'  {name}')
