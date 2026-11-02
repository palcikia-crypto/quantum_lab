import sys, os, subprocess, time, shutil, re
from pathlib import Path

sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))
from llm_backend import ask

SANDBOX = Path.home() / "quantum_lab_sandbox"
ORIGINAL = Path.home() / "quantum_lab"
LOG = SANDBOX / ".devops.log"
FIXED_DIR = SANDBOX / "fixed"
FIXED_DIR.mkdir(exist_ok=True)
IMPROVEMENTS = ORIGINAL / "IMPROVEMENTS.md"
TEST_DIR = SANDBOX / "test"
TEST_DIR.mkdir(exist_ok=True)
FAILED_FILE = SANDBOX / "FAILED_TO_FIX.txt"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def parse_improvements():
    if not IMPROVEMENTS.exists(): return []
    text = IMPROVEMENTS.read_text()
    files = []
    for match in re.finditer(r"## 📄 (.+?)\n", text):
        fpath = match.group(1).strip()
        start = match.end()
        end = text.find("---", start)
        if end == -1: end = len(text)
        block = text[start:end].strip()
        if block and len(block) > 20:
            files.append({"path": fpath, "problems": block[:800]})
    return files

def check_syntax(filepath):
    r = subprocess.run([sys.executable, "-m", "py_compile", str(filepath)], capture_output=True, text=True, timeout=30)
    return r.returncode == 0, r.stderr[-300:]

def main():
    log("🚀 DEVOPS v7: Быстрый проход (макс 2 попытки на файл)")
    problems = parse_improvements()
    
    if FAILED_FILE.exists():
        FAILED_FILE.unlink() # Очищаем старый список ошибок

    for i, item in enumerate(problems, 1):
        real = ORIGINAL / item['path']
        fixed_target = FIXED_DIR / real.name
        
        if fixed_target.exists():
            continue # Молча пропускаем готовые

        log(f"\n--- [{i}/{len(problems)}] {item['path']} ---")
        if not real.exists(): continue
        
        original_code = real.read_text()
        if len(original_code) > 4000:
            log("   ⚠️ Файл слишком большой. Пропуск.")
            continue

        prompt = f"""Ты — Senior Python разработчик. Файл: `{item['path']}`
Проблемы: {item['problems']}
Код: {original_code}
ЗАДАЧА: Исправь ТОЛЬКО найденные проблемы. Выведи ТОЛЬКО полный код. Без markdown."""

        log("   🤖 Прошу ИИ исправить...")
        fixed = ask(prompt, system_prompt="Ты пишешь чистый Python код.").replace("```python", "").replace("```", "").strip()

        if any(lib in fixed for lib in ["pandas", "numpy", "talib"]):
            log("   ⛔ Запрещенная библиотека. Пропуск.")
            time.sleep(10)
            continue

        # ЦИКЛ АВТОФИКСА (всего 2 попытки, чтобы не застревать)
        test_file = TEST_DIR / real.name
        success = False
        for attempt in range(1, 3):
            test_file.write_text(fixed)
            ok, err = check_syntax(test_file)
            
            if ok:
                log(f"   ✅ Синтаксис OK! (попытка {attempt}). Сохраняю.")
                (FIXED_DIR / real.name).write_text(fixed)
                success = True
                break
            else:
                log(f"   ❌ Сломан синтаксис (попытка {attempt}/2): {err.splitlines()[-1][:50]}")
                if attempt == 1:
                    log("   🔧 Автофикс...")
                    fixed = ask(f"Ошибка:\n{err}\nКод:\n{fixed}\nИсправь и верни ТОЛЬКО код.", system_prompt="Исправь ошибки.").replace("```python", "").replace("```", "").strip()
                    time.sleep(5)

        if not success:
            log("   ❌ Сдаемся на этом файле. Записываем в FAILED_TO_FIX.txt")
            with open(FAILED_FILE, "a") as f:
                f.write(f"{item['path']}\n")

        log("   💤 Пауза 15с...")
        time.sleep(15)

    log("\n🎉 ВСЕ ФАЙЛЫ ОБРАБОТАНЫ.")

if __name__ == "__main__":
    main()
