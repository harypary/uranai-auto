"""
毎月1日 7:30 JST に実行: noteに12星座のプレミアム月次鑑定を投稿する（各1,500円）。
GitHub Actions の monthly_note.yml から呼び出される。
"""

import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator
from src.publishers.note_publisher import NotePublisher
from src.publishers.image_generator import CoverImageGenerator
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_month_str
from src.utils.logger import get_logger

logger = get_logger("run_monthly")

POST_INTERVAL = 40
PRICE = 1500
HASHTAG_BASE = ["月次運勢", "占い", "星座占い", "スピリチュアル", "プレミアム占い"]


def main():
    today = date.today()
    month_str = get_month_str(today)

    logger.info(f"=== 月次note投稿開始: {month_str} ===")

    Path("output/images").mkdir(parents=True, exist_ok=True)

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()
    img_gen = CoverImageGenerator()

    success_count = 0
    fail_count = 0

    for i, sign in enumerate(ZODIAC_SIGNS):
        try:
            logger.info(f"[{i+1}/12] {sign['name']} 月次処理開始...")

            teaser, paid = generator.generate_monthly(sign, today)

            img_path = f"output/images/monthly_{sign['en']}_{today.year}_{today.month:02d}.png"
            img_gen.generate_monthly(sign, month_str, img_path)

            title = f"【{sign['name']}】{month_str}の運勢 プレミアム月次鑑定｜天体メッセージ完全版"
            hashtags = [sign["name"]] + HASHTAG_BASE

            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=PRICE,
                cover_image_path=img_path,
                hashtags=hashtags,
            )

            logger.info(f"[{i+1}/12] {sign['name']} 月次投稿完了: {url}")
            success_count += 1

            if i < len(ZODIAC_SIGNS) - 1:
                logger.info(f"  {POST_INTERVAL}秒待機中...")
                time.sleep(POST_INTERVAL)

        except Exception as e:
            logger.error(f"[{i+1}/12] {sign['name']} 月次投稿失敗: {e}")
            fail_count += 1
            continue

    logger.info(
        f"=== 月次note投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ==="
    )

    if fail_count == len(ZODIAC_SIGNS):
        sys.exit(1)


if __name__ == "__main__":
    main()
