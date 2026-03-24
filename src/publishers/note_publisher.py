"""note.com 自動投稿モジュール（Playwright ブラウザ自動化）"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from src.utils.logger import get_logger

logger = get_logger("note_publisher")

NOTE_BASE_URL = "https://note.com"
NOTE_LOGIN_URL = f"{NOTE_BASE_URL}/login"
NOTE_NEW_ARTICLE_URL = f"{NOTE_BASE_URL}/notes/new"

# セッションファイルパス
SESSION_FILE = Path(__file__).parent.parent.parent / "output" / "note_session.json"

# 投稿間隔（秒）- Bot検出対策
POST_INTERVAL = 35


class NotePublisher:
    """note.com への有料記事自動投稿（セッション方式）"""

    def update_draft_article(
        self,
        draft_url: str,
        title: str,
        teaser_content: str,
        paid_content: str,
    ) -> None:
        """
        既存ドラフト記事のコンテンツを新しい内容で上書き保存（セパレーター付き）。

        Parameters
        ----------
        draft_url: 既存ドラフトの編集URL（editor.note.com/notes/...）
        title: 記事タイトル（既存タイトルを維持する場合はそのまま渡す）
        teaser_content: 無料公開部分（ティーザー）
        paid_content: 有料部分
        """
        storage_state = self._load_session()

        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context: BrowserContext = browser.new_context(
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
            try:
                logger.info(f"既存ドラフト更新: {draft_url}")
                page.goto(draft_url, wait_until="networkidle", timeout=30000)
                _wait(3)

                # 本文をクリアして再入力
                self._clear_body(page)
                self._fill_body(page, teaser_content, paid_content)

                # 下書き保存
                try:
                    page.click('button:has-text("下書き保存")', timeout=5000)
                    _wait(2)
                    logger.info(f"下書き保存完了: {draft_url}")
                except Exception:
                    logger.warning("下書き保存ボタンが見つかりません（自動保存に任せる）")
            finally:
                browser.close()

    def _clear_body(self, page: Page):
        """本文エリアの内容をすべて削除"""
        try:
            body_el = page.query_selector(".ProseMirror") or page.query_selector('[contenteditable="true"]')
            if body_el:
                body_el.click()
                _wait(0.5)
                page.keyboard.press("Control+a")
                _wait(0.3)
                page.keyboard.press("Delete")
                _wait(0.5)
                logger.debug("本文クリア完了")
        except Exception as e:
            logger.warning(f"本文クリア失敗: {e}")

    def publish_article(
        self,
        title: str,
        teaser_content: str,
        paid_content: str,
        price: int,
        cover_image_path: Optional[str] = None,
        hashtags: Optional[list] = None,
    ) -> str:
        """
        note.com に有料記事を投稿してURLを返す。

        事前に scripts/setup_note_session.py を実行してセッションを保存してください。

        Parameters
        ----------
        title: 記事タイトル
        teaser_content: 無料公開部分（ティーザー）
        paid_content: 有料部分（Markdown）
        price: 価格（円）- 100円以上
        cover_image_path: カバー画像のパス（省略可）
        hashtags: ハッシュタグリスト（最大5個）
        """
        storage_state = self._load_session()

        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context: BrowserContext = browser.new_context(
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
                # セッション確認
                self._verify_session(page)
                url = self._create_paid_article(
                    page=page,
                    title=title,
                    teaser=teaser_content,
                    paid=paid_content,
                    price=price,
                    cover_image_path=cover_image_path,
                    hashtags=hashtags or [],
                )
                return url
            finally:
                browser.close()

    # ──────────────────────────────────────────────────────────
    # 内部メソッド
    # ──────────────────────────────────────────────────────────

    def _load_session(self) -> dict:
        """セッションファイルを読み込む"""
        # GitHub Actions用: 環境変数からセッション取得
        session_b64 = os.environ.get("NOTE_SESSION_B64")
        if session_b64:
            import base64
            session_json = base64.b64decode(session_b64).decode("utf-8")
            logger.info("環境変数からセッションを読み込みました")
            return json.loads(session_json)

        if not SESSION_FILE.exists():
            raise FileNotFoundError(
                f"セッションファイルが見つかりません: {SESSION_FILE}\n"
                "先に以下を実行してください:\n"
                "  python scripts/setup_note_session.py"
            )

        with open(SESSION_FILE, encoding="utf-8") as f:
            state = json.load(f)
        logger.info(f"セッション読み込み完了: {SESSION_FILE}")
        return state

    def _verify_session(self, page: Page):
        """セッションが有効かどうかを確認する"""
        logger.info("セッション確認中...")
        page.goto("https://note.com", wait_until="networkidle", timeout=30000)
        _wait(2)

        # ログイン済みならユーザーアイコンやアカウントリンクがある
        is_logged_in = page.query_selector('[data-testid="user-icon"], .o-header__userIcon, a[href*="/settings"]')
        if is_logged_in:
            logger.info("セッション有効 - ログイン済み")
        else:
            logger.warning("セッションが期限切れの可能性があります。scripts/setup_note_session.py を再実行してください。")

    def _create_paid_article(
        self,
        page: Page,
        title: str,
        teaser: str,
        paid: str,
        price: int,
        cover_image_path: Optional[str],
        hashtags: list,
    ) -> str:
        logger.info(f"記事作成開始: {title}")
        page.goto(NOTE_NEW_ARTICLE_URL, wait_until="networkidle")
        _wait(3)

        # ─── タイトル入力 ───
        self._fill_title(page, title)
        _wait(1)

        # ─── カバー画像アップロード ───
        if cover_image_path and Path(cover_image_path).exists():
            self._upload_cover(page, cover_image_path)
            _wait(3)

        # ─── 本文入力（ティーザー + セパレーター + 有料部分）───
        self._fill_body(page, teaser, paid)
        _wait(2)

        # ─── 公開設定ページへ ───
        page.click('button:has-text("公開に進む")', timeout=8000)
        logger.debug("公開設定ページへ遷移")
        _wait(4)

        # ─── ハッシュタグ設定（設定ページ）───
        if hashtags:
            self._set_hashtags(page, hashtags)
            _wait(1)

        # ─── 価格設定（設定ページ、id="price"）───
        self._set_price(page, price)
        _wait(1)

        # ─── 有料エリア設定 → /publish/ プレビューへ ───
        page.click('button:has-text("有料エリア設定")', timeout=8000)
        logger.debug("有料エリア設定クリック → /publish/ へ遷移")
        _wait(4)

        # ─── 「投稿する」クリック（window.confirm は dialog handler で自動承認）───
        page.click('button:has-text("投稿する")', timeout=8000)
        logger.debug("投稿するクリック")
        _wait(8)

        url = page.url
        logger.info(f"投稿完了: {url}")
        return url

    def _fill_title(self, page: Page, title: str):
        selectors = [
            'input[placeholder*="タイトル"]',
            'textarea[placeholder*="タイトル"]',
            '[data-placeholder*="タイトル"]',
            '.title-input',
        ]
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.fill(sel, title)
                logger.debug(f"タイトル入力完了: セレクター={sel}")
                return
            except Exception:
                continue
        logger.warning("タイトル入力フィールドが見つかりません。キーボード入力を試みます。")
        page.keyboard.press("Tab")
        page.keyboard.type(title)

    def _upload_cover(self, page: Page, image_path: str):
        try:
            file_inputs = page.query_selector_all('input[type="file"]')
            if file_inputs:
                file_inputs[0].set_input_files(image_path)
                logger.debug(f"カバー画像アップロード: {image_path}")
            else:
                logger.warning("ファイル入力フィールドが見つかりません")
        except Exception as e:
            logger.warning(f"カバー画像アップロード失敗（スキップ）: {e}")

    def _fill_body(self, page: Page, teaser: str, paid: str):
        """本文エリアにティーザーと有料コンテンツを入力"""
        body_selectors = [
            ".ProseMirror",
            '[role="textbox"]',
            ".note-editor-content",
            '[contenteditable="true"]',
        ]
        body_el = None
        for sel in body_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                body_el = page.query_selector(sel)
                if body_el:
                    logger.debug(f"本文エリア検出: {sel}")
                    break
            except Exception:
                continue

        if body_el:
            body_el.click()
        else:
            logger.warning("本文エリアが見つかりません。フォールバック入力を実行します。")

        _wait(0.5)

        # ティーザー本文を入力（クリップボード経由）
        page.evaluate(f"navigator.clipboard.writeText({json.dumps(teaser)})")
        _wait(0.3)
        page.keyboard.press("Control+v")
        _wait(0.5)

        # 有料エリア区切りを挿入（スラッシュコマンド）
        self._insert_paid_boundary(page)
        _wait(1)

        # 有料コンテンツを入力（クリップボード経由で高速・大容量対応）
        page.evaluate(f"navigator.clipboard.writeText({json.dumps(paid)})")
        _wait(0.5)
        page.keyboard.press("Control+v")
        _wait(2)

    def _insert_paid_boundary(self, page: Page):
        """noteの有料エリア区切り線を挿入（+メニューから）

        note.com エディタの「メニューを開く」(+) ボタン → 「有料エリア指定」を使用。
        separator フィールドが正しく設定される唯一の方法。
        """
        try:
            # カーソルを本文末尾へ移動
            page.keyboard.press("Control+End")
            _wait(0.5)

            # 最後の要素にホバーして + ボタンを表示させる
            page.hover(".ProseMirror > *:last-child", timeout=5000)
            _wait(0.4)

            # 「メニューを開く」(+) ボタンをクリック
            page.click('[aria-label="メニューを開く"]', timeout=5000)
            _wait(0.5)

            # 「有料エリア指定」をクリック
            page.click('text=有料エリア指定', timeout=5000)
            _wait(1.0)
            logger.debug("有料エリア区切り挿入成功（メニュー経由）")

        except Exception as e:
            logger.warning(f"有料エリア挿入失敗（{e}）、テキストフォールバック使用")
            page.keyboard.press("Enter")
            page.keyboard.type("【ここから有料コンテンツ】")
            page.keyboard.press("Enter")

    def _set_price(self, page: Page, price: int):
        """価格を設定（設定ページの id="price" inputを使用）"""
        try:
            loc = page.locator('#price').first
            loc.wait_for(state='visible', timeout=5000)
            loc.click(click_count=3)
            _wait(0.3)
            loc.fill(str(price))
            _wait(0.5)
            loc.press('Tab')
            logger.debug(f"価格設定: {price}円")
        except Exception as e:
            logger.warning(f"価格設定失敗: {e}")

    def _set_hashtags(self, page: Page, hashtags: list):
        """ハッシュタグを設定（設定ページの「ハッシュタグを追加する」入力欄）"""
        try:
            loc = page.locator('input[placeholder*="ハッシュタグ"]').first
            loc.wait_for(state='visible', timeout=5000)
            for tag in hashtags[:5]:
                loc.fill(tag)
                loc.press('Enter')
                _wait(0.3)
            logger.debug(f"ハッシュタグ設定: {hashtags[:5]}")
        except Exception as e:
            logger.warning(f"ハッシュタグ設定失敗: {e}")

    def _publish(self, page: Page) -> str:
        """記事を公開してURLを返す"""
        publish_selectors = [
            'button:has-text("公開設定へ")',
            'button:has-text("公開する")',
            '[data-cy="publish-button"]',
        ]
        for sel in publish_selectors:
            try:
                page.click(sel, timeout=5000)
                _wait(2)
                logger.debug(f"公開ボタンクリック: {sel}")
                break
            except Exception:
                continue

        # 確認ダイアログがある場合
        try:
            confirm_btn = page.query_selector('button:has-text("公開する")')
            if confirm_btn:
                confirm_btn.click()
                _wait(3)
        except Exception:
            pass

        # URLを取得
        _wait(2)
        current_url = page.url
        return current_url


def _wait(seconds: float):
    """人間らしい待機（わずかなランダムブレ付き）"""
    import random
    time.sleep(seconds + random.uniform(0, 0.5))
