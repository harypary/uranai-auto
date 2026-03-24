"""
数秘術ドラフト記事を新プロンプトで再生成し、既存ドラフトへ上書き保存するスクリプト。

使い方:
    python scripts/reupload_numerology.py

    # 特定のLP番号のみ処理:
    python scripts/reupload_numerology.py --lp 1 3 5

変更点（旧→新）:
    - 無料部分: 220〜260文字 → 600〜800文字（4段構成で集客力UP）
    - セパレーター: テキスト区切り → 正式な「有料エリア指定」ウィジェット
"""

import argparse
import sys
import time
from pathlib import Path

# プロジェクトルートをパスへ追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.gemini_client import GeminiClient
from src.content.numerology_generator import NumerologyGenerator
from src.publishers.note_publisher import NotePublisher
from src.utils.numerology_calc import LIFE_PATH_MEANINGS
from src.utils.logger import get_logger

logger = get_logger("reupload_numerology")

# 既存ドラフトの編集URL（run_numerology.py 実行時に生成されたもの）
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

# 投稿間隔（Bot検出対策）
INTERVAL_SEC = 35


def make_title(lp_num: int) -> str:
    info = LIFE_PATH_MEANINGS[lp_num]
    return f"【ライフパスナンバー{lp_num}】完全鑑定書｜{info['title']}の魂・恋愛・仕事・開運法"


def main():
    parser = argparse.ArgumentParser(description="数秘術ドラフト記事を再生成・再アップロード")
    parser.add_argument(
        "--lp",
        nargs="+",
        type=int,
        choices=list(DRAFT_EDIT_URLS.keys()),
        help="処理するライフパスナンバー（省略時は全12本）",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="生成のみ（アップロードしない）",
    )
    args = parser.parse_args()

    target_lps = args.lp if args.lp else list(DRAFT_EDIT_URLS.keys())

    logger.info(f"処理対象: LP{target_lps}")
    logger.info(f"総記事数: {len(target_lps)}")

    client = GeminiClient()
    generator = NumerologyGenerator(client)
    publisher = NotePublisher() if not args.generate_only else None

    # 生成・アップロード結果を記録
    results = []

    for i, lp_num in enumerate(target_lps):
        if lp_num not in DRAFT_EDIT_URLS:
            logger.warning(f"LP{lp_num} のドラフトURLが未定義のためスキップ")
            continue

        draft_url = DRAFT_EDIT_URLS[lp_num]
        title = make_title(lp_num)

        logger.info(f"[{i+1}/{len(target_lps)}] LP{lp_num} 処理開始...")

        # ─── コンテンツ生成 ───
        try:
            teaser, paid = generator.generate_life_path_article(lp_num)
            logger.info(
                f"LP{lp_num} 生成完了: ティーザー{len(teaser)}文字 / 有料{len(paid)}文字"
            )
        except Exception as e:
            logger.error(f"LP{lp_num} 生成失敗: {e}")
            results.append({"lp": lp_num, "status": "生成失敗", "error": str(e)})
            continue

        if args.generate_only:
            results.append({"lp": lp_num, "status": "生成のみ完了"})
            continue

        # ─── ドラフト上書き保存 ───
        try:
            publisher.update_draft_article(
                draft_url=draft_url,
                title=title,
                teaser_content=teaser,
                paid_content=paid,
            )
            logger.info(f"LP{lp_num} アップロード完了: {draft_url}")
            results.append({"lp": lp_num, "status": "完了", "url": draft_url})
        except Exception as e:
            logger.error(f"LP{lp_num} アップロード失敗: {e}")
            results.append({"lp": lp_num, "status": "アップロード失敗", "error": str(e)})

        # 次の記事まで待機（最後の記事は不要）
        if i < len(target_lps) - 1:
            logger.info(f"{INTERVAL_SEC}秒待機中...")
            time.sleep(INTERVAL_SEC)

    # ─── 結果サマリー ───
    logger.info("=" * 50)
    logger.info("処理結果サマリー")
    logger.info("=" * 50)
    for r in results:
        status = r["status"]
        lp = r["lp"]
        if "error" in r:
            logger.error(f"LP{lp}: {status} - {r['error']}")
        else:
            url = r.get("url", "")
            logger.info(f"LP{lp}: {status} {url}")

    succeeded = sum(1 for r in results if "失敗" not in r["status"])
    logger.info(f"完了: {succeeded}/{len(target_lps)} 件")


if __name__ == "__main__":
    main()
