#!/usr/bin/env python3
"""auto_compare.py — сравнение ботов v2/v3/v4."""
import os, json, sqlite3
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
OUT = os.path.join(BASE, 'data/compare_report.json')

def get_stats(db):
    try:
        c = sqlite3.connect(db, timeout=5)
        r = c.execute("""SELECT COUNT(*), SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END),
                         ROUND(SUM(pnl),2) FROM trades WHERE status='CLOSED'""").fetchone()
        c.close()
        if r and r[0]:
            n, wins, pnl = r
            return {'n': n, 'wins': wins or 0, 'wr': round(100.0*(wins or 0)/n, 1), 'pnl': pnl or 0}
    except Exception:
        pass
    return {'n': 0, 'wins': 0, 'wr': 0, 'pnl': 0}

def main():
    print(f'=== AUTO COMPARE {datetime.now():%H:%M:%S} ===')
    bots = {
        'v2': os.path.join(BASE, 'data/okx_paper.db'),
        'v3': os.path.join(BASE, 'data/okx_paper_v3.db'),
        'v4': os.path.join(BASE, 'data/okx_paper_v4.db'),
    }
    result = {}
    for name, db in bots.items():
        s = get_stats(db)
        result[name] = s
        print(f'  {name}: n={s["n"]}, WR={s["wr"]}%, PnL=${s["pnl"]}')

    best = max(result.items(), key=lambda x: x[1]['pnl']) if result else None
    out = {
        'updated_at': datetime.now().isoformat(),
        'bots': result,
        'best_pnl': best[0] if best else None,
        'best_pnl_value': best[1]['pnl'] if best else 0,
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print(f'✅ Лучший по PnL: {best[0] if best else "—"}')
    print(f'✅ Записано: {OUT}')

if __name__ == '__main__':
    main()
