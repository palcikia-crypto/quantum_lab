#!/usr/bin/env python3
"""rslab2_analytics.py — 4 анализа: Kelly, Monte Carlo, Correlation, MTF."""
import sys, os, json, sqlite3
sys.path.insert(0, os.path.expanduser('~/rsbot'))
import numpy as np
import importlib.util
spec = importlib.util.spec_from_file_location('rslab2', os.path.expanduser('~/rsbot/rslab2.py'))
rslab2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rslab2)
from datetime import datetime

BANK = 1000.0
FRACTIONAL = 0.25
MAX_BET = 20.0
MIN_BET = 5.0
PAYOUT_WIN = 0.48
PAYOUT_LOSS = -0.52

def load_h1(symbol):
    c = sqlite3.connect(rslab2.DB)
    rows = c.execute("SELECT ts,o,h,l,c FROM candles WHERE symbol=? AND tf='1h' ORDER BY ts", (symbol,)).fetchall()
    c.close()
    if rows and len(rows) > 100:
        return tuple(np.array([r[i] for r in rows]) for i in range(5)), 'h1_db'
    c = sqlite3.connect(rslab2.DB)
    rows = c.execute("SELECT ts,o,h,l,c FROM candles_m5 WHERE symbol=? ORDER BY ts", (symbol,)).fetchall()
    c.close()
    if not rows: return None, 'none'
    h1 = []
    for i in range(0, len(rows)-11, 12):
        ch = rows[i:i+12]
        h1.append((ch[0][0], ch[0][1], max(r[2] for r in ch), min(r[3] for r in ch), ch[-1][4]))
    if len(h1) < 100: return None, 'too_few'
    return tuple(np.array([r[i] for r in h1]) for i in range(5)), 'aggregated'

def kelly_analysis(findings):
    out = []
    for pair, fs in findings.items():
        conf = [f for f in fs if f['verdict'] == '✅ Confirmed']
        if not conf: continue
        best = conf[0]
        wr = best['wr'] / 100
        b = PAYOUT_WIN / abs(PAYOUT_LOSS)
        kf = (b * wr - (1-wr)) / b
        kfrac = kf * FRACTIONAL
        bet_raw = BANK * kfrac
        bet = max(MIN_BET, min(MAX_BET, round(bet_raw, 1)))
        ev = wr * PAYOUT_WIN + (1-wr) * PAYOUT_LOSS
        out.append({
            'pair': pair, 'strategy': best['strategy'], 'wr': best['wr'],
            'kelly_pct': round(kfrac*100, 2), 'bet_raw': round(bet_raw, 1),
            'bet_final': bet, 'ev_per_trade': round(ev * bet, 2),
        })
    return out

def monte_carlo(wins_list, n_sims=1000, n_trades=100):
    if len(wins_list) < 30: return None
    w = np.array([1 if x else 0 for x in wins_list])
    rng = np.random.default_rng(42)
    finals = []; dds = []
    for _ in range(n_sims):
        s = rng.choice(w, size=n_trades, replace=True)
        pnl = np.where(s == 1, PAYOUT_WIN*10, PAYOUT_LOSS*10)
        cum = np.cumsum(pnl)
        peak = np.maximum.accumulate(cum)
        finals.append(cum[-1]); dds.append((cum - peak).min())
    f = np.array(finals); d = np.array(dds)
    return {
        'pnl_mean': round(f.mean(),1), 'pnl_median': round(np.median(f),1),
        'pnl_p5': round(np.percentile(f,5),1), 'pnl_p95': round(np.percentile(f,95),1),
        'dd_mean': round(d.mean(),1), 'dd_worst5': round(np.percentile(d,5),1),
        'prob_profit': round((f>0).mean()*100,1),
    }

def mtf_test(pair, fn):
    data = rslab2.load_pair(pair)
    if data is None: return None
    ts, o, h, l, c, v = data
    ind = rslab2.indicators(o, h, l, c, v)
    up, dn = fn(o, h, l, c, v, ind)
    n = len(c); te_s = int(n * 0.80)
    h1, src = load_h1(pair)
    if h1 is None: return None
    h1_ts, h1_o, h1_h, h1_l, h1_c = h1
    h1_sma = rslab2.calc_sma(h1_c, 20)
    h1_idx = np.searchsorted(h1_ts, ts, side='right') - 1
    trend_up = np.zeros(n, bool)
    for i in range(n):
        idx = h1_idx[i]
        if idx >= 0 and not np.isnan(h1_sma[idx]):
            trend_up[i] = h1_c[idx] > h1_sma[idx]
    tr_base = rslab2.simulate(up, dn, o, c, te_s, n, None, model='open')
    wr_b, n_b = rslab2.wr_n(tr_base)
    up_m = up & trend_up
    dn_m = dn & (~trend_up)
    tr_m = rslab2.simulate(up_m, dn_m, o, c, te_s, n, None, model='open')
    wr_m, n_m = rslab2.wr_n(tr_m)
    return {
        'pair': pair, 'h1_src': src,
        'base_wr': wr_b, 'base_n': n_b,
        'mtf_wr': wr_m, 'mtf_n': n_m,
        'delta': round(wr_m - wr_b, 1) if n_m >= 20 else 0,
    }

def correlation_test(findings):
    """Проверяет корреляцию сигналов между парами."""
    signals = {}
    for pair, fs in findings.items():
        conf = [f for f in fs if f['verdict'] == '✅ Confirmed']
        if not conf: continue
        best = conf[0]
        data = rslab2.load_pair(pair)
        if data is None: continue
        ts, o, h, l, c, v = data
        ind = rslab2.indicators(o, h, l, c, v)
        fn = rslab2.STRATEGIES.get(best['strategy'])
        if not fn: continue
        try:
            up, dn = fn(o, h, l, c, v, ind)
        except: continue
        n = len(c); te_s = int(n * 0.80)
        # Вернуть vector of signals на test
        sig = np.zeros(n - te_s, int)
        sig[(up[te_s:n]) & ~(dn[te_s:n])] = 1
        sig[(dn[te_s:n]) & ~(up[te_s:n])] = -1
        signals[pair] = sig
    
    pairs = list(signals.keys())
    if len(pairs) < 2: return None
    # Обрезаем до min length
    min_len = min(len(s) for s in signals.values())
    arr = np.array([signals[p][:min_len] for p in pairs])
    # Correlation matrix
    corr = np.corrcoef(arr)
    result = {'pairs': pairs, 'matrix': corr.tolist()}
    return result

def main():
    np.random.seed(42)
    d = json.load(open(os.path.expanduser('~/rsbot/rslab2_findings_by_pair.json')))
    findings = d['findings']
    
    print("=" * 88)
    print("  RSLAB2 ANALYTICS — 4 анализа на 180 днях")
    print("=" * 88)
    
    # 1. KELLY
    print("\n" + "─" * 88)
    print("  1. KELLY SIZING")
    print("─" * 88)
    kelly = kelly_analysis(findings)
    print(f"  {'Pair':>10} | {'Strategy':>15} | {'WR':>5} | {'Kelly%':>7} | {'BET_raw':>8} | {'BET':>6} | {'EV/trade':>9}")
    for r in kelly:
        print(f"  {r['pair']:>10} | {r['strategy']:>15} | {r['wr']:>4.1f}% | {r['kelly_pct']:>6.2f}% | ${r['bet_raw']:>7.1f} | ${r['bet_final']:>5.1f} | ${r['ev_per_trade']:>+8.2f}")
    
    # 2. MONTE CARLO
    print("\n" + "─" * 88)
    print("  2. MONTE CARLO (1000×100)")
    print("─" * 88)
    mc_res = {}
    for pair in findings:
        conf = [f for f in findings[pair] if f['verdict'] == '✅ Confirmed']
        if not conf: continue
        best = conf[0]
        data = rslab2.load_pair(pair)
        if data is None: continue
        ts, o, h, l, c, v = data
        ind = rslab2.indicators(o, h, l, c, v)
        fn = rslab2.STRATEGIES.get(best['strategy'])
        if not fn: continue
        try:
            up, dn = fn(o, h, l, c, v, ind)
        except: continue
        n = len(c); te_s = int(n * 0.80)
        trades = rslab2.simulate(up, dn, o, c, te_s, n, None, model='open')
        wins = [t['win'] for t in trades]
        mc = monte_carlo(wins)
        if mc:
            mc_res[pair] = mc
            print(f"  {pair:>10} ({best['strategy']:>12}): PnL mean=${mc['pnl_mean']:+.1f} p5=${mc['pnl_p5']:+.1f} | DD mean=${mc['dd_mean']:+.1f} worst5%=${mc['dd_worst5']:+.1f} | P(profit)={mc['prob_profit']}%")
    
    # 3. MTF FILTER
    print("\n" + "─" * 88)
    print("  3. MTF FILTER (H1 trend)")
    print("─" * 88)
    mtf_res = {}
    for pair in findings:
        conf = [f for f in findings[pair] if f['verdict'] == '✅ Confirmed']
        if not conf: continue
        fn = rslab2.STRATEGIES.get(conf[0]['strategy'])
        if not fn: continue
        r = mtf_test(pair, fn)
        if r:
            mtf_res[pair] = r
            marker = '🎯' if r['delta'] > 2 else ('✅' if r['delta'] > 0 else '❌')
            print(f"  {pair:>10} ({r['h1_src']:>10}): Base={r['base_wr']:.1f}% n={r['base_n']} → MTF={r['mtf_wr']:.1f}% n={r['mtf_n']} Δ={r['delta']:+.1f} {marker}")
    
    # 4. CORRELATION
    print("\n" + "─" * 88)
    print("  4. CORRELATION (между парами)")
    print("─" * 88)
    corr = correlation_test(findings)
    if corr:
        pairs = corr['pairs']
        m = np.array(corr['matrix'])
        print(f"  {'':>10}", end='')
        for p in pairs: print(f" {p[:6]:>6}", end='')
        print()
        for i, p in enumerate(pairs):
            print(f"  {p:>10}", end='')
            for j in range(len(pairs)):
                if i == j: print(f" {'1.00':>6}", end='')
                else: print(f" {m[i,j]:>+6.2f}", end='')
            print()
    
    # Save
    out = {
        'timestamp': datetime.now().isoformat(),
        'kelly': kelly, 'monte_carlo': mc_res,
        'mtf_filter': mtf_res, 'correlation': corr,
    }
    out_path = os.path.expanduser('~/rsbot/rslab2_analytics.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\n💾 {out_path}")

if __name__ == '__main__':
    main()
