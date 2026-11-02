import base64, os, subprocess

files = {}
def add(path):
    try:
        with open(path, 'rb') as f:
            files[path] = base64.b64encode(f.read()).decode()
    except: pass

# Все .py в корне
for f in os.listdir('.'):
    if f.endswith('.py') and os.path.isfile(f) and f != 'upload.py':
        add(f)

# Папки с модулями
for folder in ['core','tools','data','fixed','fixed_v2','new_modules']:
    if os.path.isdir(folder):
        for root, dirs, fs in os.walk(folder):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in fs:
                if f.endswith(('.py','.json')): 
                    add(os.path.join(root, f))

print(f"📦 Найдено файлов для загрузки: {len(files)}")
ok = 0
for i, (path, content) in enumerate(files.items(), 1):
    # Пропускаем файлы больше 5 МБ, чтобы не завалить API
    if len(content) > 5 * 1024 * 1024:
        print(f"  [{i}/{len(files)}] ⚠️ {path} (слишком большой)")
        continue
        
    r = subprocess.run(['gh','api','--method','PUT',
        f'repos/palcikia-crypto/quantum_lab/contents/{path}',
        '-f', 'message=Add file',
        '-f', f'content={content}',
        '-f', 'branch=master'],
        capture_output=True, text=True, timeout=60)
        
    if r.returncode == 0:
        ok += 1
        print(f"  [{i}/{len(files)}] ✓ {path}")
    else:
        # Если файл уже есть, GitHub выдаёт 422. Мы его перезаписываем (нужен SHA), 
        # но для простоты просто пропускаем, если ошибка не критичная.
        print(f"  [{i}/{len(files)}] ✗ {path}: {r.stderr[:80]}")

print(f"\n✅ Загружено {ok}/{len(files)} файлов!")
