"""
毎日 7:00 JST に実行: noteに12星座の今日の運勢を投稿する（各300円）。
GitHub Actions の daily_note.yml から呼び出される。
重複投稿防止: output/post_log.json で当日の投稿状態を管理。
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
MAX_RETRIES = 2  # 1星座あたりの最大リトライ回数


def _check_already_published(key: str) -> str | None:
    """note.com APIで公開済みか確認。公開済みならURLを返す"""
    import requests
    note_user = os.environ.get("NOTE_USER_ID", "0928shoki")
    try:
        r = requests.get(
            f"https://note.com/{note_user}/n/{key}",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        if r.status_code == 200:
            return f"https://note.com/{note_user}/n/{key}"
    except Exception:
        pass
    return None


def _post_one_sign(sign, today, generator, note, img_gen, plog, period) -> str | None:
    """
    1星座を投稿して公開URLを返す。失敗時は None。
    下書き/公開済みのチェックはここでは行わない（呼び出し元で実施）。
    """
    import re
    sign_en = sign["en"]
    hashtags = [sign["name"]] + HASHTAG_BASE

    # 下書き復旧チェック
    draft_url = plog.get_draft_url(POST_TYPE, period, sign_en)
    if draft_url:
        # post_log に draft と記録されていても実際は公開済みの場合がある
        m = re.search(r'/notes/(n[a-f0-9]+)', draft_url)
        if m:
            pub_url = _check_already_published(m.group(1))
            if pub_url:
                logger.info(f"  下書き → 実は公開済み: {pub_url}")
                plog.record_published(POST_TYPE, period, sign_en, pub_url)
                return pub_url

        logger.info(f"  下書き発見 → 公開フロー: {draft_url}")
        url = note.publish_existing_draft(draft_url, price=PRICE, hashtags=hashtags)
        if infer_published(url):
            plog.record_published(POST_TYPE, period, sign_en, url)
            return url
        return None

    # 新規投稿
    date_str = get_date_str(today)
    teaser, paid = generator.generate_daily(sign, today)
    img_path = f"output/images/daily_{sign_en}_{today.isoformat()}.png"
    img_gen.generate_daily(sign, date_str, img_path)
    title = generate_daily_title(sign, date_str)
    logger.info(f"  投稿中: {title}")

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
        return url
    else:
        plog.record_draft(POST_TYPE, period, sign_en, url, title=title, price=PRICE)
        logger.warning(f"  下書き保存: {url}")
        return None


def main():
    today = datetime.now(JST).date()   # JST基準（UTC+9）
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

        # ── 重複チェック ──
        if plog.is_published(POST_TYPE, period, sign_en):
            logger.info(f"[{i+1}/12] {sign['name']} → 既に公開済みのためスキップ")
            success_count += 1
            continue

        # ── 投稿（最大 MAX_RETRIES 回リトライ）──
        logger.info(f"[{i+1}/12] {sign['name']} 処理開始...")
        posted_url = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                posted_url = _post_one_sign(sign, today, generator, note, img_gen, plog, period)
                if posted_url:
                    logger.info(f"[{i+1}/12] {sign['name']} 公開完了 (attempt {attempt}): {posted_url}")
                    break
                logger.warning(f"[{i+1}/12] {sign['name']} 公開未確認 (attempt {attempt})")
            except Exception as e:
                err_msg = str(e)
                logger.error(f"[{i+1}/12] {sign['name']} 失敗 (attempt {attempt}): {err_msg[:200]}")
                # セッション切れ検出
                if any(kw in err_msg.lower() for kw in ("session", "login", "unauthorized", "401", "403")):
                    logger.error("セッション切れの可能性。次の実行でセッション更新を試みます。")
                    break
            if attempt < MAX_RETRIES:
                logger.info(f"  30秒後にリトライ...")
                time.sleep(30)

        if posted_url:
            success_count += 1
        else:
            fail_count += 1

        if i < len(ZODIAC_SIGNS) - 1:
            logger.info(f"  {POST_INTERVAL}秒待機中...")
            time.sleep(POST_INTERVAL)

    logger.info(f"=== 日次note投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ===")

    # 失敗がある場合は exit 1（ワークフローのリトライに使われる）
    if fail_count > 0:
        logger.error(f"未投稿: {fail_count}件 → ワークフローが再試行します")
        sys.exit(1)


if __name__ == "__main__":
    main()
