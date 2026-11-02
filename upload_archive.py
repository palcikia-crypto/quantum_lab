import base64, os, subprocess, requests, json

print("🔑 Получаю токен GitHub...")
token = subprocess.check_output(['gh', 'auth', 'token']).decode().strip()

print("📦 Читаю архив code.tar.gz...")
with open('code.tar.gz', 'rb') as f:
    content = base64.b64encode(f.read()).decode()

url = 'https://api.github.com/repos/palcikia-crypto/quantum_lab/contents/code.tar.gz'
headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}

# Проверяем, есть ли файл (нужен SHA для перезаписи)
sha = None
r = requests.get(url, headers=headers)
if r.status_code == 200:
    sha = r.json()['sha']
    print(f"🔄 Файл уже есть, обновляю...")

data = {'message': 'Add code archive', 'content': content, 'branch': 'master'}
if sha: data['sha'] = sha

print(f"🚀 Отправляю {len(content)/1024/1024:.1f} МБ на GitHub...")
r = requests.put(url, headers=headers, json=data)
if r.status_code in [200, 201]:
    print("✅ Архив успешно загружен на GitHub!")
else:
    print(f"❌ Ошибка: {r.status_code}")
    print(r.text)
