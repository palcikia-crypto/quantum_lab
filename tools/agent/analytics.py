#!/usr/bin/env python3
"""Анализ памяти: адаптивные решения на основе истории."""
import os, sqlite3, json, time
from datetime import datetime

BASE = os.path.expanduser('~/quantum_lab')
MEM = os.path.join(BASE, 'tools/agent/memory.db')

def get_recent_facts(n=10):
    c = sqlite3.connect(MEM)
    rows = c.execute("SELECT ts, key, value FROM facts ORDER BY ts DESC LIMIT ?", (n*20,)).fetchall()
    c.close()
    return rows

def analyze_trend(key, n=5):
    """Смотрит, как менялся ключ за последние n циклов."""
    c = sqlite3.connect(MEM)
    rows = c.execute("SELECT ts, value FROM facts WHERE key=? ORDER BY ts DESC LIMIT ?", (key, n)).fetchall()
    c.close()
    if len(rows) < 2:
        return None
    vals = []
    for ts, v in rows:
        try: vals.append(float(v))
        except: pass
    if len(vals) < 2:
        return None
    # тренд: падает или растёт
    if vals[0] < vals[-1] * 0.8:
        return 'falling'
    elif vals[0] > vals[-1] * 1.2:
        return 'rising'
    return 'stable'

def check_adaptive():
    """Возвращает список адаптивных решений."""
    decisions = []
    # 1. PnL падает 3 цикла подряд → остановить v4
    pnl_trend = analyze_trend('pnl_24h', 3)
    if pnl_trend == 'falling':
        decisions.append({'action': 'stop_v4', 'reason': 'PnL_24h падает 3 цикла'})
    # 2. PnL растёт → ничего не делать
    elif pnl_trend == 'rising':
        decisions.append({'action': 'log', 'reason': 'PnL_24h растёт — всё ок'})
    # 3. ML proba насыщена 3 цикла → переобучить
    c = sqlite3.connect(MEM)
    ml_rows = c.execute("SELECT value FROM facts WHERE key='ml_bad' ORDER BY ts DESC LIMIT 3").fetchall()
    c.close()
    ml_bad_count = sum(1 for (v,) in ml_rows if v and v != '[]')
    if ml_bad_count >= 2:
        decisions.append({'action': 'retrain_ml', 'reason': 'ML proba насыщена 2+ цикла'})
    # 4. Новости: хаки → уведомить
    try:
        c = sqlite3.connect(os.path.join(BASE, 'data/knowledge.db'))
        hack_count = c.execute("SELECT COUNT(*) FROM knowledge WHERE content LIKE '%hack%' AND ts > ?", (int(time.time())-86400,)).fetchone()[0]
        c.close()
        if hack_count >= 3:
            decisions.append({'action': 'alert', 'reason': f'В новостях {hack_count} упоминаний хаков за 24ч'})
    except: pass
    return decisions

if __name__ == '__main__':
    print(json.dumps(check_adaptive(), indent=2))
