import subprocess, time, shutil, os, sys
from pathlib import Path

SANDBOX = Path.home() / "quantum_lab_sandbox"
LAB = SANDBOX / "strategy_lab.py"
GOLD = SANDBOX / "strategy_lab_gold.py"
LOG_LAB = SANDBOX / ".strategy_lab.log"
LOG_GUARD = SANDBOX / ".guardian.log"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = "[" + ts + "] " + msg
    print(line, flush=True)
    try:
        with open(LOG_GUARD, "a") as f:
            f.write(line + chr(10))
    except: pass

def is_alive():
    r = subprocess.run(["pgrep", "-f", "strategy_lab"], capture_output=True)
    return r.returncode == 0

def start_lab():
    try:
        with open(SANDBOX / "strategy_lab.log", "w") as f: pass
        subprocess.Popen(
            ["python3", "strategy_lab.py"],
            cwd=SANDBOX,
            stdout=open(SANDBOX / "strategy_lab.log", "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        return True
    except Exception as e:
        log("start_err " + str(e))
        return False

def has_syntax_error():
    """Проверяет лог на SyntaxError."""
    try:
        if not LOG_LAB.exists(): return False
        txt = LOG_LAB.read_text()[-5000:]
        return "SyntaxError" in txt
    except: return False

def is_syntax_valid():
    """Проверяет что файл компилируется."""
    r = subprocess.run(["python3", "-m", "py_compile", str(LAB)], capture_output=True, text=True)
    return r.returncode == 0, r.stderr[:200]

def restore_from_gold():
    """Восстанавливает из эталона."""
    if not GOLD.exists():
        log("gold_missing")
        return False
    try:
        shutil.copy2(GOLD, LAB)
        log("restored_from_gold")
        return True
    except Exception as e:
        log("restore_err " + str(e))
        return False

def main():
    log("=== GUARDIAN START ===")
    if not GOLD.exists():
        log("WARN: gold_missing, создаю из текущего")
        if LAB.exists():
            shutil.copy2(LAB, GOLD)
    
    while True:
        time.sleep(60)
        
        if is_alive():
            continue
        
        log("lab_down")
        
        # Синтаксис OK?
        ok, err = is_syntax_valid()
        if ok:
            log("syntax_ok_restart")
            start_lab()
            time.sleep(10)
            if is_alive():
                log("restarted_ok")
            else:
                log("restart_failed")
        else:
            log("syntax_broken " + err[:100])
            if restore_from_gold():
                ok2, err2 = is_syntax_valid()
                if ok2:
                    log("restored_ok_restart")
                    start_lab()
                    time.sleep(10)
                    if is_alive():
                        log("restored_alive")
                    else:
                        log("restored_dead")
                else:
                    log("gold_also_broken " + err2[:100])

if __name__ == "__main__":
    main()
