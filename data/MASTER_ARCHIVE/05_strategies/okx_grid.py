#!/usr/bin/env python3
"""okx_grid.py — сеточная стратегия OKX (из документации)."""
import numpy as np

def okx_grid_sma(period=20, step=0.003, tp=0.004):
    """Сетка от SMA: вбоковик, каждый ордер с TP 0.4%."""
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<period: return up,dn
        sma=np.convolve(c,np.ones(period)/period,'same')
        for i in range(period,n):
            # Если цена ниже SMA и отскочила — лонг (сетап)
            if c[i] < sma[i] and c[i] > c[i-1] and (sma[i]-c[i])/sma[i] > step:
                up[i]=True
            # Если цена выше SMA и упала — шорт
            elif c[i] > sma[i] and c[i] < c[i-1] and (c[i]-sma[i])/sma[i] > step:
                dn[i]=True
        return up,dn
    f.__name__=f'okx_grid_sma_{period}'; return f
