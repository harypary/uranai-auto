"""
数秘術ドラフト記事を再生成・更新・公開する統合スクリプト。

処理順序:
  1. Gemini で記事を再生成（新プロンプト + strategy_context 適用）
  2. 既存ドラフトを上書き保存（update_draft_article）
  3. 有料（¥1,500）で公開（publish_existing_draft）

使い方:
    python scripts/repost_numerology.py           # 全12本
    python scripts/repost_numerology.py --lp 1 3  # 指定ナンバーのみ
    python scripts/repost_numerology.py --skip-regen  # 再生成スキップ（公開のみ）
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.numerology_generator import NumerologyGenerator
from src.publishers.note_publisher import NotePublisher
from src.utils.numerology_calc import LIFE_PATH_MEANINGS
from src.utils.logger import get_logger

logger = get_logger("repost_numerology")

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
REGEN_INTERVAL = 35
PUBLISH_INTERVAL = 45
HASHTAG_BASE = ["数秘術", "ライフパスナンバー", "スピリチュアル", "占い", "数秘"]


def make_title(lp_num: int) -> str:
    info = LIFE_PATH_MEANINGS[lp_num]
    return f"【ライフパスナンバー{lp_num}】完全鑑定書｜{info['title']}の魂・恋愛・仕事・開運法"


def main():
    parser = argparse.ArgumentParser(description="数秘術記事を再生成・更新・公開")
    parser.add_argument("--lp", nargs="+", type=int, choices=list(DRAFT_EDIT_URLS.keys()),
                        help="処理するライフパスナンバー（省略時は全12本）")
    parser.add_argument("--skip-regen", action="store_true",
                        help="コンテンツ再生成・下書き更新をスキップして公開のみ実行")
    args = parser.parse_args()

    target_lps = args.lp if args.lp else list(DRAFT_EDIT_URLS.keys())
    logger.info(f"対象: LP{target_lps}  価格: {PRICE}円")

    publisher = NotePublisher()

    results = []

    # ─── Phase 1: 再生成 & ドラフト更新 ───
    if not args.skip_regen:
        logger.info("=== Phase 1: コンテンツ再生成 & ドラフト更新 ===")
        client = GeminiClient()
        generator = NumerologyGenerator(client)

        for i, lp_num in enumerate(target_lps):
            draft_url = DRAFT_EDIT_URLS[lp_num]
            title = make_title(lp_num)
            info = LIFE_PATH_MEANINGS[lp_num]

            logger.info(f"[{i+1}/{len(target_lps)}] LP{lp_num}「{info['title']}」再生成中...")

            try:
                teaser, paid = generator.generate_life_path_article(lp_num)
                logger.info(f"  生成完了: ティーザー{len(teaser)}文字 / 有料{len(paid)}文字")
            except Exception as e:
                logger.error(f"  LP{lp_num} 生成失敗: {e}")
                results.append({"lp": lp_num, "status": "生成失敗", "error": str(e)})
                continue

            try:
                publisher.update_draft_article(
                    draft_url=draft_url,
                    title=title,
                    teaser_content=teaser,
                    paid_content=paid,
                )
                logger.info(f"  LP{lp_num} ドラフト更新完了")
                results.append({"lp": lp_num, "status": "更新完了", "draft_url": draft_url,
                                "teaser_len": len(teaser), "paid_len": len(paid)})
            except Exception as e:
                logger.error(f"  LP{lp_num} ドラフト更新失敗: {e}")
                results.append({"lp": lp_num, "status": "更新失敗", "error": str(e)})

            if i < len(target_lps) - 1:
                logger.info(f"  {REGEN_INTERVAL}秒待機中...")
                time.sleep(REGEN_INTERVAL)

    # ─── Phase 2: 公開 ───
    logger.info("=== Phase 2: ドラフト公開 ===")

    # 更新失敗したLPは公開対象から除外
    failed_lps = {r["lp"] for r in results if "失敗" in r.get("status", "")}
    publish_targets = [lp for lp in target_lps if lp not in failed_lps]

    for i, lp_num in enumerate(publish_targets):
        draft_url = DRAFT_EDIT_URLS[lp_num]
        info = LIFE_PATH_MEANINGS[lp_num]
        hashtags = [f"ライフパス{lp_num}"] + HASHTAG_BASE

        logger.info(f"[{i+1}/{len(publish_targets)}] LP{lp_num}「{info['title']}」公開中...")

        try:
            url = publisher.publish_existing_draft(
                draft_url=draft_url,
                price=PRICE,
                hashtags=hashtags[:5],
            )
            logger.info(f"  LP{lp_num} 公開完了: {url}")
            # resultsを更新
            found = next((r for r in results if r["lp"] == lp_num), None)
            if found:
                found["status"] = "公開完了"
                found["published_url"] = url
            else:
                results.append({"lp": lp_num, "status": "公開完了", "published_url": url})
        except Exception as e:
            logger.error(f"  LP{lp_num} 公開失敗: {e}")
            found = next((r for r in results if r["lp"] == lp_num), None)
            if found:
                found["status"] = "公開失敗"
                found["error"] = str(e)
            else:
                results.append({"lp": lp_num, "status": "公開失敗", "error": str(e)})

        if i < len(publish_targets) - 1:
            logger.info(f"  {PUBLISH_INTERVAL}秒待機中...")
            time.sleep(PUBLISH_INTERVAL)

    # ─── サマリー ───
    logger.info("=" * 60)
    logger.info("最終結果サマリー")
    logger.info("=" * 60)
    for r in sorted(results, key=lambda x: x["lp"]):
        lp = r["lp"]
        status = r["status"]
        if "error" in r:
            logger.error(f"  LP{lp}: {status} - {r['error']}")
        else:
            url = r.get("published_url", r.get("draft_url", ""))
            paid_len = r.get("paid_len", "?")
            logger.info(f"  LP{lp}: {status}  有料{paid_len}文字  {url}")

    succeeded = sum(1 for r in results if r["status"] == "公開完了")
    logger.info(f"公開成功: {succeeded}/{len(target_lps)} 件")

    if succeeded == 0 and target_lps:
        sys.exit(1)


if __name__ == "__main__":
    main()
