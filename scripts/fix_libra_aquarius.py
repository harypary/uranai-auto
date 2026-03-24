"""
天秤座・水瓶座の有料コンテンツ0文字を修正する。
既存の公開済み記事を編集し、再生成したコンテンツで更新する。
"""

import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright, Page
from src.content.gemini_client import GeminiClient
from src.content.horoscope_generator import HoroscopeGenerator, generate_weekly_title
from src.publishers.note_publisher import NotePublisher
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_week_range, get_week_range_str, get_week_label
from src.utils.logger import get_logger

logger = get_logger("fix_libra_aquarius")

TARGETS = {
    "libra":   "n4239ffd6e054",
    "aquarius": "ne0891ca5eff6",
}

PAID_BOUNDARY = "---PAID_BOUNDARY---"


def generate_with_retry(generator, sign, week_start, week_end, max_tries=5):
    """PAID_BOUNDARYが見つかるまで最大max_tries回リトライ"""
    for attempt in range(1, max_tries + 1):
        teaser, paid = generator.generate_weekly(sign, week_start, week_end)
        if len(paid) > 100:
            logger.info(f"  生成OK (試行{attempt}): ティーザー{len(teaser)}文字 / 有料{len(paid)}文字")
            return teaser, paid
        logger.warning(f"  試行{attempt}: 有料{len(paid)}文字 → リトライ")
        time.sleep(3)
    raise RuntimeError(f"{sign['name']}: {max_tries}回試行しても有料コンテンツが生成できませんでした")


def update_published_article(note: NotePublisher, note_id: str, title: str, teaser: str, paid: str):
    """公開済み記事の本文を更新して再投稿する"""
    edit_url = f"https://editor.note.com/notes/{note_id}/edit/"
    storage_state = note._load_session()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            permissions=["clipboard-read", "clipboard-write"],
            storage_state=storage_state,
        )
        page: Page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.on("dialog", lambda dialog: dialog.accept())

        try:
            logger.info(f"編集ページへ遷移: {edit_url}")
            page.goto(edit_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # 本文クリア
            note._clear_body(page)
            time.sleep(1)

            # 本文再入力（ティーザー + セパレーター + 有料部分）
            note._fill_body(page, teaser, paid)
            time.sleep(2)

            # 「公開に進む」or「更新する」を探す
            try:
                page.click('button:has-text("公開に進む")', timeout=5000)
                logger.info("「公開に進む」クリック")
            except Exception:
                logger.info("「公開に進む」なし → 「更新する」を探します")

            time.sleep(4)

            # 有料エリア設定ボタン（設定ページ）
            try:
                page.click('button:has-text("有料エリア設定")', timeout=6000)
                logger.info("「有料エリア設定」クリック")
                time.sleep(4)
            except Exception:
                logger.warning("「有料エリア設定」ボタンが見つかりません")

            # 「投稿する」or「更新する」
            for btn_text in ["更新する", "投稿する"]:
                try:
                    page.click(f'button:has-text("{btn_text}")', timeout=5000)
                    logger.info(f"「{btn_text}」クリック")
                    time.sleep(8)
                    break
                except Exception:
                    continue

            final_url = page.url
            logger.info(f"更新完了: {final_url}")
            return final_url

        finally:
            browser.close()


def main():
    today = date.today()
    week_start, week_end = get_week_range(today)

    gemini = GeminiClient()
    generator = HoroscopeGenerator(gemini)
    note = NotePublisher()

    sign_map = {s["en"]: s for s in ZODIAC_SIGNS}

    for en_name, note_id in TARGETS.items():
        sign = sign_map[en_name]
        logger.info(f"=== {sign['name']} 修正開始 ===")

        # 有料コンテンツを確実に生成
        teaser, paid = generate_with_retry(generator, sign, week_start, week_end)
        logger.info(f"  最終: ティーザー{len(teaser)}文字 / 有料{len(paid)}文字")

        # 記事タイトル（既存と同じパターンで生成）
        week_label = get_week_label(week_start)
        title = generate_weekly_title(sign, week_label)

        # 公開済み記事を更新
        url = update_published_article(note, note_id, title, teaser, paid)
        logger.info(f"=== {sign['name']} 修正完了: {url} ===")

        time.sleep(10)

    logger.info("全修正完了")


if __name__ == "__main__":
    main()
