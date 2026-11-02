import re

with open('strategy_lab.py', 'r') as f:
    code = f.read()

# 1. Меняем build_indicator_prompt: теперь он принимает пороги
new_build = '''def build_indicator_prompt(history, long_thr, short_thr):
    return f"""Напиши ОДНУ функцию Python:
def my_indicator(prices):
    # ЗАДАЧА: Напиши ТОЛЬКО индикатор WILLIAMS %R.
    # Формула: (highest_high - close) / (highest_high - lowest_low) * -100
    # Период: 14.
    # ВАЖНО: Длина результата = len(prices). Первые 14 элементов = None.
    # ОПРЕДЕЛЯЙ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ВНУТРИ my_indicator, если нужно.
    return result_list

ТОЛЬКО код функции. Без markdown, без объяснений.
ПОРОГИ: LONG = {long_thr}, SHORT = {short_thr}"""'''

pattern = r"def build_indicator_prompt\(history\):.*?(?=def is_valid)"
code = re.sub(pattern, new_build, code, flags=re.DOTALL)

# 2. В main() генерируем случайные пороги и передаем их в build_indicator_prompt
old_main_part = '''    while True:
        iteration += 1
        log(f"\\n--- ИТЕРАЦИЯ {iteration} ---")'''
new_main_part = '''    import random
    while True:
        iteration += 1
        log(f"\\n--- ИТЕРАЦИЯ {iteration} ---")
        
        long_thr = random.choice([-90, -85, -80, -75, -70])
        short_thr = random.choice([-30, -25, -20, -15, -10])
        log(f"🎲 Пороги: LONG<{long_thr}, SHORT>{short_thr}")'''
code = code.replace(old_main_part, new_main_part)

# 3. Передаем пороги в build_indicator_prompt
code = code.replace('ind_func = ask_clean(build_indicator_prompt(history))', 'ind_func = ask_clean(build_indicator_prompt(history, long_thr, short_thr))')

# 4. Обновляем signal_prompt, чтобы использовал эти пороги
old_signal = '''signal_prompt = f"""Напиши ТОЛЬКО условие входа (if/elif) для индикатора WILLIAMS %R.
Переменные: i, prev_c, cur_c, ind_prev, ind_cur, pos, entry.
ЗНАЧЕНИЯ WILLIAMS: от -100 до 0.
Используй ровно эти пороги:
if ind_cur < {long_thr} and pos == 0:
    pos = 1
    entry = cur_c
elif ind_cur > {short_thr} and pos == 0:
    pos = -1
    entry = cur_c

ТОЛЬКО эти строки."""'''

# Если старый signal_prompt не найден, ищем любой блок signal_prompt и заменяем
if old_signal not in code:
    pattern2 = r'signal_prompt = f?""".*?КРИТИЧЕСКИ ВАЖНО: Вход ТОЛЬКО если pos == 0!.*?"""'
    new_signal = '''signal_prompt = f"""Напиши ТОЛЬКО условие входа (if/elif) для WILLIAMS %R.
Переменные: i, prev_c, cur_c, ind_prev, ind_cur, pos, entry.
ЗНАЧЕНИЯ WILLIAMS: от -100 до 0.
Используй ровно эти пороги:
if ind_cur < {long_thr} and pos == 0:
    pos = 1
    entry = cur_c
elif ind_cur > {short_thr} and pos == 0:
    pos = -1
    entry = cur_c

ТОЛЬКО эти строки."""'''
    code = re.sub(pattern2, new_signal, code, flags=re.DOTALL)

with open('strategy_lab.py', 'w') as f:
    f.write(code)

print("✅ strategy_lab.py исправлен (случайные пороги)")
