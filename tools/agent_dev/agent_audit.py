import sys, os, json, time, subprocess
from pathlib import Path
from datetime import datetime
sys.path.append(str(Path(__file__).parent))
from llm_backend import ask

PROJECT = Path.home() / "quantum_lab"
REPORT = PROJECT / ".agent_audit_report.json"
LOG = PROJECT / ".agent_audit.log"
STOP = PROJECT / ".agent_audit_stop"

EXCLUDE_KEYWORDS = ["rsbot", "pm_bot", "pm_v", "__pycache__", ".pyc", ".bak", "backup", "MASTER_ARCHIVE", ".git", ".agent_", "data/", "logs/"]
AUDIT_DIRS = ["core", "agents", "web", "tools/agent_dev"]
MAX_FILE_SIZE = 2500 # Уменьшили, чтобы ИИ не давился
SLEEP = 15

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def is_excluded(rel_path):
    p = rel_path.lower()
    return any(kw.lower() in p for kw in EXCLUDE_KEYWORDS)

def collect_files():
    files = []
    for subdir in AUDIT_DIRS:
        d = PROJECT / subdir
        if not d.exists(): continue
        for py in d.rglob("*.py"):
            rel = str(py.relative_to(PROJECT))
            if is_excluded(rel): continue
            if py.stat().st_size > MAX_FILE_SIZE * 2: continue
            files.append(py)
    return sorted(files, key=lambda p: str(p))

def audit_file(path):
    rel = str(path.relative_to(PROJECT))
    res = {"file": rel, "size": path.stat().st_size, "severity": "unknown", "issues": [], "checked_at": datetime.now().isoformat()}
    
    try:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(path)], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            res["severity"] = "critical"
            res["issues"].append(f"SyntaxError: {r.stderr[-300:]}")
            log("  🔴 СИНТАКСИС СЛОМАН")
            return res
        res["syntax_ok"] = True
    except Exception as e:
        res["issues"].append(f"timeout: {e}"); return res
        
    if path.stat().st_size > MAX_FILE_SIZE:
        res["severity"] = "skipped"
        log(f"  ⏭️ слишком большой")
        return res
        
    try:
        code = path.read_text()
        prompt = f"Проверь код файла `{rel}` на РЕАЛЬНЫЕ баги. Код:\n{code}\n\nОтвет СТРОГО:\nСТАТУС: OK или ПРОБЛЕМА\nКРАТКО: <1 предложение>\nСЕРЬЁЗНОСТЬ: low/medium/high/critical"
        answer = ask(prompt, system_prompt="Ты — ревьюер Python кода. Кратко.")
        
        if "ОШИБКА_API" in answer:
            res["severity"] = "error_skip" # <--- НОВЫЙ СТАТУС (не баг, а сбой ИИ)
            log("  ⚠️ ПРОПУСК (Сбой ИИ)")
            return res

        res["ai_review"] = answer[:1500]
        if "СТАТУС: OK" in answer or answer.strip().startswith("OK"):
            res["severity"] = "ok"
            log("  🟢 OK")
        else:
            sev = "medium"
            for s in ["critical", "high", "medium", "low"]:
                if f"СЕРЬЁЗНОСТЬ: {s}" in answer: sev = s; break
            res["severity"] = sev
            res["issues"].append(answer[:800])
            log(f"  🟡 {sev.upper()}")
    except Exception as e:
        res["severity"] = "error_skip"
        log(f"  ⚠️ Ошибка: {e}")
    return res

def main():
    log("🔍 СТАРТ АУДИТА (с автоповтором)")
    report = {"started_at": datetime.now().isoformat(), "files": []}
    if REPORT.exists():
        try: report = json.loads(REPORT.read_text())
        except: pass
    # Очищаем старые ошибки ИИ, чтобы они не мешали
    report["files"] = [f for f in report["files"] if f.get("severity") != "error_skip"]
    already = {f["file"] for f in report["files"]}
    
    files = collect_files()
    log(f"📁 Найдено: {len(files)} файлов (уже проверено: {len(already)})")
    
    for i, f in enumerate(files, 1):
        if STOP.exists(): break
        rel = str(f.relative_to(PROJECT))
        if rel in already: continue
        
        log(f"[{i}/{len(files)}] {rel}")
        r = audit_file(f)
        report["files"].append(r)
        report["summary"] = {"total": len(report["files"]), "ok": sum(1 for x in report["files"] if x["severity"]=="ok"), "issues": sum(1 for x in report["files"] if x["severity"] in ["critical","high","medium","low"])}
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
