import base64, subprocess, requests, json

print("🔑 Получаю свежий токен...")
token = subprocess.check_output(['gh', 'auth', 'token']).decode().strip()

print("📦 Кодирую архив...")
with open('code.tar.gz', 'rb') as f:
    content = base64.b64encode(f.read()).decode()

url = 'https://api.github.com/repos/palcikia-crypto/quantum_lab/contents/code.tar.gz'
headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}

# Получаем SHA, если файл существует
r = requests.get(url, headers=headers)
sha = r.json().get('sha') if r.status_code == 200 else None

data = {'message': 'Add code archive', 'content': content, 'branch': 'master'}
if sha: 
    data['sha'] = sha
    print("🔄 Обновляю существующий файл...")

print("🚀 Отправляю на GitHub...")
r = requests.put(url, headers=headers, json=data)
if r.status_code in [200, 201]:
    print("✅ АРХИВ УСПЕШНО ЗАГРУЖЕН!")
else:
    print(f"❌ Ошибка: {r.status_code} - {r.text}")
