"""
下書き状態になっている日次記事を公開する（1回実行用スクリプト）。
対象: 2026-05-22 の6記事
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.publishers.note_publisher import NotePublisher
from src.publishers.post_logger import PostLogger, infer_published
from src.utils.logger import get_logger

logger = get_logger("publish_pending_drafts")

PRICE = 300
HASHTAGS = ["今日の運勢", "占い", "星座占い", "スピリチュアル", "開運"]

# 2026-05-22 の下書き記事（キー → 星座EN名）
PENDING_DRAFTS = {
    "nb5d1814830b7": None,  # 星座不明 → post_log に記録しない
    "n2f1b20a50900": None,
    "naa761396405a": None,
    "nf0f26b62979e": None,
    "nf6fe8de6b393": None,
    "nc81e309a4d22": None,
}

EDITOR_BASE = "https://editor.note.com/notes/{key}/edit/"


def main():
    note = NotePublisher()
    success = 0
    fail = 0

    for key in PENDING_DRAFTS:
        draft_url = EDITOR_BASE.format(key=key)
        logger.info(f"公開中: {key}  URL={draft_url}")
        try:
            url = note.publish_existing_draft(draft_url, price=PRICE, hashtags=HASHTAGS)
            if infer_published(url):
                logger.info(f"  ✓ 公開成功: {url}")
                success += 1
            else:
                logger.warning(f"  △ 公開未確認: {url}")
                fail += 1
        except Exception as e:
            logger.error(f"  ✗ 失敗: {e}")
            fail += 1

        if key != list(PENDING_DRAFTS.keys())[-1]:
            logger.info("  45秒待機...")
            time.sleep(45)

    logger.info(f"=== 完了: 成功{success}件 / 失敗{fail}件 ===")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
