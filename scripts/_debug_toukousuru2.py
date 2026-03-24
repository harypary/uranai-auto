"""投稿するボタンをさまざまな方法でクリックして検証するデバッグスクリプト"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

SCREENSHOT_DIR = Path('output/screenshots')
SCREENSHOT_DIR.mkdir(exist_ok=True)

requests_log = []
console_log = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox'],
    )
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()

    def on_request(req):
        if req.method in ('POST', 'PUT', 'PATCH') and 'sentry' not in req.url:
            try:
                requests_log.append({'method': req.method, 'url': req.url})
            except: pass

    def on_console(msg):
        try:
            console_log.append(f"[{msg.type}] {msg.text}")
        except: pass

    page.on('request', on_request)
    page.on('console', on_console)

    # Navigate to publish page directly
    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible(): btn.click(); time.sleep(1)
    except: pass

    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(4)
    page.click('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")', timeout=5000)
    time.sleep(4)
    print('URL:', page.url)

    # Screenshot to confirm position of 投稿する
    page.screenshot(path=str(SCREENSHOT_DIR / 'debug2_publish_page.png'))

    # Get button bounding box
    btn = page.query_selector('button:has-text("\u6295\u7a3f\u3059\u308b")')
    if btn:
        box = btn.bounding_box()
        print(f'投稿する button box: {box}')

        # Method 1: Regular click
        requests_log.clear()
        console_log.clear()
        btn.click()
        time.sleep(3)
        print(f'Method 1 (regular click): requests={len(requests_log)}, url={page.url}')
        if requests_log:
            for r in requests_log: print(f'  {r}')

        # Method 2: Click by coordinates
        if box:
            requests_log.clear()
            page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
            time.sleep(3)
            print(f'Method 2 (mouse.click): requests={len(requests_log)}, url={page.url}')

        # Method 3: JS click
        requests_log.clear()
        result = page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button'));
                const btn = btns.find(b => b.textContent.trim() === '\u6295\u7a3f\u3059\u308b');
                if (btn) {
                    const event = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                    btn.dispatchEvent(event);
                    return {found: true, onclick: btn.onclick !== null};
                }
                return {found: false};
            }
        """)
        time.sleep(3)
        print(f'Method 3 (JS dispatchEvent): result={result}, requests={len(requests_log)}, url={page.url}')

        # Check for errors
        page.screenshot(path=str(SCREENSHOT_DIR / 'debug2_after_clicks.png'))

        print('\nConsole logs:')
        for log in console_log[-20:]:
            try: print(f'  {log}')
            except: pass

        # Check for any visible error message
        error_text = page.evaluate("""
            () => {
                const errorEls = document.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"]');
                return Array.from(errorEls).map(e => e.textContent.trim().substring(0, 200)).join('\\n');
            }
        """)
        if error_text:
            print('\nError elements:', error_text)

        # Get all text visible on page
        visible_text = page.evaluate("""
            () => document.body.innerText.substring(0, 1000)
        """)
        print('\nPage text (first 1000):', visible_text[:500])

    else:
        print('投稿する button NOT FOUND')
        btns = page.query_selector_all('button')
        for b in btns:
            try: print(f'  btn: {b.inner_text()[:40]}')
            except: pass

    browser.close()
