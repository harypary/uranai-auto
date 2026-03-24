"""
note.com セッション初期化スクリプト

【実行方法】
このスクリプトは Claude Code のターミナルではなく、
Windows の PowerShell または コマンドプロンプトから直接実行してください。

  cd C:\\Users\\haryp\\game\\12.uranai
  python scripts/setup_note_session.py

ブラウザが開くので note.com にログインしてください。
"""

import json
import sys
from pathlib import Path

SESSION_FILE = Path(__file__).parent.parent / "output" / "note_session.json"


def setup_session():
    print("=" * 60)
    print("note.com セッション初期化")
    print("=" * 60)
    print()

    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright がインストールされていません")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    print("ブラウザを起動します...")
    print("note.com にログインしたら、このターミナルに戻って Enter を押してください。")
    print()

    with sync_playwright() as p:
        # システムのChromeを優先、なければPlaywrightのChromiumを使用
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--no-sandbox"],
            )
            print("[INFO] システムのChromeを使用")
        except Exception:
            browser = p.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            print("[INFO] Playwright Chromiumを使用")

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.goto("https://note.com/login")
        print(f"ブラウザが開きました: https://note.com/login")
        print()

        input("ログイン完了後、Enter キーを押してください >>> ")

        # セッション保存
        storage_state = context.storage_state()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, ensure_ascii=False, indent=2)

        cookie_count = len(storage_state.get("cookies", []))
        print()
        print(f"✅ セッション保存完了: {SESSION_FILE}")
        print(f"   Cookie数: {cookie_count}")
        print()
        print("以降の自動投稿が使えるようになりました！")
        print("次のステップ:")
        print("  python scripts/run_numerology.py   # 数秘術13記事を投稿")
        print("  python scripts/run_weekly.py       # 週次12星座を投稿")

        browser.close()


if __name__ == "__main__":
    setup_session()
