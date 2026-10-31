#!/usr/bin/env python3
"""auto_filter.py — автонастройка фильтров по live-сделкам."""
import os, json, sqlite3, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB_V2 = os.path.join(BASE, 'data/okx_paper.db')
DB_V3 = os.path.join(BASE, 'data/okx_paper_v3.db')
DB_V4 = os.path.join(BASE, 'data/okx_paper_v4.db')
POLICY = os.path.join(BASE, 'data/okx_policy.json')

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(os.path.join(BASE, 'logs/auto_filter.log'), 'a') as f:
        f.write(line + '\n')

def get_wr(db, last_n=20):
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("""SELECT pnl FROM trades WHERE status='CLOSED'
                            ORDER BY exit_ts DESC LIMIT ?""", (last_n,)).fetchall()
        c.close()
        if not rows: return None
        wins = sum(1 for r in rows if r[0] and r[0] > 0)
        return 100.0 * wins / len(rows)
    except:
        return None

def main():
    log('=== AUTO FILTER ===')
    for name, db in [('v2', DB_V2), ('v3', DB_V3), ('v4', DB_V4)]:
        wr = get_wr(db, 20)
        log(f'{name}: WR={wr:.1f}%' if wr else f'{name}: нет данных')

    try:
        pol = json.load(open(POLICY))
        v2_wr = get_wr(DB_V2, 20)
        if v2_wr is not None:
            if v2_wr < 40:
                pol['filter'] = {'enabled': True, 'adx_threshold': 40}
                log(f'v2 WR={v2_wr:.1f}% < 40 → включаем фильтр')
            elif v2_wr > 55:
                pol['filter'] = {'enabled': False}
                log(f'v2 WR={v2_wr:.1f}% > 55 → выключаем фильтр')
            pol['updated_at'] = datetime.now().isoformat()
            pol['source'] = 'auto_filter'
            json.dump(pol, open(POLICY, 'w'), indent=2, ensure_ascii=False)
            log('✅ policy обновлён')
    except Exception as e:
        log(f'⚠️ policy: {e}')

    log('=== AUTO FILTER DONE ===')

if __name__ == '__main__':
    main()
