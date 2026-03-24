"""draft_save リクエストから x-note-token と正しいpayloadを取得する"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.sync_api import sync_playwright

with open('output/note_session.json') as f:
    state = json.load(f)

captured = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        storage_state=state,
    )
    page = ctx.new_page()

    def on_request(req):
        if 'draft_save' in req.url:
            try:
                captured['headers'] = dict(req.headers)
                captured['postData'] = req.post_data
                captured['url'] = req.url
            except: pass

    page.on('request', on_request)

    page.goto('https://editor.note.com/notes/nd5a979be088f/edit/', wait_until='networkidle', timeout=30000)
    time.sleep(4)
    try:
        btn = page.query_selector('button:has-text("\u4eca\u306f\u4fdd\u5b58\u3057\u306a\u3044")')
        if btn and btn.is_visible(): btn.click(); time.sleep(1)
    except: pass

    # trigger draft_save by clicking 公開に進む
    page.click('button:has-text("\u516c\u958b\u306b\u9032\u3080")', timeout=5000)
    time.sleep(4)

    # click 有料エリア設定 → triggers draft_save
    page.click('button:has-text("\u6709\u6599\u30a8\u30ea\u30a2\u8a2d\u5b9a")', timeout=5000)
    time.sleep(3)

    # also check navigator.webdriver
    webdriver = page.evaluate('navigator.webdriver')
    print(f'navigator.webdriver: {webdriver}')

    browser.close()

if 'headers' in captured:
    print('\n=== captured draft_save request ===')
    print(f'URL: {captured["url"]}')
    print('\nHeaders:')
    for k, v in captured['headers'].items():
        if k.lower() in ('x-note-token', 'content-type', 'authorization', 'cookie', 'x-requested-with', 'x-csrf-token'):
            print(f'  {k}: {v[:80]}')
    if captured.get('postData'):
        print(f'\nBody (first 500 chars):')
        print(captured['postData'][:500])

    # Save full data to file
    Path('output/captured_request.json').write_text(
        json.dumps({'url': captured['url'], 'headers': captured['headers'], 'postData': captured.get('postData', '')}, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    print('\nFull data saved to output/captured_request.json')
else:
    print('draft_save not captured')
