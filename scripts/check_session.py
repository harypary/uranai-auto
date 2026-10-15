"""
note.com セッション有効性チェック。
exit 0: 有効  /  exit 1: 期限切れ or 未ログイン

各投稿ワークフローの冒頭から呼ばれ、ログに「投稿前のセッション状態」を残す。
期限切れだった場合は週次の refresh_note_session.py でも復旧できないため、
ローカルで setup_note_session.py を実行して暗号化セッションを push する必要がある。
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()


def load_session() -> dict:
    """投稿時とまったく同じ経路で読む（暗号化ファイル → 環境変数 → ローカルファイル）。

    ここだけ Secret しか見ないと、延長済みの暗号化セッションが有効でも
    「期限切れ」と誤判定してしまう。
    """
    from src.publishers.note_publisher import NotePublisher

    try:
        return NotePublisher()._load_session() or {}
    except FileNotFoundError:
        return {}


def check_session(storage_state: dict) -> bool:
    """Playwright でログイン状態を確認する。True = ログイン済み。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 未インストール")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            storage_state=storage_state,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto("https://note.com/notes", wait_until="networkidle", timeout=20000)
            time.sleep(2)

            # ログイン済みであれば note 管理ページが開く（リダイレクトなし）
            is_logged_in = "note.com/notes" in page.url and "login" not in page.url

            # APIで確認
            result = page.evaluate("""async () => {
                const r = await fetch('https://note.com/api/v2/current_user/email',
                    {credentials: 'include'});
                return {ok: r.ok, status: r.status};
            }""")
            api_ok = result.get("ok", False)

            print(f"URL check: {is_logged_in}  API check: {api_ok}  URL: {page.url}")
            return is_logged_in and api_ok
        finally:
            browser.close()


def main():
    storage_state = load_session()
    if not storage_state:
        print("ERROR: セッションファイルが見つかりません")
        sys.exit(1)

    print("セッション有効性チェック中...")
    valid = check_session(storage_state)

    if valid:
        print("OK: セッション有効")
        sys.exit(0)
    else:
        print("WARN: セッション無効または期限切れ")
        sys.exit(1)


if __name__ == "__main__":
    main()
