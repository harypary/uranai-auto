"""公開設定ページの構造をデバッグするスクリプト"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

SCREENSHOT_DIR = Path('output/screenshots')
SCREENSHOT_DIR.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 1800},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()
    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)

    # dismiss conflict if any
    try:
        btn = page.query_selector('button:has-text("今は保存しない")')
        if btn and btn.is_visible():
            btn.click()
            time.sleep(1)
    except Exception as e:
        print(f'conflict dismiss: {e}')

    # click publish button
    page.click('button:has-text("公開に進む")', timeout=5000)
    time.sleep(5)

    print('URL:', page.url)

    # Take full page screenshot
    page.screenshot(path=str(SCREENSHOT_DIR / 'debug_full_page.png'), full_page=True)
    print('Full page screenshot saved')

    # Find ALL interactive elements
    js = """
    () => {
        const sel = 'button, a, input, [role="button"], [onclick]';
        const els = Array.from(document.querySelectorAll(sel));
        return els.map(el => {
            const text = (el.innerText || el.value || el.textContent || '').trim().substring(0, 80);
            return {
                tag: el.tagName,
                text: text,
                disabled: el.disabled || false,
                cls: (el.className || '').substring(0, 60)
            };
        }).filter(e => e.text.length > 0);
    }
    """
    elements = page.evaluate(js)
    print('\n=== ALL INTERACTIVE ELEMENTS ===')
    for el in elements:
        print(el)

    # Also search for any element containing 公開
    js2 = """
    () => {
        const all = Array.from(document.querySelectorAll('*'));
        return all
            .filter(el => el.childNodes.length > 0 &&
                         Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.includes('\u516c\u958b')))
            .map(el => ({tag: el.tagName, text: el.textContent.trim().substring(0, 100), cls: el.className.substring(0, 40)}));
    }
    """
    publish_els = page.evaluate(js2)
    print('\n=== ELEMENTS CONTAINING 公開 ===')
    for el in publish_els:
        print(el)

    browser.close()
