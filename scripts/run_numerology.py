"""
数秘術鑑定書を一括生成してnoteに投稿する（各1,500円）。
ライフパスナンバー1〜9, 11, 22, 33 の計13記事を作成する。
初回セットアップ時に1回だけ実行する。
"""

import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.numerology_generator import NumerologyGenerator
from src.publishers.note_publisher import NotePublisher
from src.publishers.image_generator import CoverImageGenerator
from src.utils.numerology_calc import ALL_LIFE_PATH_NUMBERS, LIFE_PATH_MEANINGS
from src.utils.logger import get_logger

logger = get_logger("run_numerology")

POST_INTERVAL = 40
PRICE = 1500
HASHTAG_BASE = ["数秘術", "ライフパスナンバー", "占い", "スピリチュアル", "数秘"]


def main():
    logger.info(f"=== 数秘術記事一括生成開始: {len(ALL_LIFE_PATH_NUMBERS)}記事 ===")

    Path("output/images").mkdir(parents=True, exist_ok=True)

    gemini = GeminiClient()
    generator = NumerologyGenerator(gemini)
    note = NotePublisher()
    img_gen = CoverImageGenerator()

    success_count = 0
    fail_count = 0

    for i, lpn in enumerate(ALL_LIFE_PATH_NUMBERS):
        info = LIFE_PATH_MEANINGS[lpn]
        try:
            logger.info(f"[{i+1}/{len(ALL_LIFE_PATH_NUMBERS)}] LP{lpn}（{info['title']}）処理開始...")

            # 1. コンテンツ生成
            teaser, paid = generator.generate_life_path_article(lpn)

            # 2. カバー画像生成
            img_path = f"output/images/numerology_lp{lpn}.png"
            img_gen.generate_numerology(lpn, info["title"], img_path)

            # 3. note投稿
            title = f"【ライフパスナンバー{lpn}】完全鑑定書｜{info['title']}の使命と才能・恋愛・仕事・開運法"
            hashtags = [f"ライフパスナンバー{lpn}", f"数秘{lpn}"] + HASHTAG_BASE[:3]

            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=PRICE,
                cover_image_path=img_path,
                hashtags=hashtags,
            )

            logger.info(f"[{i+1}/{len(ALL_LIFE_PATH_NUMBERS)}] LP{lpn} 投稿完了: {url}")
            success_count += 1

            if i < len(ALL_LIFE_PATH_NUMBERS) - 1:
                logger.info(f"  {POST_INTERVAL}秒待機中...")
                time.sleep(POST_INTERVAL)

        except Exception as e:
            logger.error(f"[{i+1}/{len(ALL_LIFE_PATH_NUMBERS)}] LP{lpn} 失敗: {e}")
            fail_count += 1
            continue

    logger.info(
        f"=== 数秘術記事生成完了: 成功{success_count}件 / 失敗{fail_count}件 ==="
    )
    logger.info(
        f"見込み収益: {success_count} × ¥{PRICE} × 80%(note手数料後) "
        f"= ¥{int(success_count * PRICE * 0.8):,} / 記事が1本売れるごと"
    )


if __name__ == "__main__":
    main()
