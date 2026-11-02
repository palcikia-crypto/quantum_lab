import sys, os, json, time, re, requests
from pathlib import Path
from datetime import datetime
sys.path.append(str(Path(__file__).parent))
from llm_backend import ask

PROJECT = Path.home() / "quantum_lab"
REPORT = PROJECT / ".agent_research_report.json"
MD_FILE = PROJECT / "IMPROVEMENTS.md"
LOG = PROJECT / ".agent_research.log"
STOP = PROJECT / ".agent_research_stop"

EXCLUDE = ["rsbot", "pm_bot", "pm_v", "__pycache__", ".pyc", ".bak", "backup", "MASTER_ARCHIVE", ".git", ".agent_", "data/", "logs/", "README", "requirements", "archive/"]
MAX_SIZE = 1500  # Уменьшили, чтобы ИИ успевал
SLEEP = 10

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def is_excluded(rel):
    return any(kw.lower() in rel.lower() for kw in EXCLUDE)

def collect_files():
    files = []
    for py in PROJECT.rglob("*.py"):
        rel = str(py.relative_to(PROJECT))
        if is_excluded(rel) or py.stat().st_size > MAX_SIZE * 2: continue
        files.append(py)
    return sorted(files, key=lambda p: str(p))

def research_file(path):
    rel = str(path.relative_to(PROJECT))
    res = {"file": rel, "problems": "", "improvements": ""}
    
    try: code = path.read_text()
    except: return res

    prompt = f"Изучи код файла `{rel}`.\nКод:\n{code[:MAX_SIZE]}\n\nКратко: в чем проблема и как улучшить? Если все ок, напиши 'OK'."
    log(f"   ⏳ Отправляю в ИИ (ждет ответа)...")
    
    answer = ask(prompt, system_prompt="Ты — ревьюер кода. Пиши кратко.")
    
    if "ОШИБКА" in answer:
        log(f"   ❌ {answer}")
        res["problems"] = "СБОЙ_СЕТИ"
        return res

    # Показываем мысли ИИ в логе!
    log(f"   💭 Мысли ИИ: {answer[:200]}...")
    
    if "OK" not in answer[:10]:
        res["problems"] = answer[:500]
    return res

def save_markdown(report):
    lines = ["# 📋 Предложения по улучшению проекта\n", f"Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for item in report["files"]:
        if item.get("problems") == "СБОЙ_СЕТИ": continue
        if not item.get("problems"): continue
        lines.append(f"## 📄 {item['file']}\n")
        lines.append(f"**🔴 Проблема:** {item['problems']}\n")
        lines.append("\n---\n")
    MD_FILE.write_text("\n".join(lines))

def main():
    log("🧠 СТАРТ (с показом мыслей ИИ)")
    report = {"started_at": datetime.now().isoformat(), "files": []}
    if REPORT.exists():
        try: report = json.loads(REPORT.read_text())
        except: pass
    
    report["files"] = [f for f in report["files"] if f.get("problems") != "СБОЙ_СЕТИ"]
    already = {f["file"] for f in report["files"]}
    
    files = collect_files()
    log(f"📁 Файлов к проверке: {len(files)}")
    
    for i, f in enumerate(files, 1):
        if STOP.exists(): break
        rel = str(f.relative_to(PROJECT))
        if rel in already: continue
        
        log(f"[{i}/{len(files)}] {rel}")
        r = research_file(f)
        
        if r["problems"] != "СБОЙ_СЕТИ":
            report["files"].append(r)
            REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            save_markdown(report)
        
        time.sleep(SLEEP)
    log("🎉 ГОТОВО!")

if __name__ == "__main__":
    main()
