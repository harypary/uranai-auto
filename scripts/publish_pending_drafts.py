"""
下書き状態になっている日次記事を公開する（1回実行用スクリプト）。
公開後に note.com API で実際のステータスを確認する。
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright
from src.publishers.note_publisher import NotePublisher
from src.utils.logger import get_logger

logger = get_logger("publish_pending_drafts")

PRICE = 300
HASHTAGS = ["今日の運勢", "占い", "星座占い", "スピリチュアル", "開運"]
NOTE_USER_ID = os.environ.get("NOTE_USER_ID", "0928shoki")
EDITOR_BASE = "https://editor.note.com/notes/{key}/edit/"


def get_all_draft_keys() -> list[str]:
    """note.com API で現在の下書き一覧を取得"""
    import base64

    session_b64 = os.environ.get("NOTE_SESSION_B64")
    if not session_b64:
        session_path = Path("output/note_session.json")
        session_b64 = base64.b64encode(session_path.read_bytes()).decode()

    state = json.loads(base64.b64decode(session_b64))

    keys = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = br.new_context(storage_state=state)
        pg = ctx.new_page()
        pg.goto("https://note.com/notes", wait_until="networkidle", timeout=30000)
        page_num = 1
        while True:
            resp = pg.request.get(
                f"https://note.com/api/v2/note_list/contents?page={page_num}&per=20",
                headers={"accept": "application/json"},
            )
            data = resp.json()
            inner = data.get("data") or {}
            notes = inner.get("notes") or []
            for n in notes:
                if n.get("status") == "draft":
                    keys.append(n["key"])
            if inner.get("isLastPage", True) or not notes:
                break
            page_num += 1
        br.close()
    return keys


def is_published(key: str) -> bool:
    """HTTP GET でアクセスして 200 なら公開済み"""
    try:
        import requests
        r = requests.get(
            f"https://note.com/{NOTE_USER_ID}/n/{key}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


def main():
    logger.info("=== 下書き公開スクリプト開始 ===")

    draft_keys = get_all_draft_keys()
    logger.info(f"下書き件数: {len(draft_keys)}")
    for k in draft_keys:
        logger.info(f"  {k}")

    if not draft_keys:
        logger.info("下書きなし → 終了")
        return

    note = NotePublisher()
    success, fail = 0, 0

    for i, key in enumerate(draft_keys):
        draft_url = EDITOR_BASE.format(key=key)
        logger.info(f"[{i+1}/{len(draft_keys)}] 公開中: {key}")
        try:
            note.publish_existing_draft(draft_url, price=PRICE, hashtags=HASHTAGS)
        except Exception as e:
            logger.error(f"  publish_existing_draft 例外: {e}")

        # 実際に公開されたか API で確認
        time.sleep(5)
        if is_published(key):
            logger.info(f"  [OK] 公開確認: https://note.com/{NOTE_USER_ID}/n/{key}")
            success += 1
        else:
            logger.warning(f"  [NG] まだ下書き: {key}")
            fail += 1

        if i < len(draft_keys) - 1:
            logger.info("  30秒待機...")
            time.sleep(30)

    logger.info(f"=== 完了: 成功{success}件 / 失敗{fail}件 ===")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
