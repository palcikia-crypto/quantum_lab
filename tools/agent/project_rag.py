#!/usr/bin/env python3
"""RAG по проекту: индексирует код, конфиги, логи. Поиск по запросу."""
import os, sqlite3, time, sys
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'data/project_knowledge.db')
LOG = os.path.join(BASE, 'logs/agent.log')

def log(m):
    with open(LOG, 'a') as f:
        f.write(f'[{datetime.now():%H:%M:%S}] [rag] {m}\n')

def init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER, path TEXT, category TEXT, content TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_path ON docs(path)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cat ON docs(category)")
    c.commit(); c.close()

def index_file(path, category):
    try:
        content = open(path, 'r', errors='ignore').read()
        if len(content) < 10: return 0
        c = sqlite3.connect(DB)
        c.execute("DELETE FROM docs WHERE path=?", (path,))
        c.execute("INSERT INTO docs (ts, path, category, content) VALUES (?,?,?,?)",
                  (int(time.time()), path, category, content[:200000]))
        c.commit(); c.close()
        return 1
    except: return 0

def index_all():
    init()
    n = 0
    # код core/
    for root, dirs, files in os.walk(os.path.join(BASE, 'core')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                n += index_file(os.path.join(root, f), 'code')
    # код agents/
    for root, dirs, files in os.walk(os.path.join(BASE, 'agents')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                n += index_file(os.path.join(root, f), 'code')
    # код tools/agent/
    for root, dirs, files in os.walk(os.path.join(BASE, 'tools/agent')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                n += index_file(os.path.join(root, f), 'code')
    # конфиги
    for f in ['config/lab.json', 'data/okx_tpsl_v4.json', 'tools/agent/rules.json']:
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            n += index_file(p, 'config')
    # логи (последние 1000 строк)
    for f in ['logs/agent.log', 'logs/okx_bot_paper_v4.log', 'logs/brain_loop.log', 'logs/ml_online.log']:
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            try:
                lines = open(p, 'r', errors='ignore').readlines()[-1000:]
                content = ''.join(lines)
                c = sqlite3.connect(DB)
                c.execute("DELETE FROM docs WHERE path=?", (p,))
                c.execute("INSERT INTO docs (ts, path, category, content) VALUES (?,?,?,?)",
                          (int(time.time()), p, 'log', content))
                c.commit(); c.close()
                n += 1
            except: pass
    log(f'indexed: {n}')
    return n

def search(query, limit=5, category=None):
    c = sqlite3.connect(DB)
    if category:
        rows = c.execute("SELECT path, category, substr(content, 1, 800) FROM docs WHERE content LIKE ? AND category=? LIMIT ?",
                         (f'%{query}%', category, limit)).fetchall()
    else:
        rows = c.execute("SELECT path, category, substr(content, 1, 800) FROM docs WHERE content LIKE ? LIMIT ?",
                         (f'%{query}%', limit)).fetchall()
    c.close()
    return rows

def stats():
    c = sqlite3.connect(DB)
    n = c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    cats = c.execute("SELECT category, COUNT(*) FROM docs GROUP BY category").fetchall()
    c.close()
    return {'total': n, 'by_cat': dict(cats)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        n = index_all()
        print(f'✅ проиндексировано: {n} файлов')
        print(f'📊 статистика: {stats()}')
    else:
        q = ' '.join(sys.argv[1:])
        print(f'🔍 поиск: "{q}"')
        for path, cat, frag in search(q):
            print(f'\n=== {path} ({cat}) ===')
            print(frag[:500])
