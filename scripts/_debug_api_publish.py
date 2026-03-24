"""
note.com の publish API を直接呼び出してみるデバッグスクリプト。
セッションクッキーを使って requests で API を試す。
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import requests

with open('output/note_session.json') as f:
    session_data = json.load(f)

# セッションクッキーを requests.Session に設定
session = requests.Session()
for cookie in session_data.get('cookies', []):
    session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', '.note.com'))

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://editor.note.com/',
    'Origin': 'https://editor.note.com',
})

NOTE_KEY = 'nd5a979be088f'
NOTE_ID = 152196290

# 1. 現在のドラフト状態を確認
print('=== 現在の状態 ===')
resp = session.get(f'https://note.com/api/v3/notes/{NOTE_KEY}?draft=true')
if resp.status_code == 200:
    d = resp.json().get('data', {})
    print(f'status: {d.get("status")}')
    print(f'price: {d.get("price")}')
    print(f'separator: {d.get("separator")}')
    print(f'body_len: {len(d.get("body", ""))}')
else:
    print(f'Error: {resp.status_code} {resp.text[:200]}')

print()

# 2. draft_save で価格を1500に更新してみる
print('=== draft_save で価格1500に更新 ===')
resp2 = session.get(f'https://note.com/api/v3/notes/{NOTE_KEY}?draft=true')
draft_data = resp2.json().get('data', {})

# x-note-token (CSRF token) を取得
resp_editor = session.get(f'https://editor.note.com/notes/{NOTE_KEY}/edit/')
x_note_token = ''
if resp_editor.status_code == 200:
    import re
    m = re.search(r'x-note-token["\s:]+([a-zA-Z0-9_-]+)', resp_editor.text)
    if m:
        x_note_token = m.group(1)
        print(f'x-note-token: {x_note_token[:20]}...')
    else:
        print('x-note-token not found in page')

# Try draft_save with is_temp_saved=false (publish)
params = {'id': NOTE_ID, 'is_temp_saved': 'false'}
payload = {
    'body': draft_data.get('body', ''),
    'separator': draft_data.get('separator', ''),
    'title': draft_data.get('name', ''),
    'price': 1500,
    'type': 'paid',
    'is_temp_saved': False,
}

headers = {'Content-Type': 'application/json'}
if x_note_token:
    headers['x-note-token'] = x_note_token

resp3 = session.post(
    'https://note.com/api/v1/text_notes/draft_save',
    params=params,
    json=payload,
    headers=headers,
)
print(f'draft_save (is_temp_saved=false): {resp3.status_code}')
print(f'response: {resp3.text[:300]}')

print()

# 3. 公開 API を試す
print('=== 公開 API を試す ===')
for method, url, extra_params in [
    ('POST', f'https://note.com/api/v1/text_notes/{NOTE_ID}/publish', {}),
    ('PUT',  f'https://note.com/api/v1/text_notes/{NOTE_ID}', {'status': 'published'}),
    ('POST', f'https://note.com/api/v2/text_notes/{NOTE_ID}/publish', {}),
]:
    payload2 = {'price': 1500, 'type': 'paid', **extra_params}
    if method == 'POST':
        r = session.post(url, json=payload2, headers=headers)
    else:
        r = session.put(url, json=payload2, headers=headers)
    print(f'{method} {url}: {r.status_code}')
    if r.status_code not in (404, 405):
        print(f'  → {r.text[:200]}')
