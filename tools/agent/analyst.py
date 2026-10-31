#!/usr/bin/env python3
"""Аналитик: читает логи, БД, находит узкие места и выдаёт план."""
import os, json, sqlite3, subprocess, re
from datetime import datetime, timedelta

BASE = os.path.expanduser('~/quantum_lab')
DATA = os.path.join(BASE, 'data')
LOGS = os.path.join(BASE, 'logs')

def read_log(name, lines=200):
    p = os.path.join(LOGS, name)
    if not os.path.exists(p): return []
    try: return open(p, 'r', errors='ignore').readlines()[-lines:]
    except: return []

def count_errors(log_lines):
    return sum(1 for l in log_lines if 'ERROR' in l or 'Traceback' in l)

def db_stats(db, table, ts_col='ts'):
    p = os.path.join(DATA, db)
    if not os.path.exists(p): return {}
    try:
        c = sqlite3.connect(p)
        n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        mn = c.execute(f"SELECT MIN({ts_col}) FROM {table}").fetchone()[0]
        mx = c.execute(f"SELECT MAX({ts_col}) FROM {table}").fetchone()[0]
        c.close()
        days = (mx - mn) / 86400 if mn and mx else 0
        return {'rows': n, 'oldest': mn, 'newest': mx, 'days': round(days, 1)}
    except Exception as e:
        return {'error': str(e)}

def v4_stats():
    p = os.path.join(DATA, 'okx_paper_v4.db')
    if not os.path.exists(p): return {}
    try:
        c = sqlite3.connect(p)
        r = c.execute("""SELECT COUNT(*), ROUND(SUM(pnl),2),
                         ROUND(100.0*SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)/COUNT(*),1),
                         ROUND(AVG(pnl),3)
                         FROM trades WHERE status='CLOSED'""").fetchone()
        c.close()
        return {'trades': r[0], 'pnl': r[1], 'wr': r[2], 'avg': r[3]}
    except: return {}

def gold_stats():
    p = os.path.join(DATA, 'evolution.json')
    if not os.path.exists(p): return []
    try:
        d = json.load(open(p))
        return d.get('top', [])[:10]
    except: return []

def analyze():
    report = []
    report.append('=' * 60)
    report.append(f'АНАЛИЗ ЛАБОРАТОРИИ: {datetime.now():%Y-%m-%d %H:%M:%S}')
    report.append('=' * 60)
    report.append('')

    # 1. Логи: ошибки
    report.append('--- 1. ЛОГИ: ОШИБКИ ---')
    for log in ['agent.log', 'okx_bot_paper_v4.log', 'brain_loop.log', 'ml_online.log', 'data_manager.log']:
        lines = read_log(log, 500)
        errs = count_errors(lines)
        status = '✅' if errs == 0 else f'⚠️ {errs}'
        report.append(f'  {log}: {len(lines)} строк, ошибок: {status}')
    report.append('')

    # 2. БД: сколько данных
    report.append('--- 2. БАЗЫ ДАННЫХ: СКОЛЬКО ДАННЫХ ---')
    for db, table in [('market.db', 'candles'), ('oracle.db', 'regime'), ('orderbook.db', 'orderbooks')]:
        s = db_stats(db, table)
        if 'error' in s:
            report.append(f'  {db}: ❌ {s["error"]}')
        else:
            report.append(f'  {db}: {s["rows"]} строк, {s["days"]} дней истории')
    report.append('')

    # 3. v4: PnL
    report.append('--- 3. ТОРГОВЛЯ v4 ---')
    v = v4_stats()
    if v:
        report.append(f'  Сделок: {v.get("trades")}, PnL: {v.get("pnl")}, WR: {v.get("wr")}%, avg: {v.get("avg")}')
    else:
        report.append('  ❌ нет данных')
    report.append('')

    # 4. Золото из эволюции
    report.append('--- 4. ЗОЛОТО (evolution.json) ---')
    gold = gold_stats()
    if gold:
        for g in gold[:5]:
            report.append(f'  {g.get("symbol")} {g.get("strategy")}: WR={g.get("wr")}% n={g.get("n")} exp={g.get("expectancy")}')
    else:
        report.append('  ❌ evolution.json пуст или нет')
    report.append('')

    # 5. Чего не хватает для бэктеста
    report.append('--- 5. ЧЕГО НЕ ХВАТАЕТ ДЛЯ БЭКТЕСТА ---')
    m = db_stats('market.db', 'candles')
    if m and 'days' in m:
        if m['days'] < 365:
            report.append(f'  ⚠️ market.db: только {m["days"]} дней. Для бэктеста за 1-2 года нужно скачать ещё {365 - int(m["days"])}+ дней.')
        else:
            report.append(f'  ✅ market.db: {m["days"]} дней — достаточно для 1 года бэктеста.')
    report.append('')

    # 6. План действий
    report.append('--- 6. ПЛАН ДЕЙСТВИЙ ---')
    plan = []
    if v and v.get('pnl', 0) < 0:
        plan.append('  🔴 v4 в минусе — остановить или пересмотреть TP/SL')
    if gold:
        plan.append(f'  🟡 Золото: {gold[0].get("symbol")} {gold[0].get("strategy")} (WR={gold[0].get("wr")}%) — подключить к торговле')
    if m and m.get('days', 0) < 365:
        plan.append(f'  🟡 Скачать историю: нужно {365 - int(m["days"])}+ дней для бэктеста')
    plan.append('  🟢 Агент v6 работает — следит, чинит, учится')
    for p in plan:
        report.append(p)
    report.append('')
    report.append('=' * 60)
    return '\n'.join(report)

if __name__ == '__main__':
    out = analyze()
    print(out)
    # сохраняем
    p = os.path.join(BASE, 'logs/analyst_report.txt')
    open(p, 'w').write(out)
    print(f'\n📄 сохранено: {p}')
