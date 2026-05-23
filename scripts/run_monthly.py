"""
毎月1日 9:00 JST に実行: noteに12星座のプレミアム月次鑑定を投稿する（各1,500円）。
GitHub Actions の monthly_note.yml から呼び出される。
重複投稿防止: output/post_log.json で当月の投稿状態を管理。
"""

import sys
import time
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator, generate_monthly_title
from src.publishers.note_publisher import NotePublisher
from src.publishers.image_generator import CoverImageGenerator
from src.publishers.post_logger import PostLogger, infer_published, period_for
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_month_str
from src.utils.logger import get_logger

logger = get_logger("run_monthly")

POST_INTERVAL = 40
PRICE = 1500
POST_TYPE = "monthly"
HASHTAG_BASE = ["月次運勢", "占い", "星座占い", "スピリチュアル", "プレミアム占い"]


def main():
    today = datetime.now(JST).date()
    month_str = get_month_str(today)
    period = period_for(POST_TYPE, today)

    logger.info(f"=== 月次note投稿開始: {month_str} ===")

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
                price = plog.get_price(POST_TYPE, period, sign_en) or PRICE
                url = note.publish_existing_draft(draft_url, price=price, hashtags=hashtags)
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
            logger.info(f"[{i+1}/12] {sign['name']} 月次処理開始...")

            teaser, paid = generator.generate_monthly(sign, today)

            img_path = f"output/images/monthly_{sign_en}_{today.year}_{today.month:02d}.png"
            img_gen.generate_monthly(sign, month_str, img_path)

            title = generate_monthly_title(sign, month_str)
            logger.info(f"  note投稿中: {title}")

            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=PRICE,
                cover_image_path=img_path,
                hashtags=hashtags,
            )

            if infer_published(url):
                plog.record_published(POST_TYPE, period, sign_en, url)
                logger.info(f"[{i+1}/12] {sign['name']} 公開完了: {url}")
                success_count += 1
            else:
                plog.record_draft(POST_TYPE, period, sign_en, url, title=title, price=PRICE)
                logger.warning(f"[{i+1}/12] {sign['name']} 下書き状態で保存: {url}")
                fail_count += 1

        except Exception as e:
            logger.error(f"[{i+1}/12] {sign['name']} 月次投稿失敗: {e}")
            fail_count += 1

        if i < len(ZODIAC_SIGNS) - 1:
            logger.info(f"  {POST_INTERVAL}秒待機中...")
            time.sleep(POST_INTERVAL)

    logger.info(f"=== 月次note投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ===")

    if fail_count > 0 and success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
