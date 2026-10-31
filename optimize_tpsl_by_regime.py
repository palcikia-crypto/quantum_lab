#!/usr/bin/env python3
"""optimize_tpsl_by_regime.py — для каждой пары × режима подбирает TP/SL
для okx_vwap_rev_10 / okx_grid_sma_10 по истории market.db + regime_history."""
import os, sys, json, sqlite3, time
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE,'core'))
from okx_mutator import generate_mutants

MARKET_DB = os.path.join(BASE, 'data/market.db')
ORACLE_DB = os.path.join(BASE, 'data/oracle.db')
ACTIVE    = os.path.join(BASE, 'data/okx_active.json')
OUT       = os.path.join(BASE, 'data/okx_tpsl_by_regime.json')

FEE  = 0.001
SLIP = 0.0002
BET  = 100.0
TIMEOUT = 1

TP_GRID = [0.003, 0.004, 0.005, 0.006]
SL_GRID = [0.002, 0.003, 0.004]
MIN_N = 30
MIN_WR = 0.53
STRATEGIES = ['okx_vwap_rev_10', 'okx_grid_sma_10']


def load_data(sym_pair):
    sym = sym_pair.replace('-','')
    mc = sqlite3.connect(MARKET_DB, timeout=30)
    rows = mc.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' ORDER BY ts ASC", (sym,)).fetchall()
    mc.close()
    if not rows: return None
    ts = np.array([r[0] for r in rows], dtype=np.int64)
    o  = np.array([r[1] for r in rows], dtype=float)
    h  = np.array([r[2] for r in rows], dtype=float)
    l  = np.array([r[3] for r in rows], dtype=float)
    c  = np.array([r[4] for r in rows], dtype=float)
    v  = np.array([r[5] for r in rows], dtype=float)
    oc = sqlite3.connect(ORACLE_DB, timeout=30)
    regs = oc.execute("SELECT ts, regime FROM regime_history WHERE symbol=? ORDER BY ts ASC", (sym,)).fetchall()
    oc.close()
    if not regs:
        regime = np.array(['flat']*len(ts), dtype=object)
    else:
        rts = np.array([r[0] for r in regs], dtype=np.int64)
        rrg = np.array([r[1] for r in regs], dtype=object)
        idx = np.searchsorted(rts, ts, side='right') - 1
        idx = np.clip(idx, 0, len(rts)-1)
        regime = rrg[idx]
    return {'ts':ts,'o':o,'h':h,'l':l,'c':c,'v':v,'regime':regime}


def simulate(c, h, l, up, dn, tp, sl, timeout=1):
    n = len(c)
    if n < 2: return 0,0,0.0
    ent_idx = np.where(up | dn)[0]
    ent_idx = ent_idx[(ent_idx >= 1) & (ent_idx < n-1)]
    if len(ent_idx) == 0: return 0,0,0.0
    sides = np.where(up[ent_idx], 1, -1)
    trades=0; wins=0; total=0.0; last_i=-1
    for k,i in enumerate(ent_idx):
        if i <= last_i: continue
        side=sides[k]; entry=c[i]
        tp_p = entry*(1+tp) if side==1 else entry*(1-tp)
        sl_p = entry*(1-sl) if side==1 else entry*(1+sl)
        end=min(i+1+timeout,n); exit_p=None
        for j in range(i+1,end):
            if side==1:
                if l[j] <= sl_p: exit_p=sl_p; break
                if h[j] >= tp_p: exit_p=tp_p; break
            else:
                if h[j] >= sl_p: exit_p=sl_p; break
                if l[j] <= tp_p: exit_p=tp_p; break
        if exit_p is None:
            jj=min(i+timeout,n-1); exit_p=c[jj]
        else:
            jj=i
        move=(exit_p-entry)/entry if side==1 else (entry-exit_p)/entry
        pnl=(move-FEE-SLIP)*BET
        total+=pnl; trades+=1
        if pnl>0: wins+=1
        last_i=jj
    return trades,wins,total


def main():
    active = json.load(open(ACTIVE))['pairs']
    pairs = []
    seen = set()
    for k,v in active.items():
        sym = v.get('symbol', k.split('_')[0])
        if sym not in seen: pairs.append(sym); seen.add(sym)
    muts = generate_mutants()
    result = {'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'params': {'fee':FEE,'slip':SLIP,'timeout':TIMEOUT},
              'per_pair': {}}
    print(f'Пар: {len(pairs)}, стратегий в пуле: {len(STRATEGIES)}')
    for pair in pairs:
        data = load_data(pair)
        if data is None:
            print(f'{pair}: ❌ нет свечей'); continue
        regimes = data['regime']
        uniq = [r for r in set(regimes) if r in ('flat','trend_up','trend_down')]
        print(f'--- {pair} ---')
        per_reg = {}
        for reg in uniq:
            mask = (regimes == reg)
            if mask.sum() < 100: continue
            idxs = np.where(mask)[0]
            sub_c = data['c'][idxs]; sub_h = data['h'][idxs]; sub_l = data['l'][idxs]
            sub_o = data['o'][idxs]; sub_v = data['v'][idxs]
            best = None
            for strat_name in STRATEGIES:
                if strat_name not in muts: continue
                fn = muts[strat_name]
                try:
                    up, dn = fn(sub_o, sub_h, sub_l, sub_c, sub_v, {})
                except Exception:
                    continue
                for tp in TP_GRID:
                    for sl in SL_GRID:
                        if sl >= tp*2: continue
                        n,wins,pnl = simulate(sub_c, sub_h, sub_l, up, dn, tp, sl)
                        if n < MIN_N: continue
                        wr = wins/n
                        if wr < MIN_WR: continue
                        if pnl <= 0: continue
                        score = pnl
                        if best is None or score > best['score']:
                            best = {'strategy':strat_name, 'tp':tp, 'sl':sl, 'n':n, 'wr':wr, 'pnl':pnl, 'score':score}
            if best:
                print(f'  {reg:10s} -> {best["strategy"]:20s} TP={best["tp"]*100:.1f}% SL={best["sl"]*100:.1f}% n={best["n"]} wr={best["wr"]*100:.1f}% pnl=${best["pnl"]:.2f}')
                per_reg[reg] = {k:(round(v,5) if isinstance(v,float) else v) for k,v in best.items() if k!='score'}
            else:
                print(f'  {reg:10s} -> ❌ не найдено')
        if per_reg:
            result['per_pair'][pair] = per_reg
    json.dump(result, open(OUT,'w'), indent=2, ensure_ascii=False)
    print(f'\n✅ Записано: {OUT}')
    print(f'   пар: {len(result["per_pair"])}')


if __name__ == '__main__':
    main()
