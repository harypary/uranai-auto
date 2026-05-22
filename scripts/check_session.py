"""
note.com セッション有効性チェック。
exit 0: 有効  /  exit 1: 期限切れ or 未ログイン

GitHub Actions の daily_note.yml から呼ばれる。
失敗時に自動で renew_note_session.py を呼ぶためのゲートとして機能する。
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()


def load_session() -> dict:
    b64 = os.environ.get("NOTE_SESSION_B64", "").strip()
    if b64:
        import base64
        return json.loads(base64.b64decode(b64).decode("utf-8"))
    session_file = Path("output/note_session.json")
    if session_file.exists():
        return json.loads(session_file.read_text(encoding="utf-8"))
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
