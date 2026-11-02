import sys, os, subprocess, time, re, shutil
from pathlib import Path

sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))
from llm_backend import ask

SANDBOX = Path.home() / "quantum_lab_sandbox"
LOG = SANDBOX / ".lab_improver.log"
BACKUPS = SANDBOX / "infra_backups"
BACKUPS.mkdir(exist_ok=True)

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def backup(p):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = BACKUPS / f"{p.name}.improver.{ts}.bak"
    shutil.copy2(p, bak)
    return bak

def test_lab():
    """Запускает лабораторию на 8 сек, проверяет работоспособность."""
    try:
        proc = subprocess.Popen(
            ["python3", "strategy_lab.py"], cwd=SANDBOX,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        time.sleep(8)
        proc.terminate()
        try: out, _ = proc.communicate(timeout=2)
        except: proc.kill(); out = ""
        
        # Проверки
        if "SyntaxError" in out: return False, "SyntaxError"
        if "NameError" in out: return False, "NameError"
        if "Traceback" in out and "ИТЕРАЦИЯ" not in out: return False, "Traceback без итерации"
        if "ИТЕРАЦИЯ" not in out: return False, "Не дошло до итерации"
        return True, out[:200]
    except Exception as e:
        return False, str(e)

def improve_lab():
    log("\n🔧 IMPROVE: strategy_lab.py")
    p = SANDBOX / "strategy_lab.py"
    if not p.exists(): return False
    
    code = p.read_text()
    
    prompt = f"""Ты улучшаешь код лаборатории `strategy_lab.py`.

Текущий код:
{code[:4000]}

Задачи:
1. Добавь оптимизацию порогов: для WILLIAMS пробуй разные пороги (-80/-85/-90, -20/-15/-10).
2. Улучши detect_indicator: если индикатор = UNKNOWN, пробуй снова.
3. Добавь сохранение ВСЕХ попыток (не только рекорда) в GOLDEN_HISTORY.json.
4. НЕ ломай существующую логику (INDICATORS, TEMPLATE, main).

Выведи ТОЛЬКО полный код файла. Без markdown."""
    
    log("   🤖 Прошу DeepSeek улучшить...")
    new_code = ask(prompt, system_prompt="Пиши ТОЛЬКО код на чистом Python.")
    if not new_code: 
        log("   ❌ AI не ответил")
        return False
    
    new_code = new_code.replace("```python", "").replace("```", "").strip()
    
    # Проверка синтаксиса
    try:
        compile(new_code, str(p), "exec")
    except SyntaxError as e:
        log(f"   ❌ SyntaxError: {e}")
        return False
    
    # Защита от регрессии: длина кода не меньше 80% от оригинала
    if len(new_code) < len(code) * 0.7:
        log(f"   ❌ Новый код слишком короткий ({len(new_code)} vs {len(code)})")
        return False
    
    # Проверка на запрещённые библиотеки
    if any(x in new_code for x in ["pandas", "numpy", "talib"]):
        log(f"   ❌ AI добавил запрещённую библиотеку")
        return False
    
    # Бэкап
    bak = backup(p)
    log(f"   💾 Бэкап: {bak.name}")
    
    # Запись
    p.write_text(new_code)
    log("   🧪 Тестируем 8 сек...")
    
    ok, msg = test_lab()
    if ok:
        log(f"   ✅ Работает: {msg[:80]}")
        return True
    else:
        log(f"   ❌ Тест упал: {msg[:80]}")
        shutil.copy2(bak, p)
        log(f"   🔄 Откат из {bak.name}")
        return False

def main():
    log("=" * 60)
    log("LAB IMPROVER: улучшаем код лаборатории через ИИ")
    log("=" * 60)
    
    # Останавливаем лабораторию
    subprocess.run(["pkill", "-9", "-f", "strategy_lab"], capture_output=True)
    time.sleep(2)
    
    iteration = 0
    while True:
        iteration += 1
        log(f"\n{'='*40}")
        log(f"ИТЕРАЦИЯ {iteration}")
        log(f"{'='*40}")
        
        if improve_lab():
            log(f"\n✅ Улучшение #{iteration} применено!")
        else:
            log(f"\n❌ Улучшение #{iteration} отклонено")
        
        # Перезапускаем лабораторию
        log(f"\n🚀 Перезапускаю лабораторию...")
        with open(SANDBOX / "strategy_lab.log", "w") as f: pass
        subprocess.Popen(
            ["python3", "strategy_lab.py"], cwd=SANDBOX,
            stdout=open(SANDBOX / "strategy_lab.log", "w"),
            stderr=subprocess.STDOUT, start_new_session=True
        )
        log(f"   ✅ Запущена")
        
        log(f"\n💤 Пауза 5 минут...")
        time.sleep(300)

if __name__ == "__main__":
    main()
