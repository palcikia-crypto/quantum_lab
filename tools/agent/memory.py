#!/usr/bin/env python3
"""Память агента: facts, actions, experience, weights + pending."""
import os, json, sqlite3, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
DB = os.path.join(BASE, 'tools/agent/memory.db')

def init():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, key TEXT, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, action TEXT, target TEXT, result TEXT, success INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS experience (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, action TEXT, context TEXT, outcome TEXT, score REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS weights (
        id INTEGER PRIMARY KEY AUTOINCREMENT, rule TEXT UNIQUE, weight REAL DEFAULT 1.0, fires INTEGER DEFAULT 0, success INTEGER DEFAULT 0)""")
    # pending: действия, результат которых ещё не проверен
    c.execute("""CREATE TABLE IF NOT EXISTS pending (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, action TEXT, target TEXT, rule TEXT, context TEXT, check_at INTEGER, check_type TEXT)""")
    c.commit(); c.close()

def save_fact(key, value):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO facts (ts, key, value) VALUES (?,?,?)", (int(time.time()), key, str(value)))
    c.commit(); c.close()

def save_action(action, target, result, success):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO actions (ts, action, target, result, success) VALUES (?,?,?,?,?)",
              (int(time.time()), action, target, str(result)[:500], int(success)))
    c.commit(); c.close()

def save_experience(action, context, outcome, score):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO experience (ts, action, context, outcome, score) VALUES (?,?,?,?,?)",
              (int(time.time()), action, str(context)[:500], str(outcome)[:100], float(score)))
    c.commit(); c.close()

def get_rule_weight(rule):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT weight, fires, success FROM weights WHERE rule=?", (rule,)).fetchone()
    c.close()
    return r if r else (1.0, 0, 0)

def update_rule_weight(rule, success):
    c = sqlite3.connect(DB)
    cur = c.execute("SELECT weight, fires, success FROM weights WHERE rule=?", (rule,)).fetchone()
    if cur:
        w, f, s = cur
        new_f = f + 1
        new_s = s + (1 if success else 0)
        new_w = max(0.1, min(2.0, w + (0.1 if success else -0.1)))
        c.execute("UPDATE weights SET weight=?, fires=?, success=? WHERE rule=?", (new_w, new_f, new_s, rule))
    else:
        c.execute("INSERT INTO weights (rule, weight, fires, success) VALUES (?,?,?,?)",
                  (rule, 1.1 if success else 0.9, 1, 1 if success else 0))
    c.commit(); c.close()

def get_experience(action, limit=20):
    """Возвращает статистику по действию: total, success, fail, avg_score, last_score."""
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT outcome, score FROM experience WHERE action=? ORDER BY ts DESC LIMIT ?",
                     (action, limit)).fetchall()
    c.close()
    if not rows:
        return {'total': 0, 'success': 0, 'fail': 0, 'avg_score': 0, 'last_score': 0}
    success = sum(1 for o, s in rows if o == 'success')
    fail = len(rows) - success
    avg = sum(s for o, s in rows) / len(rows)
    return {'total': len(rows), 'success': success, 'fail': fail,
            'avg_score': round(avg, 2), 'last_score': rows[0][1]}

def add_pending(action, target, rule, context, check_at, check_type):
    """Добавляет действие, результат которого надо проверить позже."""
    c = sqlite3.connect(DB)
    c.execute("""INSERT INTO pending (ts, action, target, rule, context, check_at, check_type)
                 VALUES (?,?,?,?,?,?,?)""",
              (int(time.time()), action, target, rule, str(context)[:500], int(check_at), check_type))
    c.commit(); c.close()

def get_pending_ready():
    """Возвращает pending, которые пора проверить."""
    c = sqlite3.connect(DB)
    rows = c.execute("""SELECT id, action, target, rule, context, check_type
                        FROM pending WHERE check_at <= ?""", (int(time.time()),)).fetchall()
    c.close()
    return rows

def resolve_pending(pending_id, success, score):
    """Закрывает pending: записывает experience + обновляет вес."""
    c = sqlite3.connect(DB)
    row = c.execute("SELECT action, rule, context FROM pending WHERE id=?", (pending_id,)).fetchone()
    if row:
        action, rule, context = row
        c.execute("DELETE FROM pending WHERE id=?", (pending_id,))
        c.commit(); c.close()
        outcome = 'success' if success else 'fail'
        save_experience(rule, {'check': context[:200]}, outcome, score)
        update_rule_weight(rule, success)
        return True
    c.close()
    return False

def stats():
    c = sqlite3.connect(DB)
    d = {
        'facts': c.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
        'actions': c.execute("SELECT COUNT(*) FROM actions").fetchone()[0],
        'experience': c.execute("SELECT COUNT(*) FROM experience").fetchone()[0],
        'weights': c.execute("SELECT COUNT(*) FROM weights").fetchone()[0],
        'pending': c.execute("SELECT COUNT(*) FROM pending").fetchone()[0],
    }
    c.close()
    return d

if __name__ == '__main__':
    init()
    print(stats())
