#!/usr/bin/env python3
"""okx_mutator.py — 100+ мутантов OKX-стратегий."""
import numpy as np

def ema_cross(fast, slow):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<slow+1: return up,dn
        ef=np.convolve(c,np.ones(fast)/fast,'same'); es=np.convolve(c,np.ones(slow)/slow,'same')
        for i in range(slow,n):
            if ef[i]>es[i] and ef[i-1]<=es[i-1]: up[i]=True
            elif ef[i]<es[i] and ef[i-1]>=es[i-1]: dn[i]=True
        return up,dn
    f.__name__=f'okx_ema_{fast}_{slow}'; return f

def donchian(p):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<p: return up,dn
        for i in range(p,n):
            hi=max(h[i-p:i]); lo=min(l[i-p:i])
            if c[i]>hi: up[i]=True
            elif c[i]<lo: dn[i]=True
        return up,dn
    f.__name__=f'okx_donchian_{p}'; return f

def rsi_vol(p, lo, hi):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<p+1: return up,dn
        d=np.diff(c,prepend=c[0]); g=np.where(d>0,d,0); ls=np.where(d<0,-d,0)
        ag=np.convolve(g,np.ones(p)/p,'same'); al=np.convolve(ls,np.ones(p)/p,'same')
        rs=ag/np.maximum(al,1e-9); rsi=100-100/(1+rs)
        vm=np.convolve(v,np.ones(20)/20,'same')
        for i in range(p,n):
            if rsi[i]<lo and v[i]>vm[i]: up[i]=True
            elif rsi[i]>hi and v[i]>vm[i]: dn[i]=True
        return up,dn
    f.__name__=f'okx_rsi_{p}_{lo}_{hi}'; return f

def vol_break(mult):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<20: return up,dn
        tr=np.array([max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,n)])
        atr=np.convolve(tr,np.ones(14)/14,'same')
        for i in range(20,n):
            if c[i]>h[i-1]+atr[i]*mult: up[i]=True
            elif c[i]<l[i-1]-atr[i]*mult: dn[i]=True
        return up,dn
    f.__name__=f'okx_vol_{mult}'; return f

def macd(fast, slow, sig):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<slow+sig: return up,dn
        ef=np.convolve(c,np.ones(fast)/fast,'same'); es=np.convolve(c,np.ones(slow)/slow,'same')
        macd=ef-es; signal=np.convolve(macd,np.ones(sig)/sig,'same')
        for i in range(slow+sig,n):
            if macd[i]>signal[i] and macd[i-1]<=signal[i-1]: up[i]=True
            elif macd[i]<signal[i] and macd[i-1]>=signal[i-1]: dn[i]=True
        return up,dn
    f.__name__=f'okx_macd_{fast}_{slow}_{sig}'; return f

from okx_strategies_power import OKX_POWER_STRATEGIES


def okx_obi_proxy(threshold=0.5):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<20: return up,dn
        vol_ma=np.convolve(v,np.ones(20)/20,'same')
        for i in range(20,n):
            body=(c[i]-o[i])/o[i]
            vol_ratio=v[i]/max(vol_ma[i],1e-9)
            if body>0.001 and vol_ratio>1.5: up[i]=True
            elif body<-0.001 and vol_ratio>1.5: dn[i]=True
        return up,dn
    f.__name__=f'okx_obi_proxy_{threshold}'; return f

def okx_vwap_rev(period=20):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<period: return up,dn
        tp=(h+l+c)/3
        vwap=np.convolve(tp*v,np.ones(period),'same')/np.maximum(np.convolve(v,np.ones(period),'same'),1e-9)
        for i in range(period,n):
            dev=(c[i]-vwap[i])/vwap[i]
            if dev<-0.005: up[i]=True
            elif dev>0.005: dn[i]=True
        return up,dn
    f.__name__=f'okx_vwap_rev_{period}'; return f

def okx_funding_proxy(period=20):
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<period: return up,dn
        for i in range(period,n):
            ret=(c[i]-c[i-1])/c[i-1]
            vol_ma=np.mean(v[i-period:i])
            if ret>0.005 and v[i]>vol_ma*2: dn[i]=True
            elif ret<-0.005 and v[i]>vol_ma*2: up[i]=True
        return up,dn
    f.__name__=f'okx_funding_{period}'; return f

from okx_grid import okx_grid_sma
from okx_funding_arb import okx_funding_signal
from okx_mtf_trend import okx_mtf_trend


def okx_obi_signal(obi_long=0.6, obi_short=-0.6):
    """OBI-стратегия: если OBI > obi_long — LONG, если < obi_short — SHORT."""
    def f(o,h,l,c,v, ind):
        n=len(c); up=np.zeros(n,dtype=bool); dn=np.zeros(n,dtype=bool)
        if n<20: return up,dn
        # Прокси OBI через объём + тело свечи (как в скальпере)
        vol_ma=np.convolve(v,np.ones(20)/20,'same')
        for i in range(20,n):
            body=(c[i]-o[i])/o[i]
            vol_ratio=v[i]/max(vol_ma[i],1e-9)
            # Сильный объём + бычья/медвежья свеча = OBI-сигнал
            if body>0.002 and vol_ratio>2.0: up[i]=True
            elif body<-0.002 and vol_ratio>2.0: dn[i]=True
        return up,dn
    f.__name__=f'okx_obi_signal_{obi_long}'; return f

def generate_mutants():
    muts={}
    for fast,slow in [(5,20),(9,21),(10,30),(12,26),(8,24),(15,35),(7,25),(6,18),(11,33),(4,16),(14,40),(20,50)]:
        m=ema_cross(fast,slow); muts[m.__name__]=m
    for p in [5,10,15,20,25,30,35,40,50,60,80,100]:
        m=donchian(p); muts[m.__name__]=m
    for p in [7,14,21,30]:
        for lo,hi in [(20,80),(30,70),(25,75),(15,85),(10,90),(35,65)]:
            m=rsi_vol(p,lo,hi); muts[m.__name__]=m
    for mult in [0.3,0.5,0.7,1.0,1.5,2.0,2.5,3.0]:
        m=vol_break(mult); muts[m.__name__]=m
    for fast,slow,sig in [(12,26,9),(5,35,5),(8,21,5),(10,30,10),(3,10,3)]:
        m=macd(fast,slow,sig); muts[m.__name__]=m
    # Мощные стратегии
    muts.update(OKX_POWER_STRATEGIES)
    for th in [0.3,0.5,0.7]:
        m=okx_obi_proxy(th); muts[m.__name__]=m
    for p in [10,20,30]:
        m=okx_vwap_rev(p); muts[m.__name__]=m
    for p in [10,20,30]:
        m=okx_funding_proxy(p); muts[m.__name__]=m
    # Grid
    for p in [10, 20, 30]:
        m=okx_grid_sma(p); muts[m.__name__]=m
    # Funding
    for th in [0.0001, 0.0003, 0.0005]:
        m=okx_funding_signal(th); muts[m.__name__]=m
    # MTF
    m=okx_mtf_trend(); muts[m.__name__]=m
    # OBI-сигналы
    for th in [0.5, 0.6, 0.7, 0.8]:
        m=okx_obi_signal(th, -th); muts[m.__name__]=m
    return muts

if __name__=='__main__':
    m=generate_mutants()
    print(f'✅ Мутантов: {len(m)}')
