"""
悩み特化の高単価記事（常設販売）を投稿する。GitHub Actions の concern_note.yml から呼び出される。

1回の実行で1テーマ × 12星座を投稿する（復縁・結婚時期・相性・転職・金運）。
テーマは環境変数 CONCERN_THEME で指定。未指定なら週番号で自動ローテーションし、
毎週1テーマずつ常設カタログを積み上げる。
重複投稿防止: output/post_log.json（常設なので一度公開したら二度と再投稿しない）。
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
from src.content.horoscope_generator import HoroscopeGenerator
from src.content.concern_themes import (
    get_theme,
    load_all_themes,
    save_dynamic_theme,
)
from src.content.concern_theme_generator import generate_new_theme
from src.publishers.note_publisher import NotePublisher
from src.publishers.post_logger import PostLogger, infer_published
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.logger import get_logger

logger = get_logger("run_concern")

POST_INTERVAL = 40
PERIOD = "permanent"  # 常設記事なので固定（再実行時は公開済みをスキップ）


def _has_remaining_signs(plog: PostLogger, theme: dict) -> bool:
    post_type = f"concern_{theme['key']}"
    return any(
        not plog.is_published(post_type, PERIOD, s["en"]) for s in ZODIAC_SIGNS
    )


def _select_theme(plog: PostLogger, gemini: GeminiClient) -> dict:
    """投稿するテーマを決める。

    1. CONCERN_THEME 指定があればそれを優先
    2. 未公開の星座が残る既存テーマを定義順に1つ選ぶ（自然に1テーマずつ消化）
    3. 全テーマ公開済みなら Gemini で新テーマを生成して永続化（永久ループ）
    """
    override = os.environ.get("CONCERN_THEME")
    if override:
        t = get_theme(override)
        if t:
            return t
        logger.warning(f"指定テーマ '{override}' が見つかりません。自動選択にフォールバック")

    all_themes = load_all_themes()
    for t in all_themes:
        if _has_remaining_signs(plog, t):
            return t

    logger.info("全テーマが公開済み。新テーマを自動生成します...")
    new_theme = generate_new_theme(gemini, all_themes)
    save_dynamic_theme(new_theme)
    return new_theme


def main():
    gemini = GeminiClient()
    plog = PostLogger()
    theme = _select_theme(plog, gemini)
    post_type = f"concern_{theme['key']}"
    hashtags_base = theme["hashtags"]
    price = theme["price"]

    logger.info(f"=== 悩み特化投稿開始: {theme['title']} (¥{price}) ===")

    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()

    success_count = 0
    fail_count = 0

    for i, sign in enumerate(ZODIAC_SIGNS):
        sign_en = sign["en"]
        hashtags = [sign["name"]] + hashtags_base

        if plog.is_published(post_type, PERIOD, sign_en):
            logger.info(f"[{i+1}/12] {sign['name']} → 既に公開済みのためスキップ")
            success_count += 1
            continue

        try:
            logger.info(f"[{i+1}/12] {sign['name']} 処理開始...")
            cached = content_cache.load(post_type, PERIOD, sign_en)
            if cached:
                teaser, paid = cached["teaser"], cached["paid"]
            else:
                teaser, paid = generator.generate_concern(sign, theme)
                content_cache.save(post_type, PERIOD, sign_en, teaser=teaser, paid=paid)
            title = f"【{sign['name']}】{theme['title']}"
            logger.info(f"  note投稿中: {title}")

            url = note.publish_article(
                title=title,
                teaser_content=teaser,
                paid_content=paid,
                price=price,
                cover_image_path=None,
                hashtags=hashtags,
            )

            if infer_published(url):
                plog.record_published(post_type, PERIOD, sign_en, url)
                logger.info(f"[{i+1}/12] {sign['name']} 公開完了: {url}")
                success_count += 1
            else:
                logger.warning(f"[{i+1}/12] {sign['name']} 公開未確認: {url}")
                fail_count += 1

        except Exception as e:
            logger.error(f"[{i+1}/12] {sign['name']} 失敗: {e}")
            fail_count += 1

        if i < len(ZODIAC_SIGNS) - 1:
            logger.info(f"  {POST_INTERVAL}秒待機中...")
            time.sleep(POST_INTERVAL)

    logger.info(f"=== 悩み特化投稿完了: 成功{success_count}件 / 失敗{fail_count}件 ===")

    if fail_count > 0 and success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
