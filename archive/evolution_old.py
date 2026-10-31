#!/usr/bin/env python3
"""rslab2_evolve_full.py — 3 уровня эволюции стратегий (программно, не AI).
   L1: Grid search по параметрам (RSI, SMA, mean_rev N)
   L2: Feature discovery (EMA, MACD, Stoch, BB, vol_zscore) + комбинации
   L3: Mutation лучших (добавляем фильтры к winners)
"""
import sys, os, json, time
sys.path.insert(0, os.path.expanduser('~/rsbot'))
import numpy as np
import importlib.util
spec = importlib.util.spec_from_file_location('rslab2', os.path.expanduser('~/rsbot/rslab2.py'))
rslab2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rslab2)

OUT = os.path.expanduser('~/rsbot/rslab2_evolve_full.json')
state = {'L1': [], 'L2': [], 'L3': [], 'all': []}

# ═══════════════════════════════════════════════════════════════
# ДОПОЛНИТЕЛЬНЫЕ ИНДИКАТОРЫ (для L2)
# ═══════════════════════════════════════════════════════════════
def calc_ema(c, p):
    n = len(c); e = np.full(n, np.nan)
    if n < p: return e
    alpha = 2 / (p + 1)
    e[p-1] = c[:p].mean()
    for i in range(p, n):
        e[i] = alpha * c[i] + (1 - alpha) * e[i-1]
    return e

def calc_macd(c, fast=12, slow=26, sig=9):
    ef = calc_ema(c, fast); es = calc_ema(c, slow)
    macd = ef - es
    signal = np.full(len(c), np.nan)
    valid = ~np.isnan(macd)
    if valid.sum() > sig:
        m = np.where(valid, macd, 0)
        ema_sig = calc_ema(m, sig)
        signal = ema_sig
    hist = macd - signal
    return macd, signal, hist

def calc_stoch(h, l, c, p=14):
    n = len(c); k = np.full(n, np.nan)
    for i in range(p, n):
        hh = h[i-p+1:i+1].max(); ll = l[i-p+1:i+1].min()
        k[i] = 100 * (c[i] - ll) / max(hh - ll, 1e-10)
    return k

def calc_bb_width(c, p=20, k=2.0):
    m = rslab2.calc_sma(c, p)
    sd = np.full(len(c), np.nan)
    for i in range(p-1, len(c)):
        sd[i] = c[i-p+1:i+1].std()
    return (2 * k * sd) / np.maximum(m, 1e-10)

def calc_vol_zscore(v, p=20):
    n = len(v); z = np.full(n, np.nan)
    for i in range(p, n):
        m = v[i-p:i].mean(); s = v[i-p:i].std()
        z[i] = (v[i] - m) / max(s, 1e-10)
    return z

def add_indicators(o, h, l, c, v, ind):
    """Расширяет ind новыми индикаторами (для L2)."""
    if 'ema9' not in ind:
        ind['ema9'] = calc_ema(c, 9)
        ind['ema21'] = calc_ema(c, 21)
        ind['macd'], ind['macd_sig'], ind['macd_hist'] = calc_macd(c)
        ind['stoch'] = calc_stoch(h, l, c, 14)
        ind['bb_width'] = calc_bb_width(c, 20, 2.0)
        ind['vol_z'] = calc_vol_zscore(v, 20)
    return ind

# ═══════════════════════════════════════════════════════════════
# L1: GRID SEARCH
# ═══════════════════════════════════════════════════════════════
def L1_grid():
    print("\n" + "=" * 80)
    print("  L1: GRID SEARCH (параметры)")
    print("=" * 80)
    pool = {}
    # RSI пороги
    for thr in [15, 20, 22, 25, 28, 30, 35]:
        def make(t):
            def fn(o,h,l,c,v,ind):
                n=len(c); up=ind['rsi']<t; dn=ind['rsi']>100-t
                return up, dn
            fn.__name__ = f'sig_rsi_{t}'; return fn
        pool[f'rsi_{thr}'] = make(thr)
    # RSI + volume
    for thr in [20, 25, 30]:
        for vm in [1.5, 2.0, 3.0]:
            def make(t, m):
                def fn(o,h,l,c,v,ind):
                    n=len(c); av=np.full(n,np.nan)
                    cs=np.cumsum(v); av[20:]=(cs[20:]-cs[:-20])/20
                    hv=(v>m*av)&~np.isnan(av)
                    return (ind['rsi']<t)&hv, (ind['rsi']>100-t)&hv
                fn.__name__=f'sig_rsi_{t}_vol{int(m*10)}'; return fn
            pool[f'rsi_{thr}_vol{int(vm*10)}'] = make(thr, vm)
    # mean_rev N
    for N in [2, 3, 4, 5]:
        def make(nn):
            def fn(o,h,l,c,v,ind):
                n=len(c); up=np.zeros(n,bool); dn=np.zeros(n,bool)
                for i in range(nn, n-1):
                    if all(c[i-j]<c[i-j-1] for j in range(nn)): up[i]=True
                    if all(c[i-j]>c[i-j-1] for j in range(nn)): dn[i]=True
                return up, dn
            fn.__name__=f'sig_mean_rev_{nn}'; return fn
        pool[f'mean_rev_{N}'] = make(N)
    # SMA cross
    for f,s in [(5,20),(5,50),(5,100),(10,50),(10,100),(20,100)]:
        def make(ff,ss):
            def fn(o,h,l,c,v,ind):
                sf=rslab2.calc_sma(c,ff); sl=rslab2.calc_sma(c,ss)
                pf=np.roll(sf,1); ps=np.roll(sl,1)
                pf[0]=np.nan; ps[0]=np.nan
                up=(sf>sl)&(pf<=ps)&~np.isnan(pf)&~np.isnan(ps)
                dn=(sf<sl)&(pf>=ps)&~np.isnan(pf)&~np.isnan(ps)
                return up, dn
            fn.__name__=f'sig_sma_{ff}_{ss}'; return fn
        pool[f'sma_{f}_{s}'] = make(f,s)
    # RSI + SMA
    for thr in [25, 30]:
        for p in [20, 50]:
            def make(t,pp,above):
                def fn(o,h,l,c,v,ind):
                    sma=rslab2.calc_sma(c,pp)
                    mask=(c>sma)&~np.isnan(sma) if above else (c<sma)&~np.isnan(sma)
                    return (ind['rsi']<t)&mask, (ind['rsi']>100-t)&(~mask)
                fn.__name__=f'sig_rsi{t}_sma{pp}_{"a" if above else "b"}'; return fn
            pool[f'rsi{thr}_sma{p}_a'] = make(thr,p,True)
            pool[f'rsi{thr}_sma{p}_b'] = make(thr,p,False)
    print(f"  Стратегий в L1: {len(pool)}")
    return pool

# ═══════════════════════════════════════════════════════════════
# L2: FEATURE DISCOVERY (новые индикаторы + комбо)
# ═══════════════════════════════════════════════════════════════
def L2_features():
    print("\n" + "=" * 80)
    print("  L2: FEATURE DISCOVERY (новые индикаторы)")
    print("=" * 80)
    pool = {}
    # EMA cross
    for f,s in [(9,21),(9,50),(21,50)]:
        def make(ff,ss):
            def fn(o,h,l,c,v,ind):
                ind = add_indicators(o,h,l,c,v,ind)
                ef = calc_ema(c,ff); es = calc_ema(c,ss)
                pf=np.roll(ef,1); ps=np.roll(es,1)
                pf[0]=np.nan; ps[0]=np.nan
                up=(ef>es)&(pf<=ps)&~np.isnan(pf)&~np.isnan(ps)
                dn=(ef<es)&(pf>=ps)&~np.isnan(pf)&~np.isnan(ps)
                return up, dn
            fn.__name__=f'sig_ema_{ff}_{ss}'; return fn
        pool[f'ema_{f}_{s}'] = make(f,s)
    # MACD hist
    def sig_macd_hist(o,h,l,c,v,ind):
        ind = add_indicators(o,h,l,c,v,ind)
        h_ = ind['macd_hist']; h_prev = np.roll(h_,1); h_prev[0]=np.nan
        up = (h_>0)&(h_prev<=0)&~np.isnan(h_prev)
        dn = (h_<0)&(h_prev>=0)&~np.isnan(h_prev)
        return up, dn
    pool['macd_hist'] = sig_macd_hist
    # Stochastic
    for thr in [20, 25, 30]:
        def make(t):
            def fn(o,h,l,c,v,ind):
                ind = add_indicators(o,h,l,c,v,ind)
                k = ind['stoch']
                up = k < t; dn = k > 100-t
                return up, dn
            fn.__name__=f'sig_stoch_{t}'; return fn
        pool[f'stoch_{thr}'] = make(thr)
    # BB squeeze breakout
    def sig_bb_squeeze(o,h,l,c,v,ind):
        ind = add_indicators(o,h,l,c,v,ind)
        m, bu, bl = rslab2.calc_bb(c, 20, 2.0)
        bw = ind['bb_width']; bw_med = np.nanmedian(bw[-500:])
        squeeze = bw < 0.7*bw_med
        up = squeeze & (c > bu); dn = squeeze & (c < bl)
        return up, dn
    pool['bb_squeeze'] = sig_bb_squeeze
    # Volume z-score + RSI
    for thr in [25, 30]:
        def make(t):
            def fn(o,h,l,c,v,ind):
                ind = add_indicators(o,h,l,c,v,ind)
                vz = ind['vol_z']
                hv = vz > 1.5
                return (ind['rsi']<t)&hv, (ind['rsi']>100-t)&hv
            fn.__name__=f'sig_rsi{t}_vz'; return fn
        pool[f'rsi_{thr}_vz'] = make(thr)
    # Multi-indicator: EMA9 + RSI
    def sig_ema9_rsi(o,h,l,c,v,ind):
        ind = add_indicators(o,h,l,c,v,ind)
        ef = ind['ema9']
        up = (c > ef) & (ind['rsi'] < 35) & ~np.isnan(ef)
        dn = (c < ef) & (ind['rsi'] > 65) & ~np.isnan(ef)
        return up, dn
    pool['ema9_rsi'] = sig_ema9_rsi
    # MACD + ATR regime
    def sig_macd_atr(o,h,l,c,v,ind):
        ind = add_indicators(o,h,l,c,v,ind)
        h_ = ind['macd_hist']
        med = np.nanmedian(ind['atr'])
        hv = (ind['atr'] > med) & ~np.isnan(ind['atr'])
        up = (h_ > 0) & hv; dn = (h_ < 0) & hv
        return up, dn
    pool['macd_atr'] = sig_macd_atr
    print(f"  Стратегий в L2: {len(pool)}")
    return pool

# ═══════════════════════════════════════════════════════════════
# L3: MUTATION (мутации победителей)
# ═══════════════════════════════════════════════════════════════
def L3_mutations(top_strats):
    print("\n" + "=" * 80)
    print("  L3: MUTATION (мутации топ-стратегий)")
    print("=" * 80)
    pool = {}
    base_fns = {name: rslab2.STRATEGIES.get(name) for name in top_strats if rslab2.STRATEGIES.get(name)}

    # Фильтры для мутации
    def filt_atr(o,h,l,c,v,ind):
        med = np.nanmedian(ind['atr'])
        return (ind['atr'] > med) & ~np.isnan(ind['atr'])

    def filt_vol(o,h,l,c,v,ind):
        av = np.full(len(v), np.nan)
        cs = np.cumsum(v); av[20:] = (cs[20:] - cs[:-20]) / 20
        return (v > 1.5 * av) & ~np.isnan(av)

    def filt_trend(o,h,l,c,v,ind):
        s50 = rslab2.calc_sma(c, 50)
        return (c > s50) & ~np.isnan(s50)

    filters = {'atr': filt_atr, 'vol': filt_vol, 'trend': filt_trend}

    for name, base_fn in base_fns.items():
        if base_fn is None: continue
        for fname, ffn in filters.items():
            def make(bn, ff):
                def fn(o,h,l,c,v,ind):
                    up, dn = bn(o,h,l,c,v,ind)
                    mask = ff(o,h,l,c,v,ind)
                    return up & mask, dn & mask
                fn.__name__ = f'{bn.__name__}_{ff.__name__}'
                return fn
            pool[f'{name}_{fname}'] = make(base_fn, ffn)

    print(f"  Мутаций: {len(pool)}")
    return pool

# ═══════════════════════════════════════════════════════════════
# ТЕСТИРОВАНИЕ ПУЛА
# ═══════════════════════════════════════════════════════════════
def test_pool(pool, stage_name):
    t0 = time.time()
    results = []
    for sym in rslab2.PAIRS:
        data = rslab2.load_pair(sym)
        if data is None: continue
        ts, o, h, l, c, v = data
        ind = rslab2.indicators(o, h, l, c, v)
        regimes = rslab2.classify_regime(ind['adx'])
        for sn, fn in pool.items():
            try:
                r = rslab2.screen_one(sym, sn, fn, data, ind, regimes, model='open')
            except Exception:
                continue
            if 'error' in r: continue
            if r['n_test'] < 200: continue
            if r['verdict'] in ('✅ Confirmed', '⚠️ Likely'):
                r['stage'] = stage_name
                results.append(r)
    dt = time.time() - t0
    conf = [r for r in results if r['verdict'] == '✅ Confirmed']
    likely = [r for r in results if r['verdict'] == '⚠️ Likely']
    print(f"  Готово за {dt:.0f}с: ✅ {len(conf)} | ⚠️ {len(likely)}")
    return results

def save_state():
    with open(OUT, 'w') as f:
        json.dump({
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'L1_count': len(state['L1']),
            'L2_count': len(state['L2']),
            'L3_count': len(state['L3']),
            'all': state['all'],
        }, f, indent=2)
    print(f"  💾 {OUT}")

def show_top(results, n=10, label=''):
    conf = [r for r in results if r['verdict'] == '✅ Confirmed']
    print(f"\n  ТОП Confirmed {label} ({len(conf)}):")
    for r in sorted(conf, key=lambda x: -x['wr_test'])[:n]:
        print(f"    {r['pair']:>10} | {r['strat']:>30} | WR={r['wr_test']}% n={r['n_test']} p={r['p']}")

def main():
    np.random.seed(42)
    print("=" * 80)
    print("  RSLAB2 EVOLVE — 3 уровня (программно, не AI)")
    print("=" * 80)

    # L1
    pool_L1 = L1_grid()
    results_L1 = test_pool(pool_L1, 'L1')
    state['L1'] = results_L1
    state['all'].extend(results_L1)
    save_state()
    show_top(results_L1, label='L1')

    # L2
    pool_L2 = L2_features()
    results_L2 = test_pool(pool_L2, 'L2')
    state['L2'] = results_L2
    state['all'].extend(results_L2)
    save_state()
    show_top(results_L2, label='L2')

    # L3 — мутации топ-3 стратегий из L1+L2
    all_conf = [r for r in state['all'] if r['verdict'] == '✅ Confirmed']
    all_conf.sort(key=lambda x: -x['wr_test'])
    top_strats = list(dict.fromkeys([r['strat'] for r in all_conf]))[:3]
    print(f"\n  L3: мутации топ-3 стратегий: {top_strats}")

    if top_strats:
        pool_L3 = L3_mutations(top_strats)
        results_L3 = test_pool(pool_L3, 'L3')
        state['L3'] = results_L3
        state['all'].extend(results_L3)
        save_state()
        show_top(results_L3, label='L3')

    # ФИНАЛЬНАЯ СВОДКА
    print("\n" + "=" * 80)
    print("  ФИНАЛЬНАЯ СВОДКА")
    print("=" * 80)
    print(f"  L1: {len(state['L1'])} результатов")
    print(f"  L2: {len(state['L2'])} результатов")
    print(f"  L3: {len(state['L3'])} результатов")

    all_conf = [r for r in state['all'] if r['verdict'] == '✅ Confirmed']
    print(f"\n  ВСЕГО Confirmed: {len(all_conf)}")
    print(f"\n  ТОП-20 по WR (все уровни):")
    for r in sorted(all_conf, key=lambda x: -x['wr_test'])[:20]:
        print(f"    {r['pair']:>10} | {r['strat']:>30} | WR={r['wr_test']}% n={r['n_test']} p={r['p']} [{r['stage']}]")

    # Записываем лучших в findings
    findings = []
    for r in sorted(all_conf, key=lambda x: -x['wr_test'])[:10]:
        findings.append({
            'symbol': r['pair'],
            'strategy': r['strat'],
            'metrics': {
                'wr': r['wr_test'], 'n': r['n_test'], 'p': r['p'],
                'ci_lo': r['ci_lo'], 'pnl': r['pnl'],
                'wr_trend': r.get('wr_trend'), 'wr_flat': r.get('wr_flat'),
            },
            'verdict': r['verdict'],
            'stage': r['stage'],
        })
    find_path = os.path.expanduser('~/rsbot/rslab2_evolve_findings.json')
    with open(find_path, 'w') as f:
        json.dump(findings, f, indent=2)
    print(f"\n  💾 {find_path} (топ-10 стратегий)")

if __name__ == '__main__':
    main()
