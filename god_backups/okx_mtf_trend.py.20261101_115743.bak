#!/usr/bin/env python3
"""okx_mtf_trend.py — мульти-таймфрейм тренд (4H + 1H EMA стек)."""
import numpy as np

def okx_mtf_trend():
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<200: return up,dn
        # 1H EMA (прокси: 4 свечи 15m = 1h)
        ema9_1h=np.convolve(c,np.ones(9*4)/(9*4),'same')
        ema21_1h=np.convolve(c,np.ones(21*4)/(21*4),'same')
        ema50_1h=np.convolve(c,np.ones(50*4)/(50*4),'same')
        for i in range(200,n):
            # Стек EMA: ema9 > ema21 > ema50 = тренд вверх
            if ema9_1h[i]>ema21_1h[i]>ema50_1h[i] and ema9_1h[i-1]<=ema21_1h[i-1]: up[i]=True
            elif ema9_1h[i]<ema21_1h[i]<ema50_1h[i] and ema9_1h[i-1]>=ema21_1h[i-1]: dn[i]=True
        return up,dn
    f.__name__='okx_mtf_trend'; return f
