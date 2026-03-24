"""requests セッションで直接publish APIを試す"""
import json, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import requests

sys.stdout.reconfigure(encoding='utf-8')

with open('output/note_session.json') as f:
    s = json.load(f)

session = requests.Session()
for c in s.get('cookies', []):
    session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.note.com'))

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://editor.note.com/',
    'Origin': 'https://editor.note.com',
    'X-Requested-With': 'XMLHttpRequest',
})

NOTE_KEY = 'nd5a979be088f'
NOTE_ID = 152196290

# 1. Get draft content
print('=== Getting draft content ===')
resp = session.get(f'https://note.com/api/v3/notes/{NOTE_KEY}?draft=true')
data = resp.json().get('data', {})
print(f'status: {data.get("status")}, price: {data.get("price")}, separator: {str(data.get("separator",""))[:20]}')

# 2. Get x-note-token (CSRF) from editor page
print('\n=== Getting x-note-token ===')
resp_editor = session.get(f'https://editor.note.com/notes/{NOTE_KEY}/edit/')
x_note_token = ''
if resp_editor.status_code == 200:
    # Look for token in script tags
    m = re.search(r'["\']x-note-token["\']\s*[,:]\s*["\']([a-zA-Z0-9._-]+)["\']', resp_editor.text)
    if m:
        x_note_token = m.group(1)
        print(f'Found x-note-token: {x_note_token[:30]}...')
    else:
        # Try to find in meta tags
        m2 = re.search(r'<meta[^>]+name=["\']x-note-token["\'][^>]+content=["\']([^"\']+)["\']', resp_editor.text)
        if m2:
            x_note_token = m2.group(1)
            print(f'Found x-note-token (meta): {x_note_token[:30]}...')
        else:
            # Try cookies
            note_token = session.cookies.get('note_token') or session.cookies.get('_note_token')
            if note_token:
                x_note_token = note_token
                print(f'Using cookie token: {x_note_token[:30]}...')
            else:
                print('x-note-token NOT found')
                # Print all cookies
                for c in session.cookies:
                    if 'token' in c.name.lower():
                        print(f'  cookie: {c.name}={c.value[:20]}')

headers = {'Content-Type': 'application/json'}
if x_note_token:
    headers['x-note-token'] = x_note_token

# 3. Try draft_save with is_temp_saved=false (final publish)
print('\n=== draft_save is_temp_saved=false (with price) ===')
payload = {
    'body': data.get('body', ''),
    'body_length': len(data.get('body', '')),
    'name': data.get('name', ''),
    'separator': data.get('separator', ''),
    'index': data.get('separator_index'),
    'is_lead_form': False,
    'price': 1500,
    'type': 'paid',
}
resp3 = session.post(
    f'https://note.com/api/v1/text_notes/draft_save?id={NOTE_ID}&is_temp_saved=false',
    json=payload,
    headers=headers,
)
print(f'Status: {resp3.status_code}')
print(f'Response: {resp3.text[:500]}')

# 4. Check status after
print('\n=== Status after ===')
resp4 = session.get(f'https://note.com/api/v3/notes/{NOTE_KEY}?draft=true')
d4 = resp4.json().get('data', {})
print(f'status: {d4.get("status")}, price: {d4.get("price")}')
