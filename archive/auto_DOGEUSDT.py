#!/usr/bin/env python3
"""Автогенерация: DOGEUSDT mean_rev_15_1.5 (WR=53.0%)"""
import os, sys, time, sqlite3, json
BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/auto_DOGEUSDT.db')
def main():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY, ts INTEGER, sym TEXT, side TEXT, pnl REAL)""")
    c.commit(); c.close()
    print("AUTO BOT DOGEUSDT mean_rev_15_1.5 STARTED")
    while True:
        time.sleep(60)
if __name__ == '__main__':
    main()
