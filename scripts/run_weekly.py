"""
毎週月曜 7:30 JST に実行: noteに12星座の週間運勢を投稿する（各980円）。
GitHub Actions の weekly_note.yml から呼び出される。
重複投稿防止: note.com の公開済み記事 + output/post_log.json で当週の投稿状態を管理。
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content import content_cache
from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator, generate_weekly_title
from src.publishers.note_publisher import NotePublisher
from src.publishers.image_generator import CoverImageGenerator
from src.publishers.post_logger import PostLogger, fetch_published_signs, infer_published, period_for
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_week_range, get_week_range_str, get_week_label
from src.utils.logger import get_logger

logger = get_logger("run_weekly")

POST_INTERVAL = 35
PRICE = 980
POST_TYPE = "weekly"
HASHTAG_BASE = ["週間運勢", "占い", "星座占い", "スピリチュアル", "運勢"]


def main():
    today = datetime.now(JST).date()
    week_start, week_end = get_week_range(today)
    week_str = get_week_range_str(week_start, week_end)
    week_label = get_week_label(week_start)
    period = period_for(POST_TYPE, today)

    logger.info(f"=== 週次note投稿開始: {week_str} ===")

    Path("output/images").mkdir(parents=True, exist_ok=True)

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()
    img_gen = CoverImageGenerator()
    plog = PostLogger()

    success_count = 0
    fail_count = 0
    first_url = None

    already_on_note = fetch_published_signs(week_label)
    if already_on_note:
        logger.info(f"note.comで公開済みの星座: {len(already_on_note)}件")

    for i, sign in enumerate(ZODIAC_SIGNS):
        sign_en = sign["en"]
        hashtags = [sign["name"]] + HASHTAG_BASE

        # ── 重複チェック ──
        if plog.is_published(POST_TYPE, period, sign_en) or sign_en in already_on_note:
            logger.info(f"[{i+1}/12] {sign['name']} → 既に公開済みのためスキップ")
            if first_url is None:
                from src.publishers.post_logger import LOG_FILE
                import json
                try:
                    data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                    key = f"{POST_TYPE}_{period}_{sign_en}"
                    first_url = data.get(key, {}).get("published_url")
                except Exception:
                    pass
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
                    if first_url is None:
                        first_url = url
                else:
                    logger.warning(f"[{i+1}/12] {sign['name']} 公開未確認: {url}")
                    fail_count += 1
            except Exception as e:
                logger.error(f"[{i+1}/12] {sign['name']} 下書き公開失敗: {e}")
                fail_count += 1

            if i < len(ZODIAC_SIGNS) - 1:
                time.sleep(POST_INTERVAL)
            continue

        # ── 新規投稿（生成済みキャッシュがあれば再生成せずquotaを節約）──
        try:
            logger.info(f"[{i+1}/12] {sign['name']} 処理開始...")

            cached = content_cache.load(POST_TYPE, period, sign_en)
            if cached:
                teaser, paid, title = cached["teaser"], cached["paid"], cached["title"]
            else:
                teaser, paid = generator.generate_weekly(sign, week_start, week_end)
                title = generate_weekly_title(sign, week_label)
                content_cache.save(POST_TYPE, period, sign_en, teaser=teaser, paid=paid, title=title)

            img_path = f"output/images/weekly_{sign_en}_{today.isoformat()}.png"
            img_gen.generate_weekly(sign, week_label, img_path)
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
                if first_url is None:
                    first_url = url
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

    if first_url:
        _write_github_output("weekly_note_url", first_url)

    logger.info(f"=== 週次note投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ===")

    # 1件でも未投稿があれば失敗扱いにし、ワークフローの再試行・バックアップcronで残りを埋める
    # （公開済みの星座は note.com / post_log で判定してスキップされる）
    if fail_count > 0:
        logger.error(f"未投稿: {fail_count}件 → ワークフローが再試行します")
        sys.exit(1)


def _write_github_output(key: str, value: str):
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
