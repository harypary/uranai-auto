"""
毎週月曜 7:30 JST に実行: noteに12星座の週間運勢を投稿する（各980円）。
GitHub Actions の weekly_note.yml から呼び出される。
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

logger = get_logger("run_weekly")

# note投稿間の待機秒数（Bot検出対策）
POST_INTERVAL = 35

PRICE = 980
HASHTAG_BASE = ["週間運勢", "占い", "星座占い", "スピリチュアル", "運勢"]


def main():
    today = date.today()
    week_start, week_end = get_week_range(today)
    week_str = get_week_range_str(week_start, week_end)
    week_label = get_week_label(week_start)

    logger.info(f"=== 週次note投稿開始: {week_str} ===")

    # 出力ディレクトリ
    Path("output/images").mkdir(parents=True, exist_ok=True)

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()
    img_gen = CoverImageGenerator()

    success_count = 0
    fail_count = 0
    first_url = None

    for i, sign in enumerate(ZODIAC_SIGNS):
        try:
            logger.info(f"[{i+1}/12] {sign['name']} 処理開始...")

            # 1. コンテンツ生成
            logger.info(f"  コンテンツ生成中...")
            teaser, paid = generator.generate_weekly(sign, week_start, week_end)

            # 2. カバー画像生成
            img_path = f"output/images/weekly_{sign['en']}_{today.isoformat()}.png"
            logger.info(f"  カバー画像生成中: {img_path}")
            img_gen.generate_weekly(sign, week_label, img_path)

            # 3. note投稿（引き込むタイトルを自動生成）
            title = generate_weekly_title(sign, week_label)
            hashtags = [sign["name"]] + HASHTAG_BASE

            logger.info(f"  note投稿中: {title}")
            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=PRICE,
                cover_image_path=img_path,
                hashtags=hashtags,
            )

            logger.info(f"[{i+1}/12] {sign['name']} 投稿完了: {url}")
            success_count += 1

            if first_url is None:
                first_url = url

            # GitHub Actions の step 出力に書き込む
            _write_github_output(f"weekly_note_url_{sign['en']}", url)

            # 最後以外は待機
            if i < len(ZODIAC_SIGNS) - 1:
                logger.info(f"  {POST_INTERVAL}秒待機中...")
                time.sleep(POST_INTERVAL)

        except Exception as e:
            logger.error(f"[{i+1}/12] {sign['name']} 失敗: {e}")
            fail_count += 1
            continue

    # 代表URLを出力（日次スクリプトが参照）
    if first_url:
        _write_github_output("weekly_note_url", first_url)

    logger.info(
        f"=== 週次note投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ==="
    )

    if fail_count == len(ZODIAC_SIGNS):
        sys.exit(1)


def _write_github_output(key: str, value: str):
    """GitHub Actions の GITHUB_OUTPUT ファイルに書き込む"""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
