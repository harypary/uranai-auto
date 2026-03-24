"""「投稿する」クリック時の network request を記録するデバッグスクリプト"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

SCREENSHOT_DIR = Path('output/screenshots')
SCREENSHOT_DIR.mkdir(exist_ok=True)

requests_log = []
responses_log = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()

    def on_request(req):
        if '/api/' in req.url and req.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            try:
                requests_log.append({
                    'method': req.method,
                    'url': req.url,
                    'postData': (req.post_data or '')[:500]
                })
            except: pass

    def on_response(resp):
        if '/api/' in resp.url and resp.request.method in ('POST', 'PUT', 'PATCH'):
            try:
                responses_log.append({
                    'method': resp.request.method,
                    'url': resp.url,
                    'status': resp.status,
                    'body': resp.text()[:300]
                })
            except: pass

    page.on('request', on_request)
    page.on('response', on_response)

    # 1. Editor → settings
    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible(): btn.click(); time.sleep(1)
    except: pass

    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(4)
    print('Settings URL:', page.url)

    # 2. Navigate to /publish/
    btn = page.query_selector('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")')
    if btn:
        btn.click()
        time.sleep(4)
        print('/publish/ URL:', page.url)
    else:
        print('有料エリア設定 NOT FOUND')

    page.screenshot(path=str(SCREENSHOT_DIR / 'debug_toukousuru_before.png'))

    # 3. Clear request log, then click 投稿する
    requests_log.clear()
    responses_log.clear()

    btn = page.query_selector('button:has-text("\u6295\u7a3f\u3059\u308b")')
    if btn:
        print('Clicking 投稿する...')
        btn.click()
        time.sleep(5)
        print('URL after 投稿する:', page.url)
        page.screenshot(path=str(SCREENSHOT_DIR / 'debug_toukousuru_after.png'))
    else:
        print('投稿する NOT FOUND')
        btns = page.query_selector_all('button')
        for b in btns:
            try: print(' btn:', b.inner_text().strip()[:40])
            except: pass

    print('\nNetwork requests after 投稿する:')
    for r in requests_log:
        print(f"  {r['method']} {r['url']}")
        if r['postData']:
            try:
                print(f"    body: {r['postData']}")
            except: pass

    print('\nNetwork responses:')
    for r in responses_log:
        print(f"  {r['status']} {r['method']} {r['url']}")
        try:
            print(f"    body: {r['body']}")
        except: pass

    # Also check if there's a new modal or error
    all_text = page.evaluate("""
        () => {
            const modals = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, [class*="modal"], [class*="error"]');
            return Array.from(modals).map(m => m.textContent.trim().substring(0, 200)).join('\\n---\\n');
        }
    """)
    if all_text.strip():
        print('\nModals/dialogs found:')
        print(all_text)

    browser.close()
