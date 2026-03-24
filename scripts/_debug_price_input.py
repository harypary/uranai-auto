"""価格inputのセレクターを調査するデバッグスクリプト"""
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
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible(): btn.click(); time.sleep(1)
    except: pass

    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(3)

    # Print ALL inputs on settings page
    inputs_info = page.evaluate("""
        () => {
            const inputs = document.querySelectorAll('input');
            return Array.from(inputs).map((inp, i) => ({
                index: i,
                type: inp.type,
                name: inp.name,
                value: inp.value,
                className: inp.className,
                placeholder: inp.placeholder,
                visible: inp.offsetParent !== null,
                id: inp.id,
            }));
        }
    """)
    print(f"Total inputs: {len(inputs_info)}")
    for info in inputs_info:
        print(f"  [{info['index']}] type={info['type']} name={info['name']} value={info['value']} class={info['className'][:60]} visible={info['visible']}")

    # Try to set price using direct JS (find input near 価格 label)
    result = page.evaluate("""
        () => {
            // Find all labels
            const labels = document.querySelectorAll('label');
            for (const label of labels) {
                if (label.textContent.includes('\u4fa1\u683c')) {
                    const forId = label.getAttribute('for');
                    const inp = forId ? document.getElementById(forId) : label.querySelector('input');
                    if (inp) return {found: true, id: forId, class: inp.className, value: inp.value};
                }
            }
            // Try finding numeric input
            const inputs = document.querySelectorAll('input[type="number"], input[type="text"]');
            for (const inp of inputs) {
                if (inp.value && !isNaN(parseInt(inp.value)) && inp.offsetParent !== null) {
                    return {found: true, id: inp.id, class: inp.className, value: inp.value, by: 'numeric'};
                }
            }
            return {found: false};
        }
    """)
    print(f"\nPrice input search result: {result}")

    # Screenshot current state
    page.screenshot(path=str(SCREENSHOT_DIR / 'debug_price_settings.png'), full_page=True)
    print("Screenshot saved: debug_price_settings.png")

    browser.close()
