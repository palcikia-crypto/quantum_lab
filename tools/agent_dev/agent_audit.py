import sys, os, json, time, subprocess
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))
from llm_backend import ask

PROJECT = Path.home() / "quantum_lab"
REPORT = PROJECT / ".agent_audit_report.json"
LOG = PROJECT / ".agent_audit.log"
STOP = PROJECT / ".agent_audit_stop"

EXCLUDE_KEYWORDS = [
    "rsbot", "pm_bot", "pm_v", "pm_watch", "polymarket",
    "__pycache__", ".pyc", ".bak", "backup", "backups",
    "MASTER_ARCHIVE", "UPGRADE_BACKUP", "QUANTUM_LAB_MASTER",
    ".git", ".agent_", "data/", "logs/",
]
AUDIT_DIRS = ["core", "agents", "web", "tools/agent_dev", "tools/agent"]
MAX_FILE_SIZE = 5000
SLEEP = 15

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def is_excluded(rel_path):
    p = rel_path.lower()
    return any(kw.lower() in p for kw in EXCLUDE_KEYWORDS)

def collect_files():
    files = []
    for subdir in AUDIT_DIRS:
        d = PROJECT / subdir
        if not d.exists(): continue
        for py in d.rglob("*.py"):
            # ВАЖНО: проверяем только ОТНОСИТЕЛЬНЫЙ путь!
            rel = str(py.relative_to(PROJECT))
            if is_excluded(rel): continue
            try:
                if py.stat().st_size > MAX_FILE_SIZE * 2: continue
            except: continue
            files.append(py)
    return sorted(files, key=lambda p: str(p))

def audit_file(path):
    rel = str(path.relative_to(PROJECT))
    result = {"file": rel, "size": path.stat().st_size, "severity": "unknown",
              "issues": [], "checked_at": datetime.now().isoformat()}
    
    try:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                          capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            result["syntax_ok"] = True
            log(f"  ✅ синтаксис OK")
        else:
            result["severity"] = "critical"
            result["issues"].append(f"SyntaxError: {r.stderr[-300:]}")
            log(f"  🔴 СИНТАКСИС СЛОМАН")
            return result
    except Exception as e:
        result["issues"].append(f"timeout: {e}")
        return result
    
    if path.stat().st_size > MAX_FILE_SIZE:
        result["severity"] = "skipped"
        log(f"  ⏭️ слишком большой ({path.stat().st_size}b)")
        return result
    
    try:
        code = path.read_text()
        prompt = f"""Ты — старший разработчик Python. Проверь код файла `{rel}` на РЕАЛЬНЫЕ проблемы:
- баги в логике
- необработанные исключения (bare except)
- опасные операции (eval, exec)
- утечки ресурсов (открытые файлы, соединения)
- SQL-инъекции

Код:
{code[:MAX_FILE_SIZE]}

Ответ СТРОГО:
СТАТУС: OK или ПРОБЛЕМА
КРАТКО: <если проблема, 1-2 предложения>
СЕРЬЁЗНОСТЬ: low/medium/high/critical"""

        answer = ask(prompt, system_prompt="Ты — ревьюер Python кода. Кратко.")
        result["ai_review"] = answer[:1500]
        
        if "СТАТУС: OK" in answer or answer.strip().startswith("OK"):
            result["severity"] = "ok"
            log(f"  🟢 OK")
        else:
            sev = "medium"
            for s in ["critical", "high", "medium", "low"]:
                if f"СЕРЬЁЗНОСТЬ: {s}" in answer:
                    sev = s; break
            result["severity"] = sev
            result["issues"].append(answer[:800])
            emoji = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}.get(sev,"⚪")
            brief = ""
            for line in answer.split("\n"):
                if "КРАТКО" in line:
                    brief = line.split(":", 1)[-1].strip()[:100]; break
            log(f"  {emoji} {sev.upper()}: {brief}")
    except Exception as e:
        result["issues"].append(f"AI error: {e}")
        result["severity"] = "error"
        log(f"  ⚠️ AI ошибка: {e}")
    
    return result

def main():
    log("=" * 60)
    log("🔍 АУДИТ (только чтение, БЕЗ изменений)")
    log(f"Остановить: touch {STOP}")
    log("=" * 60)
    
    report = {"started_at": datetime.now().isoformat(), "files": []}
    if REPORT.exists():
        try: report = json.loads(REPORT.read_text())
        except: pass
    
    already = {f["file"] for f in report["files"]}
    files = collect_files()
    log(f"📁 Найдено: {len(files)} файлов (уже проверено: {len(already)})")
    
    for i, f in enumerate(files, 1):
        if STOP.exists():
            log("🛑 STOP-сигнал"); break
        rel = str(f.relative_to(PROJECT))
        if rel in already: continue
        
        log(f"\n[{i}/{len(files)}] {rel}")
        try:
            r = audit_file(f)
            report["files"].append(r)
            report["summary"] = {
                "total": len(report["files"]),
                "ok": sum(1 for x in report["files"] if x["severity"]=="ok"),
                "issues": sum(1 for x in report["files"] if x["severity"] in ["critical","high","medium","low"]),
                "critical": sum(1 for x in report["files"] if x["severity"]=="critical"),
                "skipped": sum(1 for x in report["files"] if x["severity"]=="skipped"),
            }
            REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        except Exception as e:
            log(f"  💥 {e}")
        
        log(f"  💤 пауза {SLEEP}с")
        time.sleep(SLEEP)
    
    report["finished_at"] = datetime.now().isoformat()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log("\n" + "="*60)
    log("✅ АУДИТ ЗАВЕРШЕН")
    log(f"📊 Отчёт: {REPORT}")
    if "summary" in report:
        s = report["summary"]
        log(f"   Всего: {s['total']} | OK: {s['ok']} | Проблем: {s['issues']} | Критических: {s['critical']} | Пропущено: {s['skipped']}")
    log("="*60)

if __name__ == "__main__":
    main()
