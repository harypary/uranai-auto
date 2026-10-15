"""note.com セッション維持（GitHub Actions から毎週実行）

note のセッションは約3か月有効で、アクセスするたびに有効期限が延びる。
保存済みセッションで note を開いてログイン状態を確認し、延長されたセッションを暗号化保存する
（ワークフローがコミットする）。ログイン画面に reCAPTCHA があるため、パスワードでの自動ログインは行わない。
セッションが切れていた場合はエラー終了し、GitHub から失敗通知が届く。
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.publishers.note_publisher import NOTE_BASE_URL, NotePublisher, is_logged_in, persist_session

JST = timezone(timedelta(hours=9))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    state = NotePublisher()._load_session()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(storage_state=state, viewport={"width": 1280, "height": 900},
                                      user_agent=USER_AGENT)
        page = context.new_page()
        page.goto(NOTE_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        if not is_logged_in(context):
            browser.close()
            print("ERROR: note のセッションが切れています。ローカルで python scripts/setup_note_session.py を実行し、"
                  "新しいセッションを暗号化して push してください")
            sys.exit(1)
        user = context.request.get(f"{NOTE_BASE_URL}/api/v2/current_user").json().get("data") or {}
        refreshed = context.storage_state()
        persist_session(refreshed)
        browser.close()

    print(f"ログイン確認OK: {user.get('nickname')}（note.com/{user.get('urlname')}）")
    expires = next((c["expires"] for c in refreshed["cookies"] if c["name"] == "_note_session_v5"), None)
    if expires:
        print(f"セッション有効期限: {datetime.fromtimestamp(expires, JST):%Y-%m-%d %H:%M}（JST）")


if __name__ == "__main__":
    main()
