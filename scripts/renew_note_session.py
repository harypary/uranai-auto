"""
note.com セッション自動更新スクリプト

【用途】
- GitHub Actions から毎月自動実行（renew_session.yml）
- ローカルからも手動実行可能

【動作】
1. Playwright で note.com に自動ログイン（NOTE_EMAIL / NOTE_PASSWORD 使用）
2. 新しいセッションを output/note_session.json に保存
3. GITHUB_PAT が設定されていれば GitHub Secret の NOTE_SESSION_B64 を自動更新

【必要な環境変数（.env or GitHub Secrets）】
  NOTE_EMAIL        : note.com ログインメール
  NOTE_PASSWORD     : note.com ログインパスワード
  GITHUB_PAT        : GitHub PAT（repo + secrets write 権限）  ← 新規
  GITHUB_REPO       : "ユーザー名/リポジトリ名"               ← 新規
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

SESSION_FILE = Path(__file__).parent.parent / "output" / "note_session.json"

NOTE_EMAIL    = os.getenv("NOTE_EMAIL", "")
NOTE_PASSWORD = os.getenv("NOTE_PASSWORD", "")
GITHUB_PAT    = os.getenv("GH_PAT", "")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "")  # "username/repo"


# ──────────────────────────────────────────────
# 1. Playwright 自動ログイン
# ──────────────────────────────────────────────
def login_and_save_session() -> dict:
    from playwright.sync_api import sync_playwright

    print("[1/3] note.com に自動ログイン中...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # ログインページ
        page.goto("https://note.com/login", wait_until="networkidle")
        time.sleep(2)

        # メールアドレス入力
        page.fill('input[name="email"], input[type="email"]', NOTE_EMAIL)
        time.sleep(0.5)

        # パスワード入力
        page.fill('input[name="password"], input[type="password"]', NOTE_PASSWORD)
        time.sleep(0.5)

        # ログインボタンクリック
        page.click('button[type="submit"], button:has-text("ログイン")')
        time.sleep(4)

        # ログイン確認（ダッシュボードか記事一覧へ遷移するはず）
        current_url = page.url
        if "login" in current_url:
            raise RuntimeError(f"ログイン失敗: まだログインページにいます ({current_url})")

        print(f"    ログイン成功: {current_url}")

        # セッション保存
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        storage_state = context.storage_state()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, ensure_ascii=False, indent=2)

        browser.close()

    cookie_count = len(storage_state.get("cookies", []))
    print(f"    セッション保存完了 (Cookie数: {cookie_count}): {SESSION_FILE}")
    return storage_state


# ──────────────────────────────────────────────
# 2. Base64 エンコード
# ──────────────────────────────────────────────
def encode_session_to_b64() -> str:
    with open(SESSION_FILE, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    print(f"[2/3] Base64 エンコード完了 ({len(b64)} chars)")
    return b64


# ──────────────────────────────────────────────
# 3. GitHub Secret 更新
# ──────────────────────────────────────────────
def update_github_secret(secret_value: str):
    if not GITHUB_PAT or not GITHUB_REPO:
        print("[3/3] GITHUB_PAT / GITHUB_REPO が未設定のためスキップ")
        print(f"      手動で NOTE_SESSION_B64 を更新してください:")
        print(f"      値: {secret_value[:40]}...")
        return

    print(f"[3/3] GitHub Secret 更新中: {GITHUB_REPO} / NOTE_SESSION_B64 ...")

    import urllib.request
    import urllib.error

    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # (a) リポジトリの公開鍵を取得
    url_pubkey = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key"
    req = urllib.request.Request(url_pubkey, headers=headers)
    with urllib.request.urlopen(req) as resp:
        pk_data = json.loads(resp.read())

    key_id  = pk_data["key_id"]
    pub_key = pk_data["key"]

    # (b) PyNaCl で暗号化
    from nacl import encoding, public as nacl_public
    pk_bytes = base64.b64decode(pub_key)
    box = nacl_public.SealedBox(nacl_public.PublicKey(pk_bytes))
    encrypted = base64.b64encode(
        box.encrypt(secret_value.encode())
    ).decode()

    # (c) Secret を PUT
    url_secret = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/NOTE_SESSION_B64"
    body = json.dumps({"encrypted_value": encrypted, "key_id": key_id}).encode()
    req = urllib.request.Request(url_secret, data=body, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        raise RuntimeError(f"GitHub API エラー: {status} {e.read().decode()}")

    if status in (201, 204):
        print("    NOTE_SESSION_B64 更新成功 ✅")
    else:
        raise RuntimeError(f"GitHub API 予期しないステータス: {status}")


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────
def main():
    print("=" * 50)
    print("note.com セッション自動更新")
    print("=" * 50)

    if not NOTE_EMAIL or not NOTE_PASSWORD:
        print("ERROR: NOTE_EMAIL / NOTE_PASSWORD が設定されていません")
        sys.exit(1)

    login_and_save_session()
    b64 = encode_session_to_b64()
    update_github_secret(b64)

    print()
    print("✅ セッション更新完了！次の有効期限まで自動投稿が継続されます。")


if __name__ == "__main__":
    main()
