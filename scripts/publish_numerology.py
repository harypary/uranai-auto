"""
数秘術ドラフト記事を有料（¥1,500）で公開するスクリプト。

前提条件:
  - note.com で本人情報登録（クリエイター情報）が完了していること
  - output/note_session.json が有効なこと（期限切れなら setup_note_session.py を再実行）

使い方:
    python scripts/publish_numerology.py
    python scripts/publish_numerology.py --lp 1 3 5
"""

import argparse
import json
import os
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from src.utils.logger import get_logger

logger = get_logger("publish_numerology")

DRAFT_EDIT_URLS = {
    1:  "https://editor.note.com/notes/nd5a979be088f/edit/",
    2:  "https://editor.note.com/notes/n59954526328b/edit/",
    3:  "https://editor.note.com/notes/n91310d3c8f59/edit/",
    4:  "https://editor.note.com/notes/n598cdbba9c79/edit/",
    5:  "https://editor.note.com/notes/nf01a0522f7d3/edit/",
    6:  "https://editor.note.com/notes/n02941a418015/edit/",
    7:  "https://editor.note.com/notes/n2c7416ef6685/edit/",
    8:  "https://editor.note.com/notes/na10db99a3ff1/edit/",
    9:  "https://editor.note.com/notes/ndc3840f439a0/edit/",
    11: "https://editor.note.com/notes/n57f13dc0eb6a/edit/",
    22: "https://editor.note.com/notes/n48cb689302a4/edit/",
    33: "https://editor.note.com/notes/nf9289ce3dbe6/edit/",
}

PRICE = 1500
INTERVAL_SEC = 40
SESSION_FILE = Path(__file__).parent.parent / "output" / "note_session.json"
SCREENSHOT_DIR = Path(__file__).parent.parent / "output" / "screenshots"


def _wait(seconds: float):
    time.sleep(seconds + random.uniform(0, 0.3))


def load_session() -> dict:
    session_b64 = os.environ.get("NOTE_SESSION_B64")
    if session_b64:
        import base64
        return json.loads(base64.b64decode(session_b64).decode("utf-8"))
    with open(SESSION_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_screenshot(page: Page, name: str):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path))
    logger.debug(f"スクリーンショット保存: {path}")


def publish_draft(page: Page, lp_num: int, draft_url: str) -> str:
    """ドラフトを開いて有料（¥1,500）で公開し、公開後URLを返す"""

    logger.info(f"LP{lp_num}: ドラフト読み込み中... {draft_url}")
    page.goto(draft_url, wait_until="networkidle", timeout=30000)
    _wait(4)

    save_screenshot(page, f"lp{lp_num}_01_loaded")

    # ─── 「複数画面で編集」ダイアログが出たら「今は保存しない」を押す ───
    try:
        btn = page.query_selector('button:has-text("今は保存しない")')
        if btn and btn.is_visible():
            btn.click()
            logger.info(f"LP{lp_num}: 複数画面ダイアログを閉じた")
            _wait(2)
    except Exception:
        pass

    # ─── 公開ボタンをクリック ───
    publish_btn_selectors = [
        'button:has-text("公開に進む")',
        'button:has-text("公開設定へ")',
        'button:has-text("公開する")',
    ]
    clicked = False
    for sel in publish_btn_selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            page.click(sel)
            clicked = True
            logger.info(f"LP{lp_num}: 公開ボタンクリック ({sel})")
            break
        except Exception:
            continue

    if not clicked:
        save_screenshot(page, f"lp{lp_num}_err_no_publish_btn")
        raise RuntimeError(f"LP{lp_num}: 公開ボタンが見つかりません")

    _wait(3)
    save_screenshot(page, f"lp{lp_num}_02_settings")

    # ─── 価格を 1500 に設定（公開設定ページで）───
    _set_price(page, lp_num, PRICE)
    _wait(1)

    save_screenshot(page, f"lp{lp_num}_03_price_set")

    # ─── 「有料エリア設定」ボタンをクリック → /publish/ へ遷移 ───
    try:
        page.click('button:has-text("有料エリア設定")', timeout=8000)
        logger.info(f"LP{lp_num}: 有料エリア設定クリック → /publish/ へ遷移")
    except Exception as e:
        save_screenshot(page, f"lp{lp_num}_err_no_yuryoarea_btn")
        raise RuntimeError(f"LP{lp_num}: 有料エリア設定ボタンが見つかりません: {e}")

    _wait(4)
    save_screenshot(page, f"lp{lp_num}_04_publish_page")
    logger.info(f"LP{lp_num}: /publish/ URL = {page.url}")

    # ─── 「投稿する」ボタンをクリック ───
    try:
        page.click('button:has-text("投稿する")', timeout=8000)
        logger.info(f"LP{lp_num}: 投稿するクリック（1回目）")
    except Exception as e:
        save_screenshot(page, f"lp{lp_num}_err_no_toukousuru_btn")
        all_btns = [el.inner_text().strip() for el in page.query_selector_all('button')]
        raise RuntimeError(f"LP{lp_num}: 投稿するボタンが見つかりません: {e} | buttons={all_btns}")

    _wait(3)
    save_screenshot(page, f"lp{lp_num}_05_after_click1")

    # 確認ダイアログが出た場合（「公開する」「投稿する」の2段階確認）
    for btn_text in ["公開する", "投稿する", "OK", "確認"]:
        try:
            btn = page.query_selector(f'button:has-text("{btn_text}")')
            if btn and btn.is_visible():
                btn.click()
                logger.info(f"LP{lp_num}: 確認ダイアログ「{btn_text}」クリック")
                _wait(3)
                break
        except Exception:
            continue

    _wait(5)
    save_screenshot(page, f"lp{lp_num}_06_final")

    current_url = page.url
    logger.info(f"LP{lp_num}: 完了 → {current_url}")
    return current_url


def _select_paid_type(page: Page, lp_num: int):
    """公開設定パネルで「有料」を選択（既に選択済みの場合はスキップ）"""
    # JS で有料ラジオボタンを探してクリック
    result = page.evaluate("""
        (() => {
            // 有料ラジオボタンまたはラベルを探す
            const radios = document.querySelectorAll('input[type="radio"]');
            for (const r of radios) {
                const label = document.querySelector(`label[for="${r.id}"]`);
                const text = label ? label.textContent : r.parentElement?.textContent || '';
                if (text.includes('有料') && !r.checked) {
                    r.click();
                    return 'clicked';
                }
                if (text.includes('有料') && r.checked) {
                    return 'already_selected';
                }
            }
            // ラベルで直接探す
            const labels = document.querySelectorAll('label');
            for (const l of labels) {
                if (l.textContent.trim() === '有料') {
                    l.click();
                    return 'label_clicked';
                }
            }
            return 'not_found';
        })()
    """)
    logger.debug(f"LP{lp_num}: 有料選択結果={result}")


def _set_price(page: Page, lp_num: int, price: int):
    """価格フィールドに金額をPlaywrightのfill()で入力（React state更新確実）"""
    # Locator API (id="price" は確認済み)
    price_locators = [
        '#price',
        '.sc-85966dc5-0',
        '.jphToq',
    ]
    filled = False
    for sel in price_locators:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state='visible', timeout=5000)
            loc.click(click_count=3)    # 全選択
            _wait(0.3)
            loc.fill(str(price))        # Playwright fill → React stateも更新
            _wait(0.5)
            loc.press('Tab')            # フォーカスを外してblur発火
            val = loc.input_value()
            logger.info(f"LP{lp_num}: 価格設定完了 {price}円 ({sel}) → 確認値={val}")
            filled = True
            break
        except Exception:
            continue

    if not filled:
        logger.warning(f"LP{lp_num}: 価格フィールドが見つかりません")


def main():
    parser = argparse.ArgumentParser(description="数秘術ドラフト記事を有料（¥1500）で公開")
    parser.add_argument(
        "--lp", nargs="+", type=int,
        choices=list(DRAFT_EDIT_URLS.keys()),
        help="処理するライフパスナンバー（省略時は全12本）",
    )
    args = parser.parse_args()

    target_lps = args.lp if args.lp else list(DRAFT_EDIT_URLS.keys())
    logger.info(f"公開対象: LP{target_lps}  価格: {PRICE}円")

    storage_state = load_session()
    results = []

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context: BrowserContext = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            permissions=["clipboard-read", "clipboard-write"],
            storage_state=storage_state,
        )
        page: Page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        # window.confirm() ダイアログを自動承認（投稿確認ダイアログ）
        page.on("dialog", lambda dialog: dialog.accept())

        for i, lp_num in enumerate(target_lps):
            draft_url = DRAFT_EDIT_URLS[lp_num]
            try:
                url = publish_draft(page, lp_num, draft_url)
                results.append({"lp": lp_num, "status": "完了", "url": url})
            except Exception as e:
                logger.error(f"LP{lp_num}: 公開失敗 - {e}")
                results.append({"lp": lp_num, "status": "失敗", "error": str(e)})

            if i < len(target_lps) - 1:
                logger.info(f"{INTERVAL_SEC}秒待機中...")
                time.sleep(INTERVAL_SEC)

        browser.close()

    # ─── サマリー ───
    logger.info("=" * 50)
    logger.info("公開結果サマリー")
    logger.info("=" * 50)
    for r in results:
        if "error" in r:
            logger.error(f"LP{r['lp']}: {r['status']} - {r['error']}")
        else:
            logger.info(f"LP{r['lp']}: {r['status']} {r.get('url', '')}")

    succeeded = sum(1 for r in results if r["status"] == "完了")
    logger.info(f"完了: {succeeded}/{len(target_lps)} 件")


if __name__ == "__main__":
    main()
