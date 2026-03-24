"""有料エリア設定クリック後の /publish/ ページを調査"""
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
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 1800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()

    def on_request(req):
        if '/api/' in req.url and req.method in ('POST', 'PUT', 'PATCH'):
            try:
                requests_log.append({'method': req.method, 'url': req.url})
            except: pass

    page.on('request', on_request)

    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # dismiss conflict
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible():
            btn.click(); time.sleep(1)
    except: pass

    page.screenshot(path=str(SCREENSHOT_DIR / 'p2_01_editor.png'))

    # click publish settings
    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(4)
    print('URL after 公開に進む:', page.url)
    page.screenshot(path=str(SCREENSHOT_DIR / 'p2_02_settings.png'))

    # set price using class selector
    try:
        price_input = page.query_selector('.sc-85966dc5-0')
        if price_input:
            js = """
            (inp) => {
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(inp, '1500');
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                return 'price set to: ' + inp.value;
            }
            """
            result = page.evaluate(js, price_input)
            print('Price:', result)
    except Exception as e:
        print(f'Price set error: {e}')

    time.sleep(1)
    page.screenshot(path=str(SCREENSHOT_DIR / 'p2_03_price_set.png'))

    # Click 有料エリア設定 -> navigates to /publish/
    try:
        btn = page.query_selector('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")')
        if btn:
            btn.click()
            time.sleep(4)
            print('URL after 有料エリア設定:', page.url)
        else:
            print('有料エリア設定 button NOT found')
    except Exception as e:
        print(f'有料エリア設定 error: {e}')

    page.screenshot(path=str(SCREENSHOT_DIR / 'p2_04_publish_page.png'), full_page=True)
    print('Full page screenshot saved: p2_04_publish_page.png')

    # Find ALL elements on /publish/ page
    els = page.query_selector_all('button, a, input[type=submit]')
    print('\nElements on /publish/ page:')
    for el in els:
        try:
            text = el.inner_text().strip()
            if text:
                tag = el.evaluate('el => el.tagName')
                disabled = el.evaluate('el => el.disabled')
                print(f'  [{tag}] {text[:60]} (disabled={disabled})')
        except: pass

    print('\nNetwork requests:')
    for r in requests_log:
        print(f"  {r['method']} {r['url']}")

    browser.close()
