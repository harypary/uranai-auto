"""
note.com の下書き記事を削除する。
数秘術（LP1〜33）の12本は残し、それ以外の下書きをすべて削除する。

使い方:
    python scripts/delete_drafts.py           # 実際に削除
    python scripts/delete_drafts.py --dry-run # 削除せず一覧表示のみ
"""

import argparse
import json
import os
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.utils.logger import get_logger

logger = get_logger("delete_drafts")

NOTE_USER_ID = "0928shoki"

# 数秘術ドラフトのnote ID（削除しない）
NUMEROLOGY_NOTE_IDS = {
    "nd5a979be088f", "n59954526328b", "n91310d3c8f59",
    "n598cdbba9c79", "nf01a0522f7d3", "n02941a418015",
    "n2c7416ef6685", "na10db99a3ff1", "ndc3840f439a0",
    "n57f13dc0eb6a", "n48cb689302a4", "nf9289ce3dbe6",
}


def load_session() -> dict:
    import base64
    b64 = os.environ.get("NOTE_SESSION_B64", "").strip()
    if b64:
        return json.loads(base64.b64decode(b64).decode("utf-8"))
    session_file = Path("output/note_session.json")
    if session_file.exists():
        with open(session_file, encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("セッションが見つかりません")


def fetch_all_drafts(page) -> list[dict]:
    """note.com API で全下書きを取得（note_list/contents エンドポイント使用）"""
    all_notes = []
    p = 1
    while True:
        result = page.evaluate(f"""
            async () => {{
                const r = await fetch(
                    'https://note.com/api/v2/note_list/contents?page={p}&per_page=50',
                    {{credentials: 'include'}}
                );
                if (!r.ok) return null;
                return await r.json();
            }}
        """)
        if not result:
            break
        notes = result.get("data", {}).get("notes", [])
        if not notes:
            break
        all_notes.extend(notes)
        is_last = result.get("data", {}).get("isLastPage", True)
        if is_last:
            break
        p += 1
    # status == 'draft' のみ返す
    return [n for n in all_notes if n.get("status") == "draft"]


def delete_note(page, note_id: str) -> bool:
    """note.com API で1件削除（正しいエンドポイント: /api/v1/notes/n/{key}）"""
    result = page.evaluate(f"""
        async () => {{
            const r = await fetch('https://note.com/api/v1/notes/n/{note_id}', {{
                method: 'DELETE',
                credentials: 'include',
                headers: {{
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/plain, */*',
                }}
            }});
            return {{ok: r.ok, status: r.status}};
        }}
    """)
    return bool(result and result.get("ok"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="削除せず一覧表示のみ")
    args = parser.parse_args()

    storage_state = load_session()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright未インストール: pip install playwright && playwright install chromium")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            storage_state=storage_state,
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # note.com 管理ページにアクセスしてセッション確立
        page.goto("https://note.com/notes", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        logger.info("下書き一覧を取得中...")
        drafts = fetch_all_drafts(page)

        # エディタページに移動してアクセストークンを確立（DELETE API が通るようになる）
        if drafts:
            first_id = drafts[0].get("key", "") or str(drafts[0].get("id", ""))
            page.goto(f"https://editor.note.com/notes/{first_id}/edit/", wait_until="networkidle", timeout=30000)
            time.sleep(3)
            logger.info("エディタページでアクセストークン確立完了")
        logger.info(f"下書き総数: {len(drafts)}件")

        # 削除対象と保持対象を分類
        to_delete = []
        to_keep = []
        for d in drafts:
            note_id = d.get("key", "") or str(d.get("id", ""))
            title = d.get("name", "") or d.get("title", "")
            if note_id in NUMEROLOGY_NOTE_IDS:
                to_keep.append((note_id, title))
            else:
                to_delete.append((note_id, title))

        print(f"\n{'='*50}")
        print(f"保持する下書き（数秘術）: {len(to_keep)}件")
        for note_id, title in to_keep:
            print(f"  ✅ {note_id}: {title[:40]}")

        print(f"\n削除する下書き（占い記事）: {len(to_delete)}件")
        for note_id, title in to_delete:
            print(f"  [DEL] {note_id}: {title[:40]}")
        print(f"{'='*50}\n")

        if args.dry_run:
            print("--dry-run モード: 実際には削除しません")
            browser.close()
            return

        if not to_delete:
            print("削除対象の下書きはありません")
            browser.close()
            return

        # 削除実行
        deleted = 0
        failed = 0
        for note_id, title in to_delete:
            try:
                ok = delete_note(page, note_id)
                if ok:
                    logger.info(f"削除完了: {note_id} 「{title[:30]}」")
                    deleted += 1
                else:
                    logger.warning(f"削除失敗（API応答エラー）: {note_id} 「{title[:30]}」")
                    failed += 1
            except Exception as e:
                logger.error(f"削除エラー: {note_id} - {e}")
                failed += 1
            time.sleep(random.uniform(1.0, 2.0))

        browser.close()

    print(f"\n=== 完了: 削除{deleted}件 / 失敗{failed}件 ===")


if __name__ == "__main__":
    main()
