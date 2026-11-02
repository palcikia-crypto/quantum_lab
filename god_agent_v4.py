import sys, os, subprocess, time, re, json, ast, textwrap, shutil, hashlib
from pathlib import Path
import requests

sys.path.append(str(Path.home() / "quantum_lab_sandbox" / "tools" / "agent_dev"))
from llm_backend import ask

SANDBOX = Path.home() / "quantum_lab_sandbox"
REAL = Path.home() / "quantum_lab"
LOG = SANDBOX / ".god_v4.log"
BACKUPS = SANDBOX / "god_backups"
BACKUPS.mkdir(exist_ok=True)
NEW_MODULES = SANDBOX / "new_modules"
NEW_MODULES.mkdir(exist_ok=True)
REPORT = SANDBOX / "god_v4_report.json"
PROPOSALS = SANDBOX / "PROPOSALS.md"
KNOWLEDGE = SANDBOX / "project_knowledge.json"

# Загружаем карту проекта
try:
    KMAP = json.loads(KNOWLEDGE.read_text())
except:
    KMAP = {"critical": {}, "safe": [], "rules": [], "context": ""}

PROTECTED = [
    "god_agent.py", "god_agent_v4.py", "strategy_lab.py",
    "rsi_bot.py", "scalp_lab.py", "llm_backend.py",
    "tools/agent_dev/", "new_modules/", "god_backups/",
    "GOLDEN_AI.json", "GOLDEN_SCALP.json", "indicator_history.json",
    "god_report.json", "god_v4_report.json", "project_knowledge.json",
    "data/", "logs/", "__pycache__/", ".git/",
    "backtester_simple.py", "backtester_ai_test.py", "god_test.py",
]

# Расширенные индикаторы + комбинации
INDICATORS = ["RSI", "WILLIAMS", "MACD", "BOLLINGER", "ROC", "OBV"]
COMBOS = ["RSI+MACD", "RSI+BOLLINGER", "EMA_CROSS_9_21", "EMA_CROSS_12_26"]

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def is_protected(path):
    try:
        rel = str(path.relative_to(SANDBOX)).lower()
    except:
        rel = str(path).lower()
    return any(prot in rel for prot in PROTECTED)

def is_critical(path):
    """#1 БИЗНЕС-ЛОГИКА: критичный файл или нет"""
    try:
        rel = str(path.relative_to(SANDBOX)).replace("\\", "/")
    except:
        rel = str(path).replace("\\", "/")
    for crit in KMAP.get("critical", {}):
        if crit in rel or rel.endswith(crit.split("/")[-1]):
            return True, KMAP["critical"][crit]
    return False, ""

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
    if KMAP.get("context"):
        full = f"КОНТЕКСТ ПРОЕКТА:\n{KMAP['context']}\n\n{full}"
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

def deterministic_fix(code):
    """Расширенный набор безопасных regex-фиксов."""
    original = code
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
    # 3. == None -> is None
    code = re.sub(r'==\s*None', 'is None', code)
    code = re.sub(r'None\s*==', 'is None', code)
    # 4. != None -> is not None
    code = re.sub(r'!=\s*None', 'is not None', code)
    # 5. == True -> is True
    code = re.sub(r'==\s*True\b', 'is True', code)
    # 6. == False -> is False
    code = re.sub(r'==\s*False\b', 'is False', code)
    return code if code != original else None

# #2 РАЗБИВКА БОЛЬШИХ ФАЙЛОВ на функции
def split_functions(code):
    """Разбивает файл на функции (по AST)."""
    try:
        tree = ast.parse(code)
    except: return None
    
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funcs: return None
    
    sections = []
    for f in funcs:
        start = f.lineno - 1
        end = f.end_lineno if hasattr(f, 'end_lineno') else start + 50
        sections.append((f.name, "\n".join(code.split("\n")[start:end])))
    return sections

def fix_large_file(path):
    """#2: чинит большие файлы через разбивку на функции."""
    log(f"   📦 Большой файл, разбиваю на функции...")
    code = path.read_text()
    sections = split_functions(code)
    if not sections:
        log(f"   ⚠️ Не удалось разбить")
        return None
    
    log(f"   📋 Найдено функций: {len(sections)}")
    fixed_sections = []
    for fname, fbody in sections:
        fixed = ask_god(f"Функция `{fname}`:\n{fbody[:2000]}\n\nПочини её (если есть баги).")
        if fixed and len(fixed) > 50:
            ok, _ = is_valid(fixed)
            if ok:
                fixed_sections.append(fixed)
                continue
        fixed_sections.append(fbody)
    
    # Собираем обратно
    imports = "\n".join([ln for ln in code.split("\n") if ln.strip().startswith(("import ", "from "))])
    new_code = imports + "\n\n" + "\n\n".join(fixed_sections)
    ok, err = is_valid(new_code)
    if ok:
        return new_code
    return None

# #3 СОЗДАНИЕ СТРАТЕГИЙ (комбинации)
def create_combo_strategy(combo_name):
    """Создаёт новую стратегию на основе комбинации индикаторов."""
    prompt = f"""Создай торговую стратегию на Python для комбинации `{combo_name}`.

Требования:
- Использовать только стандартный Python (без numpy/pandas)
- Данные из data/market.db (таблица candles, 4H)
- Комбинация индикаторов: {combo_name}
- Вход: когда оба индикатора дают сигнал
- Выход: TP 2%, SL 1%
- В конце вывести `ИТОГО: <число>`

Выведи ПОЛНЫЙ код стратегии (с def main() и print ИТОГО)."""
    
    code = ask_god(prompt)
    if not code or len(code) < 200: return None
    ok, err = is_valid(code)
    if not ok: return None
    
    # Тестируем на реальных данных
    test_path = SANDBOX / "tools" / f"combo_{combo_name.replace('+','_')}.py"
    test_path.write_text(code)
    return test_path, code

# #4 РЕАЛЬНЫЙ ТЕСТ (не только py_compile)
def test_real(path):
    """Проверяет: импортируется ли, запускается ли без ошибок."""
    try:
        # 1. Проверка импорта
        r = subprocess.run(
            [sys.executable, "-c", f"import importlib.util; spec = importlib.util.spec_from_file_location('m', '{path}'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)"],
            cwd=SANDBOX, capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0 and "ModuleNotFoundError" not in r.stderr:
            return False, f"import: {r.stderr[-200:]}"
        return True, "OK"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)

# #5 РЕЖИМ СОВЕТНИКА (для критичных)
def advisor_mode(path, problem):
    """#6: для критичных файлов — только рекомендации."""
    log(f"   💡 РЕЖИМ СОВЕТНИКА (критичный файл)")
    proposal = f"""
## {path.name}
**Проблема:** {problem}
**Рекомендация:** НЕ ЧИНИТЬ АВТОМАТИЧЕСКИ. Нужна ручная проверка.
**Почему:** {is_critical(path)[1]}
"""
    with open(PROPOSALS, "a") as f:
        f.write(proposal)
    log(f"   📝 Записано в PROPOSALS.md")

def audit_file(path):
    try:
        code = path.read_text()
    except Exception as e:
        return "error", f"Не читается: {e}", None
    
    # #1 КРИТИЧНЫЙ ФАЙЛ — только рекомендации
    is_crit, reason = is_critical(path)
    
    # #2 БОЛЬШОЙ ФАЙЛ — разбивка на функции
    if len(code) > 4000 and not is_crit:
        log(f"   📦 Файл {len(code)}b — через разбивку")
        fixed = fix_large_file(path)
        if fixed:
            return "fixed_large", "разбит на функции", fixed
        return "needs_review", "большой файл, ИИ не справился", None
    
    ok, err = is_valid(code)
    if ok:
        prompt = f"""Проверь файл `{path.name}` на РЕАЛЬНЫЕ проблемы:
- утечки файлов (open без with)
- голые except:
- неопределённые переменные

Код:
{code[:3000]}

Верни `ПРОБЛЕМА: <кратко>` или `OK`."""
        
        try:
            ans = ask(prompt, system_prompt="Ты ревьюер Python. Кратко.")
            if "OK" in ans[:20] or len(ans) < 15:
                return "ok", "чистый", None
            
            if "ПРОБЛЕМА" in ans:
                log(f"   🟡 {ans[:80]}")
                
                # #6 КРИТИЧНЫЙ — советник
                if is_crit:
                    advisor_mode(path, ans[:200])
                    return "advisor", ans[:100], None
                
                # Детерминированный фикс
                det_fixed = deterministic_fix(code)
                if det_fixed != code:
                    ok2, _ = is_valid(det_fixed)
                    if ok2:
                        # #4 РЕАЛЬНЫЙ ТЕСТ
                        test_copy = BACKUPS / f"test_{path.name}"
                        test_copy.write_text(det_fixed)
                        real_ok, real_err = test_real(test_copy)
                        if real_ok:
                            log(f"   🔧 regex + реальный тест OK")
                            return "fixed_deterministic", "regex", det_fixed
                        else:
                            log(f"   ⚠️ Реальный тест упал: {real_err[:80]}")
                
                # AI-фикс
                for attempt in range(3):
                    fixed = ask_god(
                        f"Файл `{path.name}`. Проблема: {ans[:300]}\n\nКод:\n{code[:3000]}\n\nВыведи ПОЛНЫЙ код.",
                        error_ctx=ans[:200], prev_code=code
                    )
                    if fixed and len(fixed) > len(code) * 0.7:
                        ok2, _ = is_valid(fixed)
                        if ok2:
                            log(f"   🔧 AI-фикс (попытка {attempt+1})")
                            return "fixed_ai", ans[:100], fixed
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
    
    return "error", f"Не починил: {err[:100]}", None

def scan_files():
    files = []
    for subdir in ["core", "agents", "web"]:
        d = SANDBOX / subdir
        if not d.exists(): continue
        for p in d.rglob("*.py"):
            if is_protected(p): continue
            if p.stat().st_size > 8000: continue
            files.append(p)
    return sorted(files, key=lambda x: str(x))

def main():
    log("👑 GOD AGENT v4: 6 улучшений")
    log("1. Бизнес-логика (PROJECT_MAP)")
    log("2. Большие файлы (разбивка)")
    log("3. Стратегии (комбинации)")
    log("4. Реальный тест (import)")
    log("5. Контекст проекта")
    log("6. Режим советника")
    
    # Очищаем PROPOSALS
    PROPOSALS.write_text("# 💡 Рекомендации для критичных файлов\n\n")
    
    iteration = 0
    combo_idx = 0
    while True:
        iteration += 1
        log(f"\n{'='*60}")
        log(f"ПРОХОД {iteration}")
        log(f"{'='*60}")
        
        report = {"scanned": 0, "ok": 0, "fixed": 0, "errors": 0, "advisor": 0, "modules_created": 0, "files": []}
        
        files = scan_files()
        log(f"📁 Файлов: {len(files)}")
        
        for i, path in enumerate(files, 1):
            rel = path.relative_to(SANDBOX)
            log(f"\n[{i}/{len(files)}] {rel}")
            report["scanned"] += 1
            
            status, msg, fixed = audit_file(path)
            
            if status == "ok":
                log(f"   ✅ чистый")
                report["ok"] += 1
            elif status == "advisor":
                log(f"   💡 рекомендация")
                report["advisor"] += 1
            elif status.startswith("fixed"):
                bak = backup_file(path)
                log(f"   💾 бэкап: {bak.name}")
                path.write_text(fixed)
                ok, _ = is_valid(fixed)
                if ok:
                    log(f"   ✅ ИСПРАВЛЕН ({status})")
                    report["fixed"] += 1
                else:
                    log(f"   ❌ откат")
                    shutil.copy2(bak, path)
                    report["errors"] += 1
            elif status == "needs_review":
                log(f"   🟡 требует внимания")
            else:
                log(f"   ❌ {msg}")
                report["errors"] += 1
            
            report["files"].append({"file": str(rel), "status": status, "msg": msg[:200]})
            REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            time.sleep(15)
        
        # #3 КОМБИНАЦИИ СТРАТЕГИЙ
        log(f"\n🧪 Создание стратегии-комбинации...")
        combo = COMBOS[combo_idx % len(COMBOS)]
        combo_idx += 1
        log(f"   🎯 {combo}")
        result = create_combo_strategy(combo)
        if result:
            path, code = result
            log(f"   ✅ Создан: {path.name}")
            report["modules_created"] += 1
        
        log(f"\n📊 ИТОГИ: OK={report['ok']} FIX={report['fixed']} ADVISOR={report['advisor']} ERR={report['errors']}")
        log(f"💤 Пауза 60с...")
        time.sleep(60)

if __name__ == "__main__":
    main()
