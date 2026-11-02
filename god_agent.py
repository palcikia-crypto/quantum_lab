import sys, os, subprocess, time, re, json, ast, textwrap, shutil, hashlib
from pathlib import Path
import requests

sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))
from llm_backend import ask

SANDBOX = Path.home() / "quantum_lab_sandbox"
REAL = Path.home() / "quantum_lab"
LOG = SANDBOX / ".god_agent.log"
BACKUPS = SANDBOX / "god_backups"
BACKUPS.mkdir(exist_ok=True)
NEW_MODULES = SANDBOX / "new_modules"
NEW_MODULES.mkdir(exist_ok=True)
REPORT = SANDBOX / "god_report.json"

# Файлы, которые НЕ трогаем (критичные)
PROTECTED = [
    # Наши рабочие скрипты (не трогать!)
    "rsi_bot.py", "scalp_lab.py", "strategy_lab.py", "god_agent.py",
    "devops_agent.py", "fixer_v2.py", "fix_prompt.py", "test_long.py",
    "god_test.py", "agent_researcher.py", "agent_audit.py", "agent_monitor.py",
    # Системные
    "tools/agent_dev/llm_backend.py", "tools/agent_dev/",
    "new_modules/", "god_backups/",
    "GOLDEN_AI.json", "GOLDEN_SCALP.json", "indicator_history.json",
    "scalp_history.json", "god_report.json",
    "data/", "logs/", "__pycache__/", ".git/",
    "backtester_ai_test.py", "backtester_simple.py",
]

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def is_protected(path):
    # ВАЖНО: проверяем только ОТНОСИТЕЛЬНЫЙ путь от SANDBOX
    try:
        rel = str(path.relative_to(SANDBOX)).lower()
    except:
        rel = str(path).lower()
    return any(prot in rel for prot in PROTECTED)

def web_search(q):
    log(f"   🌐 {q[:50]}...")
    try:
        r = requests.get("https://html.duckduckgo.com/html/", params={"q": q}, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            s = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL)
            res = [re.sub(r'<[^>]+>', '', x).strip() for x in s[:3] if x.strip()]
            return "\n".join(res) if res else "пусто"
    except: pass
    return "пусто"

def is_valid(code):
    try: ast.parse(code); return True, ""
    except Exception as e: return False, str(e)

def ask_god(prompt, error_ctx=None, prev_code=None):
    full = prompt
    if error_ctx:
        full += f"\n\nОШИБКА:\n{error_ctx}\n\n"
        if prev_code: full += f"ТВОЙ КОД:\n{prev_code}\n\n"
        full += "ИСПРАВЬ."
    try:
        r = ask(full, system_prompt="Пиши ТОЛЬКО код на чистом Python. Без numpy, pandas, talib.").strip()
        r = r.replace("```python", "").replace("```", "").strip()
        if not r: return None
        if any(x in r for x in ["numpy", "pandas", "talib"]): return None
        r = textwrap.dedent(r).strip()
        last = r.rstrip()[-1] if r.rstrip() else ""
        if last in "([{,+-*/=:":
            cont = ask(f"Продолжи ровно с:\n{r[-300:]}", system_prompt="Продолжаешь код.").strip()
            cont = cont.replace("```python", "").replace("```", "").strip()
            r = r + cont
        return r
    except Exception as e:
        log(f"   ⚠️ {e}")
        return None

def backup_file(path):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = BACKUPS / f"{path.name}.{ts}.bak"
    shutil.copy2(path, bak)
    return bak

def file_hash(path):
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]

def deterministic_fix(code):
    """Regex-фиксы, которые никогда не ломают синтаксис."""
    # 1. Голый except -> except Exception
    code = re.sub(r'\bexcept\s*:', 'except Exception:', code)
    # 2. open(...) без encoding
    def fix_open(m):
        args = m.group(1)
        if "'rb'" in args or '"rb"' in args or 'encoding' in args:
            return m.group(0)
        if 'encoding' not in args:
            return f"open({args}, encoding='utf-8')"
        return m.group(0)
    code = re.sub(r'open\(([^)]+)\)', fix_open, code)
    return code

def audit_file(path):
    """Проверяет один файл. Возвращает (status, message, fixed_code)."""
    try:
        code = path.read_text()
    except Exception as e:
        return "error", f"Не читается: {e}", None
    
    ok, err = is_valid(code)
    if ok:
        prompt = f"""Проверь файл `{path.name}` на РЕАЛЬНЫЕ проблемы:
- утечки файлов (open без with)
- голые except:
- неопределённые переменные
- деление на ноль

Код:
{code[:3000]}

Если есть проблема — верни `ПРОБЛЕМА: <кратко>`.
Если чистый — верни `OK`."""
        
        try:
            ans = ask(prompt, system_prompt="Ты ревьюер Python. Кратко.")
            if "OK" in ans[:20] or len(ans) < 15:
                return "ok", "чистый", None
            
            if "ПРОБЛЕМА" in ans:
                log(f"   🟡 {ans[:80]}")
                
                # ДЕТЕРМИНИРОВАННЫЙ ФИКС
                det_fixed = deterministic_fix(code)
                if det_fixed != code:
                    ok2, _ = is_valid(det_fixed)
                    if ok2:
                        log(f"   🔧 Детерминированный фикс (regex)")
                        return "fixed_deterministic", "regex fix", det_fixed
                
                # AI-ФИКС (3 попытки)
                for attempt in range(3):
                    fixed = ask_god(
                        f"Файл `{path.name}`. Проблема: {ans[:300]}\n\nКод:\n{code[:3000]}\n\nВыведи ПОЛНЫЙ исправленный код.",
                        error_ctx=ans[:200], prev_code=code
                    )
                    if fixed and len(fixed) > len(code) * 0.7:
                        ok2, err2 = is_valid(fixed)
                        if ok2:
                            log(f"   🔧 AI-фикс (попытка {attempt+1})")
                            return "fixed_ai", ans[:100], fixed
                        else:
                            log(f"   ⚠️ AI AST: {err2[:60]}")
                    else:
                        log(f"   ⚠️ AI: код короткий ({len(fixed) if fixed else 0}b)")
                    time.sleep(3)
                
                return "needs_review", ans[:100], None
            return "needs_review", ans[:100], None
        except Exception as e:
            return "error", f"AI: {e}", None
    
    # Синтаксис сломан
    det_fixed = deterministic_fix(code)
    if det_fixed != code:
        ok2, _ = is_valid(det_fixed)
        if ok2:
            return "fixed_syntax_det", err[:100], det_fixed
    
    fixed = ask_god(
        f"Файл `{path.name}` не компилируется.\n\nКод:\n{code[:3000]}\n\nВыведи ПОЛНЫЙ исправленный код.",
        error_ctx=err, prev_code=code
    )
    if fixed:
        ok2, _ = is_valid(fixed)
        if ok2:
            return "fixed_syntax_ai", err[:100], fixed
    
    return "error", f"Не починил: {err[:100]}", None

def create_module(name, task):
    prompt = f"""Создай Python-модуль '{name}'.
Задача: {task}
ТОЛЬКО код. С `if __name__ == '__main__': main()`."""
    code = ask_god(prompt)
    if not code or len(code) < 100: return None
    ok, err = is_valid(code)
    if not ok:
        log(f"   ❌ AST: {err[:60]}")
        return None
    path = NEW_MODULES / f"{name}.py"
    path.write_text(code)
    return path

def scan_all_files():
    files = []
    # Сканируем ТОЛЬКО core/ и agents/ (рабочие модули ботов)
    for subdir in ["core", "agents", "web"]:
        d = SANDBOX / subdir
        if not d.exists(): continue
        for p in d.rglob("*.py"):
            if is_protected(p): continue
            if p.stat().st_size > 3000: continue  # маленькие файлы только
            files.append(p)
    return sorted(files, key=lambda x: str(x))

def main():
    log("👑 GOD AGENT v3: Полная автономия (сканирует ВСЮ песочницу)")
    
    report = {"scanned": 0, "ok": 0, "fixed": 0, "errors": 0, "modules_created": 0, "files": []}
    
    iteration = 0
    while True:
        iteration += 1
        log(f"\n{'='*60}")
        log(f"ПРОХОД {iteration}: сканирую песочницу...")
        log(f"{'='*60}")
        
        files = scan_all_files()
        log(f"📁 Найдено файлов: {len(files)}")
        
        report = {"scanned": 0, "ok": 0, "fixed": 0, "errors": 0, "modules_created": 0, "files": []}
        
        for i, path in enumerate(files, 1):
            rel = path.relative_to(SANDBOX)
            log(f"\n[{i}/{len(files)}] {rel}")
            report["scanned"] += 1
            
            status, msg, fixed = audit_file(path)
            
            if status == "ok":
                log(f"   ✅ чистый")
                report["ok"] += 1
            elif status.startswith("fixed"):
                # Бэкап и замена
                bak = backup_file(path)
                log(f"   💾 бэкап: {bak.name}")
                path.write_text(fixed)
                # Проверяем что компилируется
                ok, err = is_valid(fixed)
                if ok:
                    log(f"   ✅ ИСПРАВЛЕН ({status})")
                    report["fixed"] += 1
                else:
                    log(f"   ❌ Всё равно сломано. Откат.")
                    shutil.copy2(bak, path)
                    report["errors"] += 1
            elif status == "needs_review":
                log(f"   🟡 Требует внимания: {msg}")
            else:
                log(f"   ❌ {msg}")
                report["errors"] += 1
            
            report["files"].append({"file": str(rel), "status": status, "msg": msg[:200]})
            REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            
            time.sleep(15)  # пауза между файлами
        
        # Создаем новый полезный модуль
        log(f"\n🆕 Создание нового модуля...")
        module_tasks = [
            ("backup_manager", "Создай менеджер бэкапов: создает zip-архивы папки data/ с датой в имени, хранит последние 10, удаляет старые"),
            ("health_monitor", "Создай монитор здоровья: проверяет что все ключевые процессы (okx_bot_paper_v3, oracle.py, orderbook_oracle) живы, если нет — перезапускает"),
            ("performance_tracker", "Создай трекер производительности: записывает в JSON ежедневный PnL всех ботов, строит историю"),
            ("data_validator", "Создай валидатор данных: проверяет market.db на пропуски, дубли, отрицательные цены, чинит или логирует"),
            ("log_analyzer", "Создай анализатор логов: находит ошибки в logs/*.log за последние 24 часа, группирует по типу, выводит топ проблем"),
        ]
        task = module_tasks[iteration % len(module_tasks)]
        log(f"   📝 {task[0]}: {task[1][:60]}...")
        mod_path = create_module(task[0], task[1])
        if mod_path:
            log(f"   ✅ Создан: {mod_path.name}")
            report["modules_created"] += 1
        else:
            log(f"   ❌ Не удалось создать {task[0]}")
        
        log(f"\n{'='*60}")
        log(f"📊 ИТОГИ ПРОХОДА {iteration}:")
        log(f"   Сканировано: {report['scanned']}")
        log(f"   Чистых: {report['ok']}")
        log(f"   Исправлено: {report['fixed']}")
        log(f"   Ошибок: {report['errors']}")
        log(f"   Модулей создано: {report['modules_created']}")
        log(f"{'='*60}")
        
        log(f"\n💤 Пауза 60с перед следующим проходом...\n")
        time.sleep(60)

if __name__ == "__main__":
    main()
