#!/usr/bin/env python3
"""ai_generator.py — LLM создаёт новые sig_*. Через tgpt. Безопасно."""
import os, sys, json, subprocess, re, ast
from datetime import datetime
BASE = os.path.expanduser('~/quantum_lab')
AI_FILE = os.path.join(BASE, 'core/ai_strategies.py')
LOG = os.path.join(BASE, 'logs/ai_generator.log')

def log(m):
    line = f'[{datetime.now():%H:%M:%S}] {m}'
    print(line, flush=True)
    with open(LOG, 'a') as f: f.write(line+'\n')

def call_llm(prompt):
    try:
        r = subprocess.run(['tgpt','--provider','pollinations','-q',prompt], capture_output=True, text=True, timeout=90)
        return r.stdout.strip() if r.returncode == 0 else None
    except: return None

def extract_code(resp):
    if not resp: return None
    # Убираем markdown
    resp = resp.replace('```python', '').replace('```py', '').replace('```', '')
    lines = resp.split('\n')
    # Ищем def sig_ и собираем до return up, dn
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith('def sig_'):
            start = i
            break
    if start is None: return None
    # Собираем до return up, dn (включая вложенные def)
    code = []
    for line in lines[start:]:
        code.append(line)
        if line.strip() == 'return up, dn':
            break
    if not code: return None
    result = '\n'.join(code)
    # Проверяем: есть return up, dn
    if 'return up, dn' not in result: return None
    return result
def validate(code):
    if not code: return False
    try:
        ast.parse(code)
        return 'def sig_' in code and 'return up, dn' in code
    except: return False

def main():
    log('=== AI GENERATOR START ===')
    prompt = """Создай УНИКАЛЬНУЮ торговую стратегию на Python.

Формат:
def sig_ai_strategy(o, h, l, c, v, ind):
    up = np.zeros(len(c), dtype=bool)
    dn = np.zeros(len(c), dtype=bool)
    # ТВОЯ ЛОГИКА
    return up, dn

Требования:
- Комбинируй RSI + EMA + объём (2+ индикатора)
- НЕ используй sma20 (это шаблон)
- Придумай СВОЮ логику
- Верни ТОЛЬКО код, без markdown, без объяснений"""
    resp = call_llm(prompt)
    if not resp:
        log('tgpt недоступен или ошибка'); return
    code = extract_code(resp)
    if not code or not validate(code):
        log('код невалиден'); return
    if not os.path.exists(AI_FILE):
        with open(AI_FILE, 'w') as f: f.write('import numpy as np\n\n')
    with open(AI_FILE, 'a') as f: f.write('\n' + code + '\n')
    log('новая стратегия добавлена')

if __name__ == '__main__': main()
