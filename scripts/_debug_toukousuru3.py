"""webdriver fix + 投稿する クリック時の詳細デバッグ"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

SCREENSHOT_DIR = Path('output/screenshots')
SCREENSHOT_DIR.mkdir(exist_ok=True)

requests_log = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()
    # BOT detection bypass
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def on_request(req):
        if 'sentry' not in req.url:
            try:
                requests_log.append({'method': req.method, 'url': req.url, 'postData': (req.post_data or '')[:200]})
            except: pass

    def on_response(resp):
        if '/api/' in resp.url:
            try:
                print(f"  RESPONSE: {resp.status} {resp.request.method} {resp.url}")
                if resp.status not in (200, 204):
                    print(f"    body: {resp.text()[:300]}")
            except: pass

    page.on('request', on_request)
    page.on('response', on_response)

    # Full publish flow
    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # Dismiss conflict dialog
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible(): btn.click(); time.sleep(1)
    except: pass

    # Click 公開に進む
    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(4)
    print('Settings page URL:', page.url)

    # Set price using #price ID (Locator API)
    try:
        inp = page.locator('#price')
        inp.wait_for(timeout=5000)
        inp.click(click_count=3)
        time.sleep(0.3)
        inp.fill('1500')
        time.sleep(0.5)
        inp.press('Tab')
        val = inp.input_value()
        print(f'Price set to: {val}')
    except Exception as e:
        print(f'Price input error: {e}')

    page.screenshot(path=str(SCREENSHOT_DIR / 'debug3_settings.png'))
    time.sleep(1)

    # Click 有料エリア設定
    page.click('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")', timeout=8000)
    time.sleep(5)
    print('/publish/ URL:', page.url)
    page.screenshot(path=str(SCREENSHOT_DIR / 'debug3_publish_page.png'))

    # Clear request log
    requests_log.clear()
    print('\nwebdriver value:', page.evaluate('navigator.webdriver'))

    # Find 投稿する button
    btn = page.query_selector('button:has-text("\u6295\u7a3f\u3059\u308b")')
    if btn:
        print(f'Button found: visible={btn.is_visible()}, text={btn.inner_text()}')
        print('Clicking 投稿する...')
        btn.click()
        time.sleep(8)
        print('URL after click:', page.url)
        print(f'Requests made: {len(requests_log)}')
        for r in requests_log:
            print(f"  {r['method']} {r['url']}")
            if r['postData']:
                print(f"    body: {r['postData']}")
    else:
        print('投稿する NOT FOUND')
        btns = page.query_selector_all('button')
        for b in btns:
            try: print(f'  btn: {b.inner_text()[:40]}')
            except: pass

    # Check for errors/modals
    text = page.evaluate("() => document.body.innerText.substring(0, 500)")
    print('\nPage text:', text[:300])
    page.screenshot(path=str(SCREENSHOT_DIR / 'debug3_after_click.png'))

    browser.close()
