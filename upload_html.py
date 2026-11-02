import base64, subprocess, requests

print("🔑 Авторизация...")
token = subprocess.check_output(['gh', 'auth', 'token']).decode().strip()

print("📦 Читаю index.html...")
with open('index.html', 'rb') as f:
    content = base64.b64encode(f.read()).decode()

url = 'https://api.github.com/repos/palcikia-crypto/quantum_lab/contents/index.html'
headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}

r = requests.get(url, headers=headers)
sha = r.json().get('sha') if r.status_code == 200 else None

data = {'message': 'Add dashboard html', 'content': content, 'branch': 'master'}
if sha: data['sha'] = sha

print("🚀 Отправляю на GitHub...")
r = requests.put(url, headers=headers, json=data)
if r.status_code in [200, 201]:
    print("✅ УСПЕХ! Файл index.html загружен в репозиторий.")
    print("⏳ Подожди 1-2 минуты, GitHub собирает сайт.")
else:
    print(f"❌ Ошибка: {r.status_code} - {r.text}")
