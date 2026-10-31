#!/usr/bin/env python3
"""auto_tpsl_tuner.py — автонастройка TP/SL для v3/v4 по live-сделкам."""
import os, json, sqlite3, shutil, time, stat
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB_V3 = os.path.join(BASE, 'data/okx_paper_v3.db')
DB_V4 = os.path.join(BASE, 'data/okx_paper_v4.db')
V3_CFG = os.path.join(BASE, 'data/okx_tpsl_v3.json')
V4_CFG = os.path.join(BASE, 'data/okx_tpsl_v4.json')
LOG = os.path.join(BASE, 'logs/auto_tpsl_tuner.log')

# Сетки TP/SL
V3_GRID = [(0.004, 0.003), (0.006, 0.004), (0.008, 0.005), (0.006, 0.003), (0.008, 0.004)]
V4_GRID = [(0.001, 0.0005), (0.0015, 0.00075), (0.002, 0.001), (0.001, 0.001), (0.0015, 0.001)]

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def backup(path):
    if os.path.exists(path):
        shutil.copy(path, f'{path}.bak.{int(time.time())}')

def get_trades(db, last_n=100):
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("""SELECT symbol, side, entry_price, exit_price, pnl, entry_ts, exit_ts, tp, sl
                            FROM trades WHERE status='CLOSED'
                            ORDER BY exit_ts DESC LIMIT ?""", (last_n,)).fetchall()
        c.close()
        return rows
    except:
        return []

def recalc_pnl(trades, new_tp, new_sl):
    """Пересчитывает PnL для новых TP/SL (по entry/exit)."""
    n = 0; wins = 0; pnl = 0
    for t in trades:
        sym, side, ep, xp, pnl_v, ets, xts, tp, sl = t
        if ep is None or xp is None: continue
        # Пересчитываем: если движение вышло за новые TP/SL
        move = (xp - ep) / ep if side == 'LONG' else (ep - xp) / ep
        # Проверяем: если move >= new_tp → TP; если move <= -new_sl → SL
        if move >= new_tp:
            new_pnl = (new_tp - 0.0015) * 100  # FEE
        elif move <= -new_sl:
            new_pnl = (-new_sl - 0.0015) * 100
        else:
            new_pnl = (move - 0.0015) * 100
        n += 1
        if new_pnl > 0: wins += 1
        pnl += new_pnl
    wr = 100.0 * wins / n if n else 0
    return {'n': n, 'wins': wins, 'wr': wr, 'pnl': round(pnl, 2)}

def tune_for(db, cfg_path, grid, name):
    """Настраивает TP/SL для бота."""
    trades = get_trades(db, last_n=100)
    if len(trades) < 10:
        log(f'⚠️ {name}: мало сделок: {len(trades)} < 10 — не трогаем')
        return None

    log(f'{name}: сделок {len(trades)}')
    results = []
    for tp, sl in grid:
        r = recalc_pnl(trades, tp, sl)
        results.append({'tp': tp, 'sl': sl, **r})
        log(f'  TP={tp*100:.2f}% SL={sl*100:.2f}%: n={r["n"]}, WR={r["wr"]:.1f}%, PnL={r["pnl"]:+.2f}%')

    # Лучший: n >= 10, WR >= 50%, max PnL
    valid = [r for r in results if r['n'] >= 10 and r['wr'] >= 50]
    if not valid:
        log(f'⚠️ {name}: нет TP/SL с n>=10, WR>=50% — не меняем')
        return None

    best = max(valid, key=lambda x: x['pnl'])
    log(f'✅ {name}: лучший TP={best["tp"]*100:.2f}% SL={best["sl"]*100:.2f}% (n={best["n"]}, WR={best["wr"]:.1f}%, PnL={best["pnl"]:+.2f}%)')

    # Обновляем конфиг
    try:
        cur = json.load(open(cfg_path))
        backup(cfg_path)
        st = os.stat(cfg_path)
        need_restore = False
        if st.st_mode & stat.S_IWUSR == 0:
            os.chmod(cfg_path, 0o644)
            need_restore = True

        for sym, cfg in cur.get('per_pair', {}).items():
            if isinstance(cfg, dict) and 'strategy' in cfg:
                cfg['tp'] = best['tp']
                cfg['sl'] = best['sl']
            else:
                for reg, rc in cfg.items():
                    rc['tp'] = best['tp']
                    rc['sl'] = best['sl']
        cur['source'] = f'{name}_tuned'
        cur['updated_at'] = datetime.now().isoformat()
        json.dump(cur, open(cfg_path, 'w'), indent=2, ensure_ascii=False)
        log(f'✅ {name}: обновлён (TP={best["tp"]*100:.2f}%, SL={best["sl"]*100:.2f}%)')

        if need_restore:
            os.chmod(cfg_path, 0o444)
            log(f'✅ {name}: 444 восстановлен')
    except Exception as e:
        log(f'⚠️ {name}: {e}')
    return best

def main():
    log('=== AUTO TPSL TUNER ===')

    # v3 — свечной
    tune_for(DB_V3, V3_CFG, V3_GRID, 'v3')
    # v4 — скальпинг
    tune_for(DB_V4, V4_CFG, V4_GRID, 'v4')

    log('=== DONE ===')

if __name__ == '__main__':
    main()
