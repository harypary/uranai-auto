"""ネットワークリクエストを傍受して publish API を特定するデバッグスクリプト"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

requests_log = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )

    # Intercept requests
    page = ctx.new_page()

    def on_request(req):
        if '/api/' in req.url and req.method in ('POST', 'PUT', 'PATCH'):
            requests_log.append({'method': req.method, 'url': req.url, 'postData': req.post_data})

    page.on('request', on_request)

    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # dismiss conflict
    try:
        btn = page.query_selector('button:has-text("今は保存しない")')
        if btn and btn.is_visible():
            btn.click(); time.sleep(1)
    except: pass

    # click publish settings
    page.click('button:has-text("公開に進む")', timeout=5000)
    time.sleep(4)
    print('URL:', page.url)

    # Try clicking "有料エリア設定" button to see what happens
    try:
        btn = page.query_selector('button:has-text("有料エリア設定")')
        if btn:
            print('Clicking 有料エリア設定...')
            btn.click()
            time.sleep(3)
            print('URL after 有料エリア設定:', page.url)
            page.screenshot(path='output/screenshots/debug_after_yuryoarea.png')
    except Exception as e:
        print(f'有料エリア設定 click error: {e}')

    # Check for any "公開" related elements
    all_btns = page.query_selector_all('button, a')
    print('\nAll buttons/links:')
    for btn in all_btns:
        try:
            text = btn.inner_text().strip()
            if text:
                print(f'  {btn.tag_name()}: {text[:60]}')
        except: pass

    print('\nNetwork requests (POST/PUT/PATCH to /api/):')
    for r in requests_log:
        print(f"  {r['method']} {r['url']}")
        if r['postData']:
            print(f"    body: {r['postData'][:200]}")

    # Try to directly call the publish API with cookies
    cookies = ctx.cookies()
    print('\nCookies for API call:')
    important = [c for c in cookies if 'note' in c['name'].lower() or 'session' in c['name'].lower() or 'token' in c['name'].lower()]
    for c in important[:5]:
        print(f"  {c['name']}={c['value'][:30]}...")

    browser.close()
