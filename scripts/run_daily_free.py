"""
毎朝 6:30 JST に実行: noteに無料の「今日の12星座ランキング」を投稿する（集客用）。
GitHub Actions の daily_free.yml から呼び出される。
有料記事への導線となり、フォロワーを増やす入口。
重複投稿防止: output/post_log.json で当日の投稿状態を管理。
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator
from src.publishers.note_publisher import NotePublisher
from src.publishers.post_logger import PostLogger, infer_published, period_for
from src.utils.date_utils import get_date_str
from src.utils.logger import get_logger

logger = get_logger("run_daily_free")

POST_TYPE = "free_ranking"
KEY = "all"
HASHTAGS = ["占い", "星座占い", "今日の運勢", "12星座", "ランキング"]
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def main():
    today = datetime.now(JST).date()
    period = period_for(POST_TYPE, today)
    plog = PostLogger()

    logger.info(f"=== 無料ランキング投稿開始: {today.isoformat()} ===")

    if plog.is_published(POST_TYPE, period, KEY):
        logger.info("本日分は既に投稿済みのためスキップ")
        return

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()

    try:
        content = generator.generate_daily_free_ranking(today)
        title = f"【無料】{get_date_str(today)}（{WEEKDAY_JP[today.weekday()]}）今日の12星座ランキング🔮"
        logger.info(f"note投稿中: {title}")

        url = note.publish_free_article(
            title=title,
            content=content,
            cover_image_path=None,
            hashtags=HASHTAGS,
        )

        if infer_published(url):
            plog.record_published(POST_TYPE, period, KEY, url)
            logger.info(f"無料ランキング公開完了: {url}")
        else:
            logger.warning(f"公開未確認: {url}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"無料ランキング投稿失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
