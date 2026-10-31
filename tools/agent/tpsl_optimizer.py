#!/usr/bin/env python3
"""Анализирует PnL и меняет TP/SL."""
import os, sqlite3, json
BASE = os.path.expanduser('~/quantum_lab')
def optimize():
    db = os.path.join(BASE, 'data/okx_paper_v4.db')
    if not os.path.exists(db): return
    c = sqlite3.connect(db)
    # лучший TP/SL по PnL
    rows = c.execute("""SELECT tp, sl, SUM(pnl) pnl, COUNT(*) n
                        FROM trades WHERE status='CLOSED'
                        GROUP BY tp, sl HAVING n > 20 ORDER BY pnl DESC LIMIT 1""").fetchone()
    c.close()
    if rows:
        tp, sl, pnl, n = rows
        print(f'✅ лучший TP/SL: tp={tp} sl={sl} pnl={pnl} n={n}')
        # тут можно записать в okx_tpsl_v4.json
        return {'tp': tp, 'sl': sl, 'pnl': pnl}
    return None
if __name__ == '__main__':
    optimize()
