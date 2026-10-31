#!/usr/bin/env python3
"""Генерирует бота по шаблону из evolution.json."""
import os, json, sqlite3, time
BASE = os.path.expanduser('~/quantum_lab')

def get_gold():
    p = os.path.join(BASE, 'data/evolution.json')
    if not os.path.exists(p): return None
    d = json.load(open(p))
    top = d.get('top', [])
    if not top: return None
    # лучшая по WR
    best = max(top, key=lambda x: x.get('wr', 0))
    return best

def generate_bot(gold):
    sym = gold['symbol']
    strat = gold['strategy']
    wr = gold['wr']
    # шаблон простого бота
    code = f'''#!/usr/bin/env python3
"""Автогенерация: {sym} {strat} (WR={wr}%)"""
import os, sys, time, sqlite3, json
BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/auto_{sym}.db')
def main():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY, ts INTEGER, sym TEXT, side TEXT, pnl REAL)""")
    c.commit(); c.close()
    print("AUTO BOT {sym} {strat} STARTED")
    while True:
        time.sleep(60)
if __name__ == '__main__':
    main()
'''
    path = os.path.join(BASE, f'core/auto_{sym}.py')
    open(path, 'w').write(code)
    return path

if __name__ == '__main__':
    gold = get_gold()
    if gold:
        path = generate_bot(gold)
        print(f'✅ generated: {path}')
        print(f'   {gold["symbol"]} {gold["strategy"]} WR={gold["wr"]}%')
    else:
        print('❌ нет золота в evolution.json')
