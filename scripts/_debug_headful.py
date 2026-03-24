"""headfulで投稿するクリックを目視確認するデバッグスクリプト"""
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
    browser = p.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
        slow_mo=500,
    )
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def on_request(req):
        if 'sentry' not in req.url and req.method in ('POST', 'PUT', 'PATCH'):
            try:
                requests_log.append({'method': req.method, 'url': req.url})
            except: pass

    page.on('request', on_request)

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

    # Set price
    try:
        loc = page.locator('#price').first
        loc.wait_for(state='visible', timeout=5000)
        loc.click(click_count=3)
        time.sleep(0.3)
        loc.fill('1500')
        time.sleep(0.5)
        loc.press('Tab')
        print(f'Price: {loc.input_value()}')
    except Exception as e:
        print(f'Price error: {e}')

    time.sleep(2)
    page.screenshot(path=str(SCREENSHOT_DIR / 'headful_settings.png'))

    # Click 有料エリア設定
    page.click('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")', timeout=8000)
    time.sleep(5)

    # Listen to console errors
    console_log = []
    page.on('console', lambda msg: console_log.append(f'[{msg.type}] {msg.text[:200]}'))

    page.screenshot(path=str(SCREENSHOT_DIR / 'headful_publish_page.png'))
    print('URL:', page.url)

    # Check for any overlay elements covering the button
    overlay_check = page.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => b.textContent.trim() === '\u6295\u7a3f\u3059\u308b');
            if (!btn) return {found: false};
            const rect = btn.getBoundingClientRect();
            const centerX = rect.left + rect.width/2;
            const centerY = rect.top + rect.height/2;
            const topEl = document.elementFromPoint(centerX, centerY);
            return {
                found: true,
                disabled: btn.disabled,
                ariaDisabled: btn.getAttribute('aria-disabled'),
                rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                topElement: topEl ? topEl.tagName + '.' + topEl.className.substring(0, 50) : null,
                isButton: topEl === btn,
            };
        }
    """)
    print(f'Button info: {overlay_check}')

    requests_log.clear()
    page.click('button:has-text("\u6295\u7a3f\u3059\u308b")', timeout=5000)
    time.sleep(8)

    print(f'URL after: {page.url}')
    print(f'Requests: {len(requests_log)}')
    for r in requests_log:
        print(f'  {r["method"]} {r["url"]}')

    # Save errors
    errors = [l for l in console_log if 'error' in l.lower() or 'Error' in l]
    for e in errors:
        print(f'Console: {e[:200]}')

    page.screenshot(path=str(SCREENSHOT_DIR / 'headful_after_click.png'))

    # Wait a bit to see what happens
    time.sleep(5)
    page.screenshot(path=str(SCREENSHOT_DIR / 'headful_final.png'))
    print('Final URL:', page.url)

    browser.close()
