"""
毎日 9:00 JST に実行: X（Twitter）に12星座の今日の占いを投稿する。
GitHub Actions の daily_horoscope.yml から呼び出される。
"""

import os
import sys
import time
from datetime import date
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator
from src.publishers.twitter_publisher import TwitterPublisher
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_date_str
from src.utils.logger import get_logger

logger = get_logger("run_daily")

# X投稿間の待機秒数（レート制限対策）
POST_INTERVAL = 5


def main():
    today = date.today()
    logger.info(f"=== 日次X投稿開始: {get_date_str(today)} ===")

    # 今週のnote記事URL（週次Workflowが設定したGitHub Variables から取得）
    note_weekly_url = os.environ.get(
        "WEEKLY_NOTE_URL",
        os.environ.get("NOTE_ACCOUNT_URL", "https://note.com"),
    )

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    publisher = TwitterPublisher()

    success_count = 0
    fail_count = 0

    for i, sign in enumerate(ZODIAC_SIGNS):
        try:
            logger.info(f"[{i+1}/12] {sign['name']} 占い生成中...")
            content = generator.generate_daily(sign, today)

            logger.info(f"[{i+1}/12] {sign['name']} X投稿中...")
            tweet_id = publisher.post_daily_horoscope(sign, content, note_weekly_url)

            logger.info(f"[{i+1}/12] {sign['name']} 投稿完了 (id={tweet_id})")
            success_count += 1

            # 最後の星座以外は待機
            if i < len(ZODIAC_SIGNS) - 1:
                time.sleep(POST_INTERVAL)

        except Exception as e:
            logger.error(f"[{i+1}/12] {sign['name']} 投稿失敗: {e}")
            fail_count += 1
            continue

    logger.info(
        f"=== 日次X投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ==="
    )

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
