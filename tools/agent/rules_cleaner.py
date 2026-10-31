#!/usr/bin/env python3
"""Удаляет правила, которые не работают."""
import os, json, sqlite3
BASE = os.path.expanduser('~/quantum_lab')
MEM = os.path.join(BASE, 'tools/agent/memory.db')
RULES = os.path.join(BASE, 'tools/agent/rules.json')
def clean():
    c = sqlite3.connect(MEM)
    rows = c.execute("""SELECT action, AVG(score), COUNT(*) FROM experience
                        GROUP BY action HAVING COUNT(*) >= 3""").fetchall()
    c.close()
    bad = [r for r, s, n in rows if s < -0.5 and n >= 3]
    if not bad: return
    rules = json.load(open(RULES))
    new_rules = [r for r in rules if r.get('name') not in bad]
    if len(new_rules) < len(rules):
        json.dump(new_rules, open(RULES, 'w'), indent=2, ensure_ascii=False)
        print(f'✅ удалено правил: {len(rules) - len(new_rules)} ({bad})')
if __name__ == '__main__':
    clean()
