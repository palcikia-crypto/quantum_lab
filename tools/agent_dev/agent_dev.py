import sys, subprocess, shutil
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))
from llm_backend import ask

PROJECT_DIR = Path.home() / "quantum_lab"
BACKUP_DIR = PROJECT_DIR / ".agent_backups"
BACKUP_DIR.mkdir(exist_ok=True)

def safe_apply(target_file: str, new_code: str):
    file_path = PROJECT_DIR / target_file
    file_path.parent.mkdir(parents=True, exist_ok=True) # Создаем папки, если их нет
    
    if len(new_code) < 100:
        print(f"❌ ИИ вернул слишком короткий код. Ответ: '{new_code}'")
        return

    # Бэкап, только если файл существует
    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"{file_path.name}_{ts}.py.bak"
        shutil.copy2(file_path, backup_path)
        print(f"💾 Бэкап старой версии: {backup_path.name}")
    else:
        print(f"🆕 Файл {target_file} будет создан с нуля.")

    # Записываем новый код
    file_path.write_text(new_code)

    # Проверка синтаксиса
    check = subprocess.run([sys.executable, "-m", "py_compile", str(file_path)], capture_output=True, text=True)
    if check.returncode == 0:
        print(f"\n✅ Файл {target_file} успешно обновлен! Синтаксис в порядке.")
    else:
        print(f"\n❌ Ошибка синтаксиса! Откат...\n{check.stderr}")
        if file_path.exists() and 'backup_path' in locals():
            shutil.copy2(backup_path, file_path) # Откатываем из бэкапа
            print("🔄 Файл восстановлен из бэкапа.")
        elif file_path.exists():
            file_path.unlink() # Если файл был создан впервые и не скомпилировался — удаляем

def main():
    if len(sys.argv) < 3:
        print("Использование: python3 agent_dev.py <файл.py> '<задача>'")
        return

    target_file = sys.argv[1]
    task = sys.argv[2]
    
    print(f"🧠 Агент думает над задачей...")
    file_path = PROJECT_DIR / target_file
    
    # Если файла нет, отправляем пустую строку, иначе — читаем код
    code = file_path.read_text() if file_path.exists() else ""
    safe_code = code[:4000]
    
    prompt = f"""Ты — Senior Python разработчик.
Вот текущий код файла `{target_file}`:
{safe_code}

Задача: {task}

Выведи ТОЛЬКО ПОЛНЫЙ ИСПРАВЛЕННЫЙ КОД этого файла. Без лишних слов, без markdown-тегов."""

    response = ask(prompt, system_prompt="Ты пишешь чистый Python код.")
    new_code = response.replace("```python", "").replace("```", "").strip()
    
    safe_apply(target_file, new_code)

if __name__ == "__main__":
    main()
