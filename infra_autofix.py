import sys, os, subprocess, re, shutil, time
from pathlib import Path

HOME = Path.home()
SANDBOX = HOME / "quantum_lab_sandbox"
LOG = SANDBOX / ".infra_autofix.log"
BACKUPS = SANDBOX / "infra_backups"
BACKUPS.mkdir(exist_ok=True)

SAFE_INDICATORS = "['RSI', 'WILLIAMS', 'MACD', 'BOLLINGER', 'ROC', 'OBV']"

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

def fix_strategy_lab():
    p = SANDBOX / "strategy_lab.py"
    if not p.exists(): return False
    code = p.read_text()
    original = code
    
    # 1. Удаляем все docstrings (строки с тройными кавычками) внутри TEMPLATE
    lines = code.split("\n")
    new_lines = []
    for ln in lines:
        # Если это строка вида:     """Текст"""
        stripped = ln.strip()
        if stripped.startswith('"""') and stripped.endswith('"""') and len(stripped) > 6:
            # Заменяем на комментарий
            indent = ln[:len(ln) - len(ln.lstrip())]
            new_lines.append(indent + "# " + stripped[3:-3])
        else:
            new_lines.append(ln)
    code = "\n".join(new_lines)
    
    # 2. Заменяем INDICATORS
    code = re.sub(r'INDICATORS\s*=\s*\[[^\]]*\]', f'INDICATORS = {SAFE_INDICATORS}', code, count=1)
    
    # 3. Заменяем длинный список в тексте промпта
    old_list = "MACD, Bollinger, Stochastic, CCI, Williams, OBV, ROC, EMA, SMA"
    new_list = "RSI, WILLIAMS, MACD, BOLLINGER, ROC, OBV"
    if old_list in code:
        code = code.replace(old_list, new_list)
    
    # 4. Убираем упоминание SMA в предупреждении
    code = re.sub(r'CCI\(\), SMA\(\), EMA\(\)', 'SMA(), EMA(), CCI()', code)
    
    if code == original:
        return False  # ничего не изменилось
    
    # Проверяем синтаксис
    try:
        compile(code, str(p), "exec")
    except SyntaxError as e:
        log(f"   ❌ После фикса SyntaxError: {e}")
        return False
    
    bak = backup(p)
    log(f"   💾 Бэкап: {bak.name}")
    p.write_text(code)
    return True

def fix_check_status():
    p = HOME / "check_status.sh"
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
    lines.append('    python3 -c "import json; d=json.load(open(\'/data/data/com.termux/files/home/quantum_lab_sandbox/GOLDEN_AI.json\')); print(\'Рекорд:   \' + str(d.get(\'pnl\',\'?\')))"')
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
    
    new_content = "\n".join(lines) + "\n"
    
    # Проверяем что изменилось
    if p.exists() and p.read_text() == new_content:
        return False
    
    bak = backup(p)
    log(f"   💾 Бэкап: {bak.name}")
    p.write_text(new_content)
    p.chmod(0o755)
    
    # bash -n
    r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        log(f"   ❌ bash -n: {r.stderr[:80]}")
        if bak.exists(): shutil.copy2(bak, p)
        return False
    return True

def test_strategy_lab():
    try:
        proc = subprocess.Popen(
            ["python3", "strategy_lab.py"], cwd=SANDBOX,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        time.sleep(6)
        proc.terminate()
        try: out, _ = proc.communicate(timeout=2)
        except: proc.kill(); out = ""
        if "SMA' is not defined" in out or "SyntaxError" in out:
            return False
        return True
    except: return False

def main():
    log("=" * 50)
    log("INFRA AUTOFIX: чиним инфраструктуру")
    log("=" * 50)
    
    # 1. Останавливаем лабораторию (если работает)
    subprocess.run(["pkill", "-9", "-f", "strategy_lab"], capture_output=True)
    time.sleep(1)
    
    # 2. Фиксим strategy_lab.py
    log("\n1. strategy_lab.py...")
    r1 = fix_strategy_lab()
    if r1:
        log("   ✅ Пофикшен")
    else:
        log("   ℹ️ Не требовал фикса")
    
    # 3. Фиксим check_status.sh
    log("\n2. check_status.sh...")
    r2 = fix_check_status()
    if r2:
        log("   ✅ Пофикшен")
    else:
        log("   ℹ️ Не требовал фикса")
    
    # 4. Тест
    log("\n3. Тестируем strategy_lab...")
    t = test_strategy_lab()
    if t:
        log("   ✅ Работает")
    else:
        log("   ⚠️ Проблема, но продолжаем")
    
    # 5. Перезапускаем лабораторию если нужно
    if not subprocess.run(["pgrep", "-f", "strategy_lab"], capture_output=True).returncode == 0:
        log("\n4. Запускаем лабораторию...")
        with open(SANDBOX / "strategy_lab.log", "w") as f: pass
        subprocess.Popen(
            ["python3", "strategy_lab.py"], cwd=SANDBOX,
            stdout=open(SANDBOX / "strategy_lab.log", "w"),
            stderr=subprocess.STDOUT, start_new_session=True
        )
        log("   ✅ Запущена")
    
    log("\n" + "=" * 50)
    log("ГОТОВО")
    log("=" * 50)

if __name__ == "__main__":
    main()
