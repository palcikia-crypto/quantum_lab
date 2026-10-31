import sys, subprocess
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from llm_backend import ask

PROJECT_DIR = Path.home() / "quantum_lab"

def safe_apply(target_file: str, new_code: str):
    file_path = PROJECT_DIR / target_file
    if not file_path.exists():
        print(f"❌ Файл {target_file} не найден!")
        return

    subprocess.run(["git", "add", "."], cwd=PROJECT_DIR, capture_output=True)
    subprocess.run(["git", "commit", "-m", "agent_before_change"], cwd=PROJECT_DIR, capture_output=True)

    if len(new_code) < 100:
        print(f"❌ ИИ вернул слишком короткий код. Вот что он прислал: '{new_code}'")
        return

    file_path.write_text(new_code)

    check = subprocess.run([sys.executable, "-m", "py_compile", str(file_path)], capture_output=True, text=True)
    if check.returncode == 0:
        print(f"\n✅ Файл {target_file} успешно обновлен! Синтаксис в порядке.")
    else:
        print(f"\n❌ Ошибка синтаксиса! Откат...\n{check.stderr}")
        subprocess.run(["git", "checkout", "--", "."], cwd=PROJECT_DIR, capture_output=True)

def main():
    if len(sys.argv) < 3:
        print("Использование: python3 agent_dev.py <файл.py> '<задача>'")
        return

    target_file = sys.argv[1]
    task = sys.argv[2]
    
    print(f"🧠 Агент думает над задачей...")
    
    file_path = PROJECT_DIR / target_file
    if not file_path.exists():
         print(f"❌ Ошибка: Файл {target_file} не существует.")
         return

    code = file_path.read_text()
    # УМЕНЬШИЛИ РАЗМЕР КОДА до 3000 символов, чтобы ИИ не давился
    safe_code = code[:3000] 
    
    prompt = f"""Ты — Senior Python разработчик.
Вот код файла `{target_file}`:
{safe_code}

Задача: {task}

Выведи ТОЛЬКО ПОЛНЫЙ ИСПРАВЛЕННЫЙ КОД этого файла. Без лишних слов, без markdown-тегов."""

    response = ask(prompt, system_prompt="Ты пишешь чистый Python код.")
    
    new_code = response.replace("```python", "").replace("```", "").strip()
    
    safe_apply(target_file, new_code)

if __name__ == "__main__":
    main()
