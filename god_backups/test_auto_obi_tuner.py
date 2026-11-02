#!/usr/bin/env python3
"""auto_obi_tuner.py — автонастройка OBI-порога для v4 (по live-сделкам)."""
import os, json, sqlite3, shutil, time, stat
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB_V4 = os.path.join(BASE, 'data/okx_paper_v4.db')
OB_DB = os.path.join(BASE, 'data/orderbook.db')
V4_CFG = os.path.join(BASE, 'data/okx_tpsl_v4.json')
LOG = os.path.join(BASE, 'logs/auto_obi_tuner.log')

OBI_GRID = [-0.2, -0.3, -0.4, -0.5, -0.6]

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def backup(path):
    if os.path.exists(path):
        shutil.copy(path, f'{path}.bak.{int(time.time())}')

def get_trades(last_n=100):
    try:
        c = sqlite3.connect(DB_V4, timeout=5)
        rows = c.execute("""SELECT id, symbol, side, entry_price, exit_price, pnl, entry_ts, exit_ts
                            FROM trades WHERE status='CLOSED'
                            ORDER BY exit_ts DESC LIMIT ?""", (last_n,)).fetchall()
        c.close()
        return rows
    except Exception:
        return []

def get_obi_at(symbol, ts):
    try:
        c = sqlite3.connect(OB_DB, timeout=5)
        r = c.execute("""SELECT imbalance FROM orderbooks
                         WHERE symbol=? AND ts <= ? ORDER BY ts DESC LIMIT 1""",
                      (symbol, ts)).fetchone()
        c.close()
        return r[0] if r else None
    except Exception:
        return None

def main():
    log('=== AUTO OBI TUNER ===')
    trades = get_trades(last_n=100)
    if len(trades) < 10:
        log(f'⚠️ мало сделок: {len(trades)} < 10 — не трогаем')
        return
    log(f'Сделок: {len(trades)}')

    results = {}
    for th in OBI_GRID:
        n = 0; wins = 0; pnl = 0
        for t in trades:
            tid, sym, side, entry, exit_p, pnl_v, ets, xts = t
            obi = get_obi_at(sym, ets)
            if obi is None: continue
            if side == 'SHORT' and obi < th:
                n += 1
                if pnl_v and pnl_v > 0: wins += 1
                pnl += (pnl_v or 0)
        wr = 100.0 * wins / n if n else 0
        results[th] = {'n': n, 'wins': wins, 'wr': wr, 'pnl': round(pnl, 2)}
        log(f'  OBI < {th:.2f}: n={n}, WR={wr:.1f}%, PnL=${pnl:+.2f}')

    best = None
    for th, r in results.items():
        if r['n'] >= 10 and r['wr'] >= 50:
            if best is None or r['pnl'] > best['pnl']:
                best = {'th': th, **r}

    if not best:
        log('⚠️ нет порога с n>=10, WR>=50% — не меняем')
        return

    log(f'✅ Лучший OBI: {best["th"]:.2f} (n={best["n"]}, WR={best["wr"]:.1f}%, PnL=${best["pnl"]:+.2f})')

    try:
        cur = json.load(open(V4_CFG, encoding='utf-8'))
        backup(V4_CFG)
        st = os.stat(V4_CFG)
        need_restore = False
        if st.st_mode & stat.S_IWUSR == 0:
            os.chmod(V4_CFG, 0o644)
            need_restore = True

        for sym, cfg in cur.get('per_pair', {}).items():
            cfg['obi_threshold'] = best['th']
        cur['source'] = 'auto_obi_tuner'
        cur['updated_at'] = datetime.now().isoformat()
        json.dump(cur, open(V4_CFG, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
        log(f'✅ v4 обновлён: OBI={best["th"]:.2f}')

        if need_restore:
            os.chmod(V4_CFG, 0o444)
            log('✅ v4: 444 восстановлен')
    except Exception as e:
        log(f'⚠️ v4: {e}')

    log('=== DONE ===')

if __name__ == '__main__':
    main()
