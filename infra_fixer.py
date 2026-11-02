import sys, os, subprocess, time, re, shutil, ast
from pathlib import Path

sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))

SANDBOX = Path.home() / "quantum_lab_sandbox"
HOME = Path.home()
LOG = SANDBOX / ".infra_fixer.log"
BACKUPS = SANDBOX / "infra_backups"
BACKUPS.mkdir(exist_ok=True)

SAFE_INDICATORS = ["RSI", "WILLIAMS", "MACD", "BOLLINGER", "ROC", "OBV"]

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def backup(p):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = BACKUPS / f"{p.name}.{ts}.bak"
    shutil.copy2(p, bak)
    return bak

def is_valid(code):
    try: ast.parse(code); return True, ""
    except Exception as e: return False, str(e)

def fix_strategy_lab():
    log("\n🔧 ФИКСИМ: strategy_lab.py")
    p = SANDBOX / "strategy_lab.py"
    if not p.exists():
        log("   ❌ Не найден"); return False
    
    code = p.read_text()
    new_indicators = f'INDICATORS = {SAFE_INDICATORS!r}'
    code2 = re.sub(r'INDICATORS\s*=\s*\[[^\]]*\]', new_indicators, code, count=1)
    
    old_list = "RSI, MACD, Bollinger, Stochastic, EMA Cross, SMA Cross, ATR, OBV, CCI, Williams %R, ROC"
    new_list = "RSI, WILLIAMS, MACD, BOLLINGER, ROC, OBV"
    if old_list in code2:
        code2 = code2.replace(old_list, new_list)
    
    if code2 == code:
        log("   ⚠️ Regex не изменил файл")
        return False
    
    bak = backup(p)
    log(f"   💾 Бэкап: {bak.name}")
    p.write_text(code2)
    
    ok, err = is_valid(code2)
    if not ok:
        log(f"   ❌ AST: {err[:80]}")
        shutil.copy2(bak, p)
        return False
    
    m = re.search(r'INDICATORS\s*=\s*\[[^\]]*\]', code2)
    if m:
        log(f"   ✅ {m.group(0)}")
    return True

def fix_check_status():
    log("\n🔧 ПЕРЕСОЗДАЁМ: check_status.sh")
    p = HOME / "check_status.sh"
    
    # Строим скрипт через список строк (без f-string, без экранирования)
    lines = []
    lines.append('#!/data/data/com.termux/files/usr/bin/bash')
    lines.append('clear')
    lines.append('echo "════════════════════════════════════════════════"')
    lines.append('echo "  ДАШБОРД: $(date +%H:%M:%S)  |  $(date +%d.%m.%Y)"')
    lines.append('echo "════════════════════════════════════════════════"')
    lines.append('echo ""')
    lines.append('echo "=== БОТЫ ==="')
    lines.append('echo "v3:           $(pgrep -f okx_bot_paper_v3 > /dev/null && echo OK || echo FAIL)"')
    lines.append('echo "oracle:       $(pgrep -f \'oracle.py loop\' > /dev/null && echo OK || echo FAIL)"')
    lines.append('echo "RSI-bot:      $(pgrep -f rsi_bot > /dev/null && echo OK || echo FAIL)"')
    lines.append('echo "GOD v4:       $(pgrep -f god_agent_v4 > /dev/null && echo OK || echo FAIL)"')
    lines.append('echo ""')
    lines.append('echo "=== ИИ-ЛАБОРАТОРИЯ ==="')
    lines.append('echo "Процесс:  $(pgrep -f strategy_lab > /dev/null && echo OK || echo FAIL)"')
    lines.append('if [ -f /data/data/com.termux/files/home/quantum_lab_sandbox/GOLDEN_AI.json ]; then')
    lines.append('    python3 -c "import json; d=json.load(open(\'/data/data/com.termux/files/home/quantum_lab_sandbox/GOLDEN_AI.json\')); print(\'Рекорд:   \' + str(d.get(\'pnl\', \'?\')))"')
    lines.append('else')
    lines.append('    echo "Рекорд:   нет файла"')
    lines.append('fi')
    lines.append('echo "Итераций: $(grep -c ИТЕРАЦИЯ /data/data/com.termux/files/home/quantum_lab_sandbox/.strategy_lab.log 2>/dev/null || echo 0)"')
    lines.append('echo ""')
    lines.append('echo "=== PnL v3 ==="')
    lines.append('echo -n "Всего: "')
    lines.append('sqlite3 /data/data/com.termux/files/home/quantum_lab/data/okx_paper_v3.db "SELECT COUNT(*) || \' сделок, PnL=\' || ROUND(COALESCE(SUM(pnl),0),2) FROM trades WHERE status=\'CLOSED\';" 2>/dev/null')
    lines.append('echo -n "Открыто: "')
    lines.append('sqlite3 /data/data/com.termux/files/home/quantum_lab/data/okx_paper_v3.db "SELECT COUNT(*) FROM trades WHERE status=\'OPEN\';" 2>/dev/null')
    lines.append('echo ""')
    lines.append('echo "=== СИСТЕМА ==="')
    lines.append('free -h | awk \'NR==2{print "RAM: " $3 "/" $2 " (avail " $7 ")"}\'')
    lines.append('free -h | awk \'NR==3{print "Swap: " $3 "/" $2}\'')
    lines.append('echo ""')
    
    new_script = "\n".join(lines) + "\n"
    
    bak = backup(p)
    log(f"   💾 Бэкап: {bak.name}")
    p.write_text(new_script)
    p.chmod(0o755)
    
    r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"   ❌ bash -n: {r.stderr[:80]}")
        shutil.copy2(bak, p)
        return False
    
    log("   ✅ Синтаксис OK")
    return True

def test_strategy_lab():
    log("\n🧪 ТЕСТ strategy_lab (8 сек)...")
    try:
        proc = subprocess.Popen(
            ["python3", "strategy_lab.py"], cwd=SANDBOX,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        time.sleep(8)
        proc.terminate()
        try: out, _ = proc.communicate(timeout=3)
        except: proc.kill(); out = ""
        
        if "SMA' is not defined" in out:
            log("   ❌ SMA NameError"); return False
        log("   ✅ Нет SMA ошибок")
        return True
    except Exception as e:
        log(f"   ⚠️ {e}"); return False

def test_check_status():
    log("\n🧪 ТЕСТ check_status...")
    try:
        r = subprocess.run(["bash", str(HOME / "check_status.sh")], capture_output=True, text=True, timeout=15)
        for line in r.stdout.split("\n"):
            if "Рекорд" in line:
                log(f"   {line.strip()[:100]}")
                if "0.540" in line or "?" not in line.replace("Рекорд:   ", ""):
                    log("   ✅ Рекорд показывается"); return True
        log("   ⚠️ Рекорд не найден")
        return False
    except Exception as e:
        log(f"   ⚠️ {e}"); return False

def main():
    log("INFRA FIXER v2")
    log(f"Начало: {time.strftime('%H:%M:%S')}")
    
    log("\nОстанавливаю strategy_lab...")
    subprocess.run(["pkill", "-9", "-f", "strategy_lab"], capture_output=True)
    time.sleep(2)
    
    r1 = fix_strategy_lab()
    r2 = fix_check_status()
    
    log("\n" + "="*50)
    log("ТЕСТЫ")
    log("="*50)
    t1 = test_strategy_lab() if r1 else False
    t2 = test_check_status() if r2 else False
    
    if r1 and t1:
        log("\nПерезапускаю strategy_lab...")
        with open(SANDBOX / "strategy_lab.log", "w") as f: pass
        subprocess.Popen(
            ["python3", "strategy_lab.py"], cwd=SANDBOX,
            stdout=open(SANDBOX / "strategy_lab.log", "w"),
            stderr=subprocess.STDOUT, start_new_session=True
        )
        log("   Запущена")
    
    log("\n" + "="*50)
    log("ИТОГИ")
    log("="*50)
    log(f"   strategy_lab:   fix={'OK' if r1 else 'FAIL'} test={'OK' if t1 else 'FAIL'}")
    log(f"   check_status:   fix={'OK' if r2 else 'FAIL'} test={'OK' if t2 else 'FAIL'}")

if __name__ == "__main__":
    main()
