import sys, os, re, subprocess
from pathlib import Path

SANDBOX = Path.home() / "quantum_lab_sandbox"
ORIGINAL = Path.home() / "quantum_lab"
FIXED_V2 = SANDBOX / "fixed_v2"
FIXED_V2.mkdir(exist_ok=True)
FAILED_FILE = SANDBOX / "FAILED_TO_FIX.txt"

def log(msg):
    print(msg, flush=True)

def has_syntax_errors(filepath):
    r = subprocess.run([sys.executable, "-m", "py_compile", str(filepath)], capture_output=True, text=True)
    return r.returncode != 0

def fix_open_calls(code):
    def repl(match):
        args = match.group(1)
        if "'rb'" in args or '"rb"' in args or "encoding=" in args:
            return match.group(0)
        if "'r'" in args:
            new_args = args.replace("'r'", "'r', encoding='utf-8'")
            return f"open({new_args})"
        elif '"r"' in args:
            new_args = args.replace('"r"', '"r", encoding="utf-8"')
            return f"open({new_args})"
        else:
            return f"open({args}, encoding='utf-8')"
    return re.sub(r'open\(([^\)]+)\)', repl, code)

def main():
    log("🚀 ФИКСЕР v2 (детерминированные фиксы, без ИИ)")
    if not FAILED_FILE.exists():
        log(f"❌ Файл {FAILED_FILE} не найден.")
        log("   Подожди, пока DevOps закончит — он создаст его заново.")
        return

    failed_files = FAILED_FILE.read_text().splitlines()
    log(f"📋 Файлов в очереди: {len(failed_files)}\n")

    for fpath in failed_files:
        fpath = fpath.strip()
        if not fpath: continue
        
        real = ORIGINAL / fpath
        if not real.exists():
            log(f"⏭️ {fpath}: Нет в оригинале")
            continue

        if has_syntax_errors(real):
            log(f"⚠️ {fpath}: Изначально сломан (SyntaxError). Пропуск.")
            continue

        code = real.read_text()
        orig_code = code

        code = re.sub(r'except\s*:', 'except Exception:', code)
        code = fix_open_calls(code)
        
        target = FIXED_V2 / real.name
        target.write_text(code)

        r = subprocess.run([sys.executable, "-m", "py_compile", str(target)], capture_output=True)
        
        if r.returncode == 0:
            if code != orig_code:
                log(f"✅ {fpath}: Исправлен")
            else:
                log(f"ℹ️ {fpath}: Проблем не найдено")
        else:
            log(f"❌ {fpath}: Синтаксис сломался. Откат.")
            if target.exists(): target.unlink()

    log("\n🎉 ГОТОВО! Результаты в fixed_v2/")

if __name__ == "__main__":
    main()
