import base64, subprocess, requests

token = subprocess.check_output(['gh', 'auth', 'token']).decode().strip()
with open('.github/workflows/quantum_run.yml', 'rb') as f:
    content = base64.b64encode(f.read()).decode()

url = 'https://api.github.com/repos/palcikia-crypto/quantum_lab/contents/.github/workflows/quantum_run.yml'
headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}

r = requests.get(url, headers=headers)
sha = r.json().get('sha') if r.status_code == 200 else None

data = {'message': 'Update workflow with copy step', 'content': content, 'branch': 'master'}
if sha: data['sha'] = sha

r = requests.put(url, headers=headers, json=data)
print("✅ Конфиг обновлен!" if r.status_code in [200, 201] else f"❌ Ошибка: {r.text}")
