"""
残り8星座の週間運勢をnoteに投稿（クォータリセット後の再実行用）。
牡羊座・牡牛座・双子座・蠍座は投稿済みのためスキップ。
"""

import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator, generate_weekly_title
from src.publishers.note_publisher import NotePublisher
from src.publishers.image_generator import CoverImageGenerator
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_week_range, get_week_range_str, get_week_label
from src.utils.logger import get_logger

logger = get_logger("run_weekly_remaining")

POST_INTERVAL = 35
PRICE = 980
HASHTAG_BASE = ["週間運勢", "占い", "星座占い", "スピリチュアル", "運勢"]

# 投稿済み（スキップ）
DONE = {"aries", "taurus", "gemini", "scorpio"}

REMAINING = [s for s in ZODIAC_SIGNS if s["en"] not in DONE]


def main():
    today = date.today()
    week_start, week_end = get_week_range(today)
    week_str = get_week_range_str(week_start, week_end)
    week_label = get_week_label(week_start)

    logger.info(f"=== 残り{len(REMAINING)}星座 週次note投稿開始: {week_str} ===")
    logger.info(f"対象: {[s['name'] for s in REMAINING]}")

    Path("output/images").mkdir(parents=True, exist_ok=True)

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()
    img_gen = CoverImageGenerator()

    success_count = 0
    fail_count = 0

    for i, sign in enumerate(REMAINING):
        try:
            logger.info(f"[{i+1}/{len(REMAINING)}] {sign['name']} 処理中...")

            teaser, paid = generator.generate_weekly(sign, week_start, week_end)

            img_path = f"output/images/weekly_{sign['en']}_{today.isoformat()}.png"
            img_gen.generate_weekly(sign, week_label, img_path)

            title = generate_weekly_title(sign, week_label)
            hashtags = [sign["name"]] + HASHTAG_BASE

            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=PRICE,
                cover_image_path=img_path,
                hashtags=hashtags,
            )

            logger.info(f"[{i+1}/{len(REMAINING)}] {sign['name']} 完了: {url}")
            success_count += 1

            if i < len(REMAINING) - 1:
                logger.info(f"  {POST_INTERVAL}秒待機中...")
                time.sleep(POST_INTERVAL)

        except Exception as e:
            logger.error(f"[{i+1}/{len(REMAINING)}] {sign['name']} 失敗: {e}")
            fail_count += 1
            continue

    logger.info(f"=== 完了: 成功{success_count}件 / 失敗{fail_count}件 ===")


if __name__ == "__main__":
    main()
