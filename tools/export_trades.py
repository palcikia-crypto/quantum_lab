#!/usr/bin/env python3
"""export_trades.py — выгрузка сделок paper-ботов в data/web_dashboard.json для веб-панели."""
import sqlite3, json, glob, os, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
OUT = os.path.join(DATA, 'web_dashboard.json')


def dump_db(path):
    name = os.path.basename(path).replace('.db', '')
    try:
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        rows = []
        if 'trades' in tables:
            rows = [dict(r) for r in c.execute("SELECT * FROM trades ORDER BY rowid DESC LIMIT 150")]
        c.close()
        return name, rows
    except Exception:
        return name, []


def main():
    bots, trades = {}, []
    dbs = sorted(glob.glob(os.path.join(DATA, 'pm_*.db'))) + \
          sorted(glob.glob(os.path.join(DATA, 'okx_paper_*.db')))
    for p in dbs:
        name, rows = dump_db(p)
        if not rows:
            continue
        pnls = [r.get('pnl') for r in rows
                if isinstance(r.get('pnl'), (int, float))]
        wins = [v for v in pnls if v > 0]
        bots[name] = {
            'trades': len(rows),
            'closed': sum(1 for r in rows if str(r.get('status', '')).upper() != 'OPEN'),
            'open': sum(1 for r in rows if str(r.get('status', '')).upper() == 'OPEN'),
            'pnl': round(sum(pnls), 2),
            'wr': round(100.0 * len(wins) / len(pnls), 1) if pnls else None,
        }
        for r in rows:
            r['_bot'] = name
            trades.append(r)
    trades.sort(key=lambda r: r.get('exit_ts') or r.get('entry_ts') or 0, reverse=True)
    out = {
        'updated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'bots': bots,
        'trades': trades[:300],
    }
    with open(OUT, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('exported %d trades from %d bots -> %s' % (len(trades), len(bots), OUT))


if __name__ == '__main__':
    main()
