"""
毎日 7:00 JST に実行: noteに12星座の今日の運勢を投稿する（各300円）。
GitHub Actions の daily_note.yml から呼び出される。
重複投稿防止: output/post_log.json で当日の投稿状態を管理。
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
from src.content.horoscope_generator import HoroscopeGenerator, generate_daily_title
from src.publishers.note_publisher import NotePublisher
from src.publishers.image_generator import CoverImageGenerator
from src.publishers.post_logger import PostLogger, infer_published, period_for
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_date_str
from src.utils.logger import get_logger

logger = get_logger("run_daily")

POST_INTERVAL = 30
PRICE = 300
POST_TYPE = "daily"
HASHTAG_BASE = ["今日の運勢", "占い", "星座占い", "スピリチュアル", "開運"]


def main():
    today = date.today()
    date_str = get_date_str(today)
    period = period_for(POST_TYPE, today)

    logger.info(f"=== 日次note投稿開始: {date_str} ===")

    Path("output/images").mkdir(parents=True, exist_ok=True)

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()
    img_gen = CoverImageGenerator()
    plog = PostLogger()

    success_count = 0
    fail_count = 0

    for i, sign in enumerate(ZODIAC_SIGNS):
        sign_en = sign["en"]
        hashtags = [sign["name"]] + HASHTAG_BASE

        # ── 重複チェック ──
        if plog.is_published(POST_TYPE, period, sign_en):
            logger.info(f"[{i+1}/12] {sign['name']} → 既に公開済みのためスキップ")
            success_count += 1
            continue

        # ── 下書き復旧チェック ──
        draft_url = plog.get_draft_url(POST_TYPE, period, sign_en)
        if draft_url:
            logger.info(f"[{i+1}/12] {sign['name']} → 下書き発見、公開フローを実行: {draft_url}")
            try:
                url = note.publish_existing_draft(draft_url, price=PRICE, hashtags=hashtags)
                if infer_published(url):
                    plog.record_published(POST_TYPE, period, sign_en, url)
                    logger.info(f"[{i+1}/12] {sign['name']} 下書きから公開完了: {url}")
                    success_count += 1
                else:
                    logger.warning(f"[{i+1}/12] {sign['name']} 公開未確認: {url}")
                    fail_count += 1
            except Exception as e:
                logger.error(f"[{i+1}/12] {sign['name']} 下書き公開失敗: {e}")
                fail_count += 1

            if i < len(ZODIAC_SIGNS) - 1:
                time.sleep(POST_INTERVAL)
            continue

        # ── 新規投稿 ──
        try:
            logger.info(f"[{i+1}/12] {sign['name']} 処理開始...")

            teaser, paid = generator.generate_daily(sign, today)

            img_path = f"output/images/daily_{sign_en}_{today.isoformat()}.png"
            img_gen.generate_daily(sign, date_str, img_path)

            title = generate_daily_title(sign, date_str)
            logger.info(f"  note投稿中: {title}")

            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=PRICE,
                cover_image_path=img_path,
                hashtags=hashtags,
            )

            # 結果を記録（下書きでも公開済みでも保存）
            if infer_published(url):
                plog.record_published(POST_TYPE, period, sign_en, url)
                logger.info(f"[{i+1}/12] {sign['name']} 公開完了: {url}")
                success_count += 1
            else:
                plog.record_draft(POST_TYPE, period, sign_en, url, title=title, price=PRICE)
                logger.warning(f"[{i+1}/12] {sign['name']} 下書き状態で保存: {url}")
                fail_count += 1

        except Exception as e:
            logger.error(f"[{i+1}/12] {sign['name']} 失敗: {e}")
            fail_count += 1

        if i < len(ZODIAC_SIGNS) - 1:
            logger.info(f"  {POST_INTERVAL}秒待機中...")
            time.sleep(POST_INTERVAL)

    logger.info(f"=== 日次note投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ===")

    if fail_count > 0 and success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
