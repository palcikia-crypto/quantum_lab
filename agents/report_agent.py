#!/usr/bin/env python3
import os, json, sqlite3
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab'); REPORTS = os.path.join(BASE, 'reports')
RSBOT = os.path.expanduser('~/rsbot'); LOG = os.path.join(BASE, 'logs/report_agent.log')
def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')
def daily():
    today = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, f'daily_{today}.md')
    lines = [f'# Отчёт за {today}\n', f'## Боты\n']
    for db in ['pm_bot.db','pm_v3.db','pm_v4.db','pm_v5.db','pm_v6.db','pm_v7.db']:
        p = os.path.join(RSBOT, db)
        if not os.path.exists(p): continue
        try:
            c = sqlite3.connect(p)
            r = c.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(pnl),0),2) FROM trades").fetchone()
            c.close()
            lines.append(f'- {db}: {r[0]} сделок, PnL=${r[1]}\n')
        except: pass
    with open(path, 'w') as f: f.writelines(lines)
    log(f'daily: {path}')
def main():
    log('=== REPORT AGENT ===')
    daily()
if __name__ == '__main__': main()
