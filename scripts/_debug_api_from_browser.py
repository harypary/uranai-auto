"""ブラウザ内からfetch APIで直接公開APIを呼び出すデバッグ"""
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

    # Navigate to the note page first to get cookies in context
    page.goto(f'https://editor.note.com/notes/{NOTE_KEY}/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(3)

    # Get x-note-token from page
    x_note_token = page.evaluate("""
        () => {
            // Try to find x-note-token in window object, meta tags, or cookies
            const metaTags = document.querySelectorAll('meta');
            for (const m of metaTags) {
                const name = m.getAttribute('name') || m.getAttribute('property');
                if (name && name.toLowerCase().includes('note-token')) {
                    return m.getAttribute('content');
                }
            }
            // Try window object
            if (window.__NOTE_TOKEN) return window.__NOTE_TOKEN;
            if (window.noteToken) return window.noteToken;
            // Try from XHR headers stored in window
            return null;
        }
    """)
    print(f'x-note-token from meta: {x_note_token}')

    # Get the current draft data via API call from browser
    draft_data = page.evaluate(f"""
        async () => {{
            const resp = await fetch('https://note.com/api/v3/notes/{NOTE_KEY}?draft=true');
            return await resp.json();
        }}
    """)
    data = draft_data.get('data', {})
    print(f'Current: status={data.get("status")}, price={data.get("price")}, body_len={len(data.get("body", ""))}')

    # Try calling draft_save with is_temp_saved=false (which might publish)
    print('\n=== Trying draft_save with is_temp_saved=false ===')
    result = page.evaluate(f"""
        async () => {{
            const draftResp = await fetch('https://note.com/api/v3/notes/{NOTE_KEY}?draft=true');
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
    print(f'draft_save result: {result}')

    # Try various publish endpoints from browser
    print('\n=== Trying publish endpoints ===')
    for endpoint, method in [
        (f'/api/v1/text_notes/{NOTE_ID}/publish', 'POST'),
        (f'/api/v2/text_notes/{NOTE_ID}/publish', 'POST'),
        (f'/api/v3/text_notes/{NOTE_ID}/publish', 'POST'),
        (f'/api/v1/text_notes/{NOTE_KEY}/publish', 'POST'),
    ]:
        result = page.evaluate(f"""
            async () => {{
                const resp = await fetch(
                    'https://note.com{endpoint}',
                    {{
                        method: '{method}',
                        headers: {{
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest',
                        }},
                        body: JSON.stringify({{price: 1500, type: 'paid'}}),
                    }}
                );
                const text = await resp.text();
                return {{status: resp.status, body: text.substring(0, 300)}};
            }}
        """)
        print(f'{method} {endpoint}: {result["status"]} -> {result["body"][:200]}')

    # Check current status after attempts
    print('\n=== Current status ===')
    status = page.evaluate(f"""
        async () => {{
            const resp = await fetch('https://note.com/api/v3/notes/{NOTE_KEY}?draft=true');
            const d = (await resp.json()).data || {{}};
            return {{status: d.status, price: d.price}};
        }}
    """)
    print(f'After attempts: {status}')

    browser.close()
