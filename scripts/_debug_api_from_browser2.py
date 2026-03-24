"""ブラウザ内からcredentials:includeでAPI呼び出し"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

NOTE_KEY = 'nd5a979be088f'
NOTE_ID = 152196290

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    )
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    page.goto(f'https://editor.note.com/notes/{NOTE_KEY}/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(3)

    output = []

    # Check draft status with credentials
    draft_data = page.evaluate(f"""
        async () => {{
            const resp = await fetch('https://note.com/api/v3/notes/{NOTE_KEY}?draft=true', {{
                credentials: 'include',
            }});
            const j = await resp.json();
            const d = j.data || {{}};
            return {{status: resp.status, note_status: d.status, price: d.price, body_len: (d.body||'').length}};
        }}
    """)
    output.append(f'Draft API: {draft_data}')

    # Try draft_save with is_temp_saved=false + price + credentials
    output.append('\n=== draft_save is_temp_saved=false + price ===')
    result = page.evaluate(f"""
        async () => {{
            const draftResp = await fetch('https://note.com/api/v3/notes/{NOTE_KEY}?draft=true', {{
                credentials: 'include',
            }});
            const draftData = (await draftResp.json()).data || {{}};

            const payload = {{
                body: draftData.body || '',
                body_length: (draftData.body || '').length,
                name: draftData.name || '',
                separator: draftData.separator || '',
                index: draftData.separator_index || null,
                is_lead_form: false,
                price: 1500,
                type: 'paid',
            }};

            const resp = await fetch(
                'https://note.com/api/v1/text_notes/draft_save?id={NOTE_ID}&is_temp_saved=false',
                {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    }},
                    body: JSON.stringify(payload),
                }}
            );
            const text = await resp.text();
            return {{status: resp.status, body: text.substring(0, 500)}};
        }}
    """)
    output.append(f'draft_save (is_temp_saved=false): {result}')

    # Try publish endpoints with credentials
    output.append('\n=== Trying publish endpoints ===')
    for endpoint, method, payload in [
        (f'/api/v1/text_notes/{NOTE_ID}/publish', 'POST', {'price': 1500, 'type': 'paid'}),
        (f'/api/v2/text_notes/{NOTE_ID}/publish', 'POST', {'price': 1500, 'type': 'paid'}),
        (f'/api/v1/text_notes/draft_save?id={NOTE_ID}&is_temp_saved=false', 'POST', None),
    ]:
        result = page.evaluate(f"""
            async () => {{
                const resp = await fetch(
                    'https://note.com{endpoint}',
                    {{
                        method: '{method}',
                        credentials: 'include',
                        headers: {{
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest',
                        }},
                        body: JSON.stringify({json.dumps(payload) if payload else '{}'}),
                    }}
                );
                const text = await resp.text();
                return {{status: resp.status, body: text.substring(0, 400)}};
            }}
        """)
        output.append(f'{method} {endpoint}: {result["status"]} -> {result["body"][:300]}')

    browser.close()

# Write results to file
Path('output/api_debug.txt').write_text('\n'.join(str(o) for o in output), encoding='utf-8')
print('Results saved to output/api_debug.txt')
