"""React状態とfetchの詳細ログ"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

NOTE_KEY = 'nd5a979be088f'
SCREENSHOT_DIR = Path('output/screenshots')
output = []

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

    # Monkey-patch fetch before page loads
    page.add_init_script("""
        window.__fetchLog = [];
        const origFetch = window.fetch;
        window.fetch = function(...args) {
            const url = typeof args[0] === 'string' ? args[0] : args[0].url;
            window.__fetchLog.push('CALL: ' + url);
            return origFetch.apply(this, args).then(r => {
                window.__fetchLog.push('OK ' + r.status + ': ' + url);
                return r;
            }).catch(e => {
                window.__fetchLog.push('ERR ' + e.message + ': ' + url);
                throw e;
            });
        };
        const origXHR = XMLHttpRequest.prototype.open;
        window.__xhrLog = [];
        XMLHttpRequest.prototype.open = function(method, url, ...rest) {
            window.__xhrLog.push(method + ' ' + url);
            return origXHR.apply(this, [method, url, ...rest]);
        };
    """)

    console_msgs = []
    page.on('console', lambda m: console_msgs.append(f'[{m.type}] {m.text[:300]}'))

    page.goto(f'https://editor.note.com/notes/{NOTE_KEY}/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(3)

    # Dismiss conflict
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible(): btn.click(); time.sleep(1)
    except: pass

    # Click 公開に進む
    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(4)

    # Set price
    loc = page.locator('#price').first
    loc.wait_for(state='visible', timeout=5000)
    loc.click(click_count=3)
    time.sleep(0.2)
    loc.fill('1500')
    time.sleep(0.5)
    loc.press('Tab')
    output.append(f'Price: {loc.input_value()}')

    # Clear fetch log
    page.evaluate("window.__fetchLog = []; window.__xhrLog = [];")

    # Click 有料エリア設定
    page.click('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")', timeout=8000)
    time.sleep(5)
    output.append(f'/publish/ URL: {page.url}')

    # Check Next.js data
    next_data = page.evaluate("JSON.stringify(window.__NEXT_DATA__ || {})")
    next_d = json.loads(next_data)
    output.append(f'NEXT_DATA keys: {list(next_d.get("props", {}).get("pageProps", {}).keys())}')

    # Read current fetch log (during navigation to /publish/)
    fetch_log = page.evaluate("window.__fetchLog.slice(-20)")
    output.append(f'Fetch during nav: {fetch_log}')

    # Clear again
    page.evaluate("window.__fetchLog = []; window.__xhrLog = [];")
    console_msgs.clear()

    # Add button click listener
    page.evaluate("""
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '\u6295\u7a3f\u3059\u308b');
        if (btn) {
            btn.addEventListener('click', (e) => {
                window.__fetchLog.push('BTN_CLICK: isTrusted=' + e.isTrusted + ' target=' + e.target.tagName);
            }, true);
        } else {
            window.__fetchLog.push('BTN_NOT_FOUND');
        }
    """)

    # Click 投稿する
    page.click('button:has-text("\u6295\u7a3f\u3059\u308b")', timeout=5000)
    time.sleep(8)

    # Read logs
    fetch_log2 = page.evaluate("window.__fetchLog")
    xhr_log2 = page.evaluate("window.__xhrLog")
    output.append(f'\nAfter 投稿する click:')
    output.append(f'URL: {page.url}')
    output.append(f'fetchLog: {fetch_log2}')
    output.append(f'xhrLog: {xhr_log2}')
    output.append(f'Console errors: {[m for m in console_msgs if "error" in m.lower() or "Error" in m]}')

    # Get React fiber to check state
    react_info = page.evaluate("""
        () => {
            // Find React root
            const root = document.querySelector('#__next');
            if (!root) return {error: 'no __next'};

            // Try to find React fiber
            const fiberKey = Object.keys(root).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
            if (!fiberKey) return {error: 'no fiber key'};

            // Walk up to find the publish component state
            let fiber = root[fiberKey];
            let depth = 0;
            while (fiber && depth < 30) {
                try {
                    const state = fiber.memoizedState;
                    const props = fiber.memoizedProps;
                    if (props && typeof props === 'object') {
                        const keys = Object.keys(props);
                        if (keys.includes('price') || keys.includes('isPaid') || keys.includes('notePrice')) {
                            return {found: true, props_keys: keys, price_val: props.price || props.notePrice};
                        }
                    }
                } catch(e) {}
                fiber = fiber.return;
                depth++;
            }
            return {error: 'not found', depth};
        }
    """)
    output.append(f'React info: {react_info}')

    page.screenshot(path=str(SCREENSHOT_DIR / 'react_debug_after.png'))
    browser.close()

Path('output/react_debug.txt').write_text('\n'.join(str(o) for o in output), encoding='utf-8')
print('Saved to output/react_debug.txt')
