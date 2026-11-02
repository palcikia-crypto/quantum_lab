#!/usr/bin/env python3
"""auto_stop_losers.py — автоостановка убыточных ботов."""
import os, json, sqlite3, time, subprocess
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
LOG = os.path.join(BASE, 'logs/auto_stop_losers.log')

BOTS = {
    'v2': {'db': os.path.join(BASE, 'data/okx_paper.db'), 'proc': 'okx_bot_paper_v2', 'min_wr': 40},
    'v3': {'db': os.path.join(BASE, 'data/okx_paper_v3.db'), 'proc': 'okx_bot_paper_v3', 'min_wr': 40},
    'v4': {'db': os.path.join(BASE, 'data/okx_paper_v4.db'), 'proc': 'okx_bot_paper_v4', 'min_wr': 35},
}

def log(msg):
    line = f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_wr(db, last_n=20):
    try:
        c = sqlite3.connect(db, timeout=5)
        rows = c.execute("""SELECT pnl FROM trades WHERE status='CLOSED'
                            ORDER BY exit_ts DESC LIMIT ?""", (last_n,)).fetchall()
        c.close()
        if not rows: return None, 0
        wins = sum(1 for r in rows if r[0] and r[0] > 0)
        return 100.0 * wins / len(rows), len(rows)
    except Exception:
        return None, 0

def main():
    log('=== AUTO STOP LOSERS ===')
    for name, cfg in BOTS.items():
        wr, n = get_wr(cfg['db'], 20)
        if wr is None:
            log(f'{name}: нет сделок')
            continue
        log(f'{name}: WR={wr:.1f}% ({n} сделок)')
        if wr < cfg['min_wr'] and n >= 10:
            log(f'❌ {name} WR={wr:.1f}% < {cfg["min_wr"]}% → останавливаем')
            pid = subprocess.run(['pgrep','-f',cfg['proc']], capture_output=True, text=True)
            if pid.stdout.strip():
                for p in pid.stdout.strip().split('\n'):
                    subprocess.run(['kill','-9',p], capture_output=True)
                    log(f'  {name} PID {p} убит')
        else:
            log(f'✅ {name} OK')

    log('=== AUTO STOP LOSERS DONE ===')

if __name__ == '__main__':
    main()
