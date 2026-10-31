#!/usr/bin/env python3
"""optimize_by_regime.py — подбирает лучшие стратегии okx_mutator для каждой пары × режима рынка.
Использует market.db (свечи 15m) и oracle.db (режимы за историю).
Результат: data/okx_active_regime.json
"""
import os, sys, json, sqlite3, time
from collections import defaultdict
import numpy as np

BASE = os.path.expanduser('~/quantum_lab')
sys.path.insert(0, os.path.join(BASE,'core'))
from okx_mutator import generate_mutants

MARKET_DB = os.path.join(BASE, 'data/market.db')
ORACLE_DB = os.path.join(BASE, 'data/oracle.db')
ACTIVE    = os.path.join(BASE, 'data/okx_active.json')
OUT       = os.path.join(BASE, 'data/okx_active_regime.json')

FEE  = 0.001
SLIP = 0.0002
BET  = 100.0
TP   = 0.006   # 0.6% (медиана из optimize_tpsl)
SL   = 0.004   # 0.4%
TIMEOUT = 1    # 1 бар = 15 мин

MIN_N = 30
MIN_WR = 0.55
TOP_PER_REGIME = 3

# Какие пары берём (из okx_active, но без повторов)
def load_active_pairs():
    d = json.load(open(ACTIVE))['pairs']
    pairs = []
    seen = set()
    for k, v in d.items():
        sym = v.get('symbol', k.split('_')[0])
        if sym not in seen:
            pairs.append(sym); seen.add(sym)
    return pairs


def load_candles_with_regime(sym_pair):
    """Загружает 15m свечи и присоединяет режим из oracle.db по ближайшему ts."""
    sym = sym_pair.replace('-','')
    mc = sqlite3.connect(MARKET_DB)
    rows = mc.execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf='15m' ORDER BY ts ASC", (sym,)).fetchall()
    mc.close()
    if not rows: return None
    ts = np.array([r[0] for r in rows], dtype=np.int64)
    o  = np.array([r[1] for r in rows], dtype=float)
    h  = np.array([r[2] for r in rows], dtype=float)
    l  = np.array([r[3] for r in rows], dtype=float)
    c  = np.array([r[4] for r in rows], dtype=float)
    v  = np.array([r[5] for r in rows], dtype=float)
    oc = sqlite3.connect(ORACLE_DB)
    regs = oc.execute("SELECT ts, regime FROM regime_history WHERE symbol=? ORDER BY ts ASC", (sym,)).fetchall()
    oc.close()
    if not regs:
        return {'ts':ts,'o':o,'h':h,'l':l,'c':c,'v':v,'regime':np.array(['unknown']*len(ts), dtype=object)}
    rts = np.array([r[0] for r in regs], dtype=np.int64)
    rrg = np.array([r[1] for r in regs], dtype=object)
    # для каждого ts из candles — ближайший предшествующий rts
    idx = np.searchsorted(rts, ts, side='right') - 1
    idx = np.clip(idx, 0, len(rts)-1)
    regime = rrg[idx]
    return {'ts':ts,'o':o,'h':h,'l':l,'c':c,'v':v,'regime':regime}


def simulate(data, up, dn, tp=TP, sl=SL, timeout=1):
    """На каждом up/dn[i] -> вход по close[i], выход по TP/SL/timeout. Возвращает (n,wins,total)."""
    c = data['c']; h = data['h']; l = data['l']
    n = len(c)
    if n < 2: return 0,0,0.0
    ent_idx = np.where(up | dn)[0]
    ent_idx = ent_idx[(ent_idx >= 1) & (ent_idx < n-1)]
    if len(ent_idx) == 0: return 0,0,0.0
    sides = np.where(up[ent_idx], 1, -1)
    trades = 0; wins = 0; total = 0.0; last_i = -1
    for k, i in enumerate(ent_idx):
        if i <= last_i: continue
        side = sides[k]; entry = c[i]
        tp_p = entry*(1+tp) if side==1 else entry*(1-tp)
        sl_p = entry*(1-sl) if side==1 else entry*(1+sl)
        end = min(i+1+timeout, n)
        exit_p = None
        for j in range(i+1, end):
            if side==1:
                if l[j] <= sl_p: exit_p = sl_p; break
                if h[j] >= tp_p: exit_p = tp_p; break
            else:
                if h[j] >= sl_p: exit_p = sl_p; break
                if l[j] <= tp_p: exit_p = tp_p; break
        if exit_p is None:
            jj = min(i+timeout, n-1); exit_p = c[jj]
        else:
            jj = i
        move = (exit_p - entry)/entry if side==1 else (entry-exit_p)/entry
        pnl = (move - FEE - SLIP)*BET
        total += pnl; trades += 1
        if pnl > 0: wins += 1
        last_i = jj
    return trades, wins, total


def main():
    pairs = load_active_pairs()
    muts = generate_mutants()
    print(f'Пар для анализа: {len(pairs)}')
    print(f'Стратегий в okx_mutator: {len(muts)}')
    print()
    result = {'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'params': {'tp':TP,'sl':SL,'timeout':TIMEOUT,'fee':FEE,'slip':SLIP},
              'per_pair': {}}
    for pair in pairs:
        data = load_candles_with_regime(pair)
        if data is None:
            print(f'{pair}: ❌ нет свечей'); continue
        regimes = data['regime']
        unique_regs = [r for r in set(regimes) if r in ('flat','trend_up','trend_down')]
        print(f'--- {pair} | режимов: {dict(zip(*np.unique(regimes, return_counts=True)))} ---')
        per_reg = {}
        for reg in unique_regs:
            mask = (regimes == reg)
            if mask.sum() < 100: continue
            idxs = np.where(mask)[0]
            # берём только свечи этого режима (но индексируем непрерывно)
            sub = {
                'o': data['o'][idxs], 'h': data['h'][idxs], 'l': data['l'][idxs],
                'c': data['c'][idxs], 'v': data['v'][idxs],
            }
            scores = []
            for name, fn in muts.items():
                try:
                    up, dn = fn(sub['o'],sub['h'],sub['l'],sub['c'],sub['v'],{})
                except Exception:
                    continue
                n, wins, pnl = simulate(sub, up, dn)
                if n < MIN_N: continue
                wr = wins/n
                if wr < MIN_WR: continue
                scores.append((name, n, wr, pnl))
            scores.sort(key=lambda x: -x[3])
            top = scores[:TOP_PER_REGIME]
            print(f'  {reg:10s} | найдено {len(scores)} кандидатов, топ:')
            for name, n, wr, pnl in top:
                print(f'    {name:30s} n={n:4d} wr={wr*100:5.1f}% pnl=${pnl:>8.2f}')
            per_reg[reg] = [{'strategy':name,'n':n,'wr':round(wr,4),'pnl':round(pnl,2)} for name,n,wr,pnl in top]
        if per_reg:
            result['per_pair'][pair] = per_reg
        print()
    json.dump(result, open(OUT,'w'), indent=2, ensure_ascii=False)
    print(f'✅ Записано: {OUT}')
    print(f'   пар: {len(result["per_pair"])}')


if __name__ == '__main__':
    main()
