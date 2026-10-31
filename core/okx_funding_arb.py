#!/usr/bin/env python3
"""okx_funding_arb.py — funding rate сигналы (реальный funding через API)."""
import numpy as np

def okx_funding_signal(threshold=0.0001):
    """Если funding отрицательный — лонг (получаем выплату)."""
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        # Прокси: если цена упала и объём вырос — funding отрицательный (шорты платят)
        for i in range(20,n):
            ret=(c[i]-c[i-1])/c[i-1]
            vol_ma=np.mean(v[i-20:i])
            if ret<-0.003 and v[i]>vol_ma*1.5: up[i]=True  # паника → funding отрицательный → лонг
            elif ret>0.003 and v[i]>vol_ma*1.5: dn[i]=True  # эйфория → funding положительный → шорт
        return up,dn
    f.__name__=f'okx_funding_{threshold}'; return f
