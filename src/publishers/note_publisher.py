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

    def publish_existing_draft(
        self,
        draft_url: str,
        price: int,
        hashtags: Optional[list] = None,
    ) -> str:
        """
        既存の下書き記事を有料で公開してURLを返す。
        コンテンツは再入力せず、公開フローのみ実行する。

        Parameters
        ----------
        draft_url: 下書きの編集URL（editor.note.com/notes/.../edit/ 形式）
        price: 価格（円）
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
                url = self._publish_draft_flow(
                    page=page,
                    draft_url=draft_url,
                    price=price,
                    hashtags=hashtags or [],
                )
                return url
            finally:
                browser.close()

    def _publish_draft_flow(
        self,
        page: Page,
        draft_url: str,
        price: int,
        hashtags: list,
    ) -> str:
        """既存下書きを開いて公開フローを実行する"""
        import re
        logger.info(f"下書き公開開始: {draft_url}")
        page.goto(draft_url, wait_until="networkidle", timeout=30000)
        _wait(4)

        # 「複数画面で編集」ダイアログを閉じる
        for sel in ['button:has-text("今は保存しない")', 'button:has-text("このまま編集")', 'button:has-text("閉じる")']:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    _wait(2)
                    break
            except Exception:
                pass

        self._dismiss_modals(page)

        # 「公開に進む」クリック
        try:
            page.click('button:has-text("公開に進む")', timeout=8000)
            _wait(6)
        except Exception as e:
            logger.error(f"「公開に進む」失敗: {e}")
            return page.url

        # ハッシュタグ
        if hashtags:
            self._set_hashtags(page, hashtags[:5])
            _wait(1)

        # 有料モード切替
        try:
            page.evaluate("""
                const r = document.getElementById('paid');
                if (r) { r.click(); r.checked = true; r.dispatchEvent(new Event('change', {bubbles: true})); }
            """)
            _wait(1.5)
        except Exception:
            pass

        # 価格設定
        self._set_price(page, price)
        _wait(1)

        # 有料エリア設定 → 確認
        try:
            page.click('button:has-text("有料エリア設定")', timeout=8000, force=True)
            _wait(5)
            confirm_btns = page.locator('button:has-text("このラインより先を有料にする")').all()
            for b in confirm_btns:
                try:
                    if b.is_visible() and b.is_enabled():
                        b.click(timeout=3000, force=True)
                        logger.info("境界確定: このラインより先を有料にする")
                        _wait(3)
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"有料エリア設定失敗: {e}")

        # 投稿（最大3周）
        m = re.search(r"/notes/(n[a-f0-9]+)", page.url)
        note_id = m.group(1) if m else None
        note_user = os.environ.get("NOTE_USER_ID", "0928shoki")

        published = False
        for round_idx in range(3):
            for _ in range(4):
                _wait(2)
                for txt in ["投稿する", "公開する"]:
                    try:
                        btns = page.locator(f'button:has-text("{txt}")').all()
                        for b in btns:
                            try:
                                if not b.is_visible() or not b.is_enabled():
                                    continue
                                if (b.text_content() or "").strip() == txt:
                                    b.scroll_into_view_if_needed(timeout=2000)
                                    _wait(0.3)
                                    b.click(timeout=4000, force=True)
                                    _wait(8)
                                    break
                            except Exception:
                                continue
                    except Exception:
                        continue

            if note_id:
                try:
                    import requests
                    r = requests.get(
                        f"https://note.com/{note_user}/n/{note_id}",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
                    )
                    if r.status_code == 200:
                        published = True
                        logger.info(f"公開確認OK ({note_id}, round {round_idx+1})")
                        break
                    else:
                        logger.warning(f"公開未確認 (status {r.status_code}) → 再試行")
                except Exception:
                    pass
            else:
                break

            try:
                page.click('button:has-text("有料エリア設定")', timeout=4000, force=True)
                _wait(4)
                page.click('button:has-text("このラインより先を有料にする")', timeout=4000, force=True)
                _wait(3)
            except Exception:
                pass

        url = page.url
        if note_id and note_user and published:
            url = f"https://note.com/{note_user}/n/{note_id}"
        logger.info(f"下書き公開完了: {url}")
        return url

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
        self._dismiss_modals(page)

        is_logged_in = page.query_selector('[data-testid="user-icon"], .o-header__userIcon, a[href*="/settings"]')
        if is_logged_in:
            logger.info("セッション有効 - ログイン済み")
        else:
            logger.warning("セッションが期限切れの可能性があります。scripts/setup_note_session.py を再実行してください。")

    def _dismiss_modals(self, page: Page):
        """note.com で出てくるモーダル（年齢認証/同意/通知許可など）を強制的に閉じる"""
        for attempt in range(8):
            modal = page.query_selector(".ReactModal__Overlay--after-open, .IdentificationModal__overlay")
            if not modal:
                try:
                    page.evaluate("""
                        document.querySelectorAll('.ReactModalPortal, .ReactModal__Overlay, [class*="Modal__overlay"]').forEach(el => el.remove());
                    """)
                except Exception:
                    pass
                return
            logger.debug(f"モーダル検出 (attempt {attempt+1}) → 閉じる")
            for sel in [
                'button:has-text("確認")', 'button:has-text("OK")',
                'button:has-text("はい")', 'button:has-text("同意")',
                'button:has-text("閉じる")', 'button:has-text("Skip")',
                'button[aria-label="閉じる"]', 'button[aria-label="Close"]',
                '.ReactModal__Content button',
            ]:
                try:
                    btns = page.locator(sel).all()
                    if btns:
                        btns[-1].click(timeout=1500, force=True)
                        _wait(1)
                        break
                except Exception:
                    continue
            try:
                page.evaluate("""
                    document.querySelectorAll('.ReactModalPortal, .ReactModal__Overlay, [class*="Modal__overlay"]').forEach(el => el.remove());
                    document.body.style.overflow = 'auto';
                """)
            except Exception:
                pass
            _wait(0.5)

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

        # トップページ経由でエディタを起動（モーダル対策）
        page.goto("https://note.com", wait_until="networkidle", timeout=30000)
        _wait(2)
        self._dismiss_modals(page)

        opened = False
        for sel in ['a[href*="/notes/new"]', 'a[href="/notes/new"]', 'a:has-text("投稿")']:
            try:
                els = page.locator(sel).all()
                if els:
                    els[0].click(timeout=5000, force=True)
                    opened = True
                    break
            except Exception:
                continue
        if not opened:
            page.goto(NOTE_NEW_ARTICLE_URL, wait_until="networkidle", timeout=30000)
        _wait(5)

        try:
            page.wait_for_selector(".ProseMirror, [contenteditable='true']", timeout=30000)
        except Exception as ex:
            logger.error(f"エディタ起動タイムアウト: {ex}")
            return ""
        _wait(2)
        self._dismiss_modals(page)

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

        # ★ note.com の自動保存が完了するまで十分待つ（公開フロー成功率向上）
        logger.info("自動保存待機 30秒...")
        _wait(30)

        # ─── 公開設定ページへ ───
        try:
            page.click('button:has-text("公開に進む")', timeout=8000)
            logger.debug("公開設定ページへ遷移")
            _wait(6)
        except Exception as e:
            logger.error(f"「公開に進む」失敗: {e}")
            return ""

        # ─── ハッシュタグ設定 ───
        if hashtags:
            self._set_hashtags(page, hashtags)
            _wait(1)

        # ─── 有料モード切替（JS で確実に）───
        try:
            page.evaluate("""
                const r = document.getElementById('paid');
                if (r) { r.click(); r.checked = true; r.dispatchEvent(new Event('change', {bubbles: true})); }
            """)
            _wait(1.5)
            logger.debug("有料モード切替 OK")
        except Exception as e:
            logger.warning(f"有料モード切替失敗: {e}")

        # ─── 価格設定 ───
        self._set_price(page, price)
        _wait(1)

        # ─── 有料エリア設定 → 「このラインより先を有料にする」確認 ───
        try:
            page.click('button:has-text("有料エリア設定")', timeout=8000, force=True)
            logger.debug("有料エリア設定クリック")
            _wait(5)
            confirm_btns = page.locator('button:has-text("このラインより先を有料にする")').all()
            for b in confirm_btns:
                try:
                    if b.is_visible() and b.is_enabled():
                        b.click(timeout=3000, force=True)
                        logger.info("境界確定: このラインより先を有料にする")
                        _wait(3)
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"有料エリア設定失敗: {e}")

        # ─── 「投稿する」を最大3周リトライ ───
        import re
        try:
            import requests as _requests
            has_requests = True
        except ImportError:
            has_requests = False

        m = re.search(r"/notes/(n[a-f0-9]+)", page.url)
        note_id = m.group(1) if m else None
        note_user = os.environ.get("NOTE_USER_ID", "0928shoki")

        published = False
        for round_idx in range(3):
            for _ in range(4):
                _wait(2)
                for txt in ["投稿する", "公開する"]:
                    try:
                        btns = page.locator(f'button:has-text("{txt}")').all()
                        for b in btns:
                            try:
                                if not b.is_visible() or not b.is_enabled():
                                    continue
                                if (b.text_content() or "").strip() == txt:
                                    b.scroll_into_view_if_needed(timeout=2000)
                                    _wait(0.3)
                                    b.click(timeout=4000, force=True)
                                    _wait(8)
                                    break
                            except Exception:
                                continue
                    except Exception:
                        continue

            if note_id and note_user and has_requests:
                try:
                    r = _requests.get(
                        f"https://note.com/{note_user}/n/{note_id}",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
                    )
                    if r.status_code == 200:
                        published = True
                        logger.info(f"公開確認OK ({note_id}, round {round_idx+1})")
                        break
                    else:
                        logger.warning(f"公開未確認 (status {r.status_code}) → 再試行")
                except Exception:
                    pass
            else:
                break

            try:
                page.click('button:has-text("有料エリア設定")', timeout=4000, force=True)
                _wait(4)
                page.click('button:has-text("このラインより先を有料にする")', timeout=4000, force=True)
                _wait(3)
            except Exception:
                pass

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
        body_el = None
        for sel in [".ProseMirror", '[role="textbox"]', ".note-editor-content", '[contenteditable="true"]']:
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

        # Step 1: ティーザーを分割貼り付け
        self._paste_chunked(page, teaser)
        _wait(1.5)

        if not paid:
            return

        # Step 2: 末尾にカーソル移動＋改行
        page.keyboard.press("Control+End")
        _wait(0.4)
        page.keyboard.press("Enter")
        _wait(0.6)

        # Step 3: 末尾段落の bbox を JS で取得
        bbox = page.evaluate("""
            () => {
                const pm = document.querySelector('.ProseMirror');
                if (!pm) return null;
                const last = pm.lastElementChild;
                if (!last) return null;
                last.scrollIntoView({block: 'center'});
                const r = last.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height};
            }
        """)

        if bbox:
            cx = bbox["x"] + bbox["w"] / 2
            cy = bbox["y"] + bbox["h"] / 2

            # Step 4: マウスを末尾段落に物理移動して + ボタンを発火
            page.mouse.move(cx, cy, steps=8)
            _wait(0.8)

            try:
                menu_btn = page.locator('[aria-label="メニューを開く"]').first
                menu_btn.wait_for(state="visible", timeout=4000)
                menu_btn.click(timeout=3000, force=True)
                _wait(1)

                # Step 5: 「有料エリア指定」をクリック → 境界挿入
                page.click('text=有料エリア指定', timeout=4000)
                _wait(2.5)

                has_paywall = page.evaluate("""
                    () => /paywall|paid_area|paid-area/i.test(document.querySelector('.ProseMirror').innerHTML)
                """)
                logger.info(f"境界挿入 has_paywall={has_paywall}")

                # Step 6: paywall要素の「下」を物理クリックしてカーソルを設置
                paywall_bbox = page.evaluate("""
                    () => {
                        const pm = document.querySelector('.ProseMirror');
                        if (!pm) return null;
                        const all = pm.querySelectorAll('*');
                        for (const el of all) {
                            const cls = el.className || '';
                            if (/paywall|paid_area|paid-area/i.test(cls)) {
                                el.scrollIntoView({block: 'center'});
                                const r = el.getBoundingClientRect();
                                return {x: r.x, y: r.y, w: r.width, h: r.height, bottom: r.bottom};
                            }
                        }
                        const last = pm.lastElementChild;
                        const r = last.getBoundingClientRect();
                        return {x: r.x, y: r.y, w: r.width, h: r.height, bottom: r.bottom};
                    }
                """)
                if paywall_bbox:
                    click_x = paywall_bbox["x"] + paywall_bbox["w"] / 2
                    click_y = paywall_bbox["bottom"] + 30
                    page.mouse.click(click_x, click_y)
                    _wait(0.4)
                    page.keyboard.press("Control+End")
                    _wait(0.3)
                    page.keyboard.press("Enter")
                    _wait(0.3)
                    logger.debug("カーソルを境界の下に移動")

            except Exception as e:
                logger.warning(f"+メニュー失敗: {e} → フォールバック")
                self._insert_paid_boundary_fallback(page)
        else:
            logger.warning("bbox 取得失敗 → フォールバック")
            self._insert_paid_boundary_fallback(page)

        # Step 7: 有料コンテンツを分割貼り付け
        self._paste_chunked(page, paid)
        _wait(2)

    def _insert_paid_boundary_fallback(self, page: Page):
        """有料エリア境界挿入のフォールバック戦略"""
        # 戦略1: hover + +メニュー（旧方式）
        try:
            page.keyboard.press("Control+End")
            _wait(0.5)
            page.keyboard.press("Enter")
            _wait(0.3)
            page.hover(".ProseMirror > *:last-child", timeout=3000)
            _wait(0.5)
            page.click('[aria-label="メニューを開く"]', timeout=3000)
            _wait(0.7)
            page.click('text=有料エリア指定', timeout=3000)
            _wait(1)
            logger.debug("境界挿入成功（hover方式）")
            return
        except Exception as e:
            logger.warning(f"hover方式失敗: {e}")

        # 戦略2: スラッシュコマンド
        try:
            page.keyboard.press("Control+End")
            _wait(0.3)
            page.keyboard.press("Enter")
            _wait(0.3)
            page.keyboard.type("/")
            _wait(1)
            page.keyboard.type("有料")
            _wait(0.5)
            page.keyboard.press("Enter")
            _wait(1)
            logger.debug("境界挿入成功（/コマンド方式）")
            return
        except Exception as e:
            logger.warning(f"/コマンド方式失敗: {e}")

        # 戦略3: テキストフォールバック
        page.keyboard.press("Enter")
        page.keyboard.type("───────── 有料エリア ─────────")
        page.keyboard.press("Enter")
        logger.warning("境界挿入テキストフォールバック（separator未設定）")

    def _paste_chunked(self, page: Page, text: str, chunk_size: int = 1500):
        """長文を行単位で分割してクリップボード+Ctrl+Vで確実に挿入"""
        if not text:
            return
        chunks = []
        cur = ""
        for line in text.split("\n"):
            if len(cur) + len(line) + 1 > chunk_size and cur:
                chunks.append(cur)
                cur = line
            else:
                cur = (cur + "\n" + line) if cur else line
        if cur:
            chunks.append(cur)

        total = len(chunks)
        logger.debug(f"本文 {len(text)}文字 → {total}分割で貼付")
        for i, ch in enumerate(chunks):
            try:
                page.evaluate(f"navigator.clipboard.writeText({json.dumps(ch if i == 0 else chr(10) + ch)})")
                _wait(0.3)
                page.keyboard.press("Control+v")
                _wait(0.6)
                if i > 0 and i % 5 == 0:
                    logger.debug(f"  ...{i}/{total}件")
            except Exception as e:
                logger.warning(f"paste chunk {i} 失敗: {e}")

    def _set_price(self, page: Page, price: int):
        """価格を設定（設定ページの id="price" inputを使用）"""
        try:
            loc = page.locator('#price').first
            loc.scroll_into_view_if_needed(timeout=3000)
            _wait(0.3)
            loc.wait_for(state='visible', timeout=5000)
            loc.click(click_count=3)
            _wait(0.3)
            loc.fill(str(price))
            _wait(0.5)
            loc.press('Tab')
            logger.debug(f"価格設定: {price}円")
        except Exception as e:
            logger.warning(f"価格設定失敗: {e}")
            try:
                page.evaluate(f"""
                    const p = document.getElementById('price');
                    if (p) {{ p.value = '{price}'; p.dispatchEvent(new Event('input', {{bubbles:true}})); p.dispatchEvent(new Event('change', {{bubbles:true}})); }}
                """)
                logger.debug(f"価格設定 JSフォールバック: {price}円")
            except Exception as ex:
                logger.warning(f"価格JS失敗: {ex}")

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


def _wait(seconds: float):
    """人間らしい待機（わずかなランダムブレ付き）"""
    import random
    time.sleep(seconds + random.uniform(0, 0.5))
