#!/usr/bin/env python3
import os, sqlite3, time
BASE = os.path.expanduser('~/quantum_lab')
KDB = os.path.join(BASE, 'data/knowledge.db')
def count_recent(kw, hours=24):
    try:
        c = sqlite3.connect(KDB)
        n = c.execute("SELECT COUNT(*) FROM knowledge WHERE (title LIKE ? OR content LIKE ?) AND ts > ?",
                      (f'%{kw}%', f'%{kw}%', int(time.time()) - hours*3600)).fetchone()[0]
        c.close(); return n
    except: return 0
def get_signals():
    s = []
    hacks = count_recent('hack') + count_recent('exploit') + count_recent('breach')
    if hacks >= 3: s.append({'type':'risk','reason':f'{hacks} упоминаний хаков за 24ч'})
    funding = count_recent('funding')
    if funding >= 5: s.append({'type':'info','reason':f'{funding} новостей про funding'})
    btc = count_recent('BTC') + count_recent('bitcoin')
    if btc >= 10: s.append({'type':'info','reason':f'{btc} новостей про BTC'})
    return s
if __name__ == '__main__':
    import json; print(json.dumps(get_signals(), indent=2))
