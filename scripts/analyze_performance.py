"""
note.com のインプレッション・スキ数・購入数を取得し、
Gemini で分析して output/strategy/current_strategy.txt を更新する。

投稿ワークフロー（daily/weekly/monthly）の完了後に実行される。
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.utils.logger import get_logger

logger = get_logger("analyze_performance")

STATS_DIR = Path("output/stats")
STRATEGY_DIR = Path("output/strategy")
STRATEGY_FILE = STRATEGY_DIR / "current_strategy.txt"
NOTE_USER_ID = os.environ.get("NOTE_USER_ID", "0928shoki")


def scrape_note_stats() -> list[dict]:
    """note.com のクリエイターダッシュボードから記事統計を取得する"""
    import base64

    session_b64 = os.environ.get("NOTE_SESSION_B64", "").strip()
    session_file = Path("output/note_session.json")

    storage_state = None
    if session_b64:
        storage_state = json.loads(base64.b64decode(session_b64).decode("utf-8"))
    elif session_file.exists():
        with open(session_file, encoding="utf-8") as f:
            storage_state = json.load(f)

    if not storage_state:
        logger.error("セッションが見つかりません")
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright未インストール")
        return []

    articles = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            storage_state=storage_state,
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # note.com の stats ページ
            logger.info("note stats ページを取得中...")
            page.goto("https://note.com/stats", wait_until="networkidle", timeout=30000)
            _wait(3)

            # ログイン確認
            if "login" in page.url.lower():
                logger.error("セッション期限切れ: ログインページにリダイレクト")
                return []

            # 記事一覧テーブルを取得（note.comのstatsページ構造に合わせて調整）
            articles = _parse_stats_page(page)
            logger.info(f"記事統計取得: {len(articles)}件")

            # データが少ない場合はAPIエンドポイントを試す
            if len(articles) < 3:
                articles = _try_api_stats(page, articles)

        except Exception as e:
            logger.error(f"stats取得失敗: {e}")
        finally:
            browser.close()

    return articles


def _parse_stats_page(page) -> list[dict]:
    """statsページのHTMLから記事データを抽出"""
    articles = []
    try:
        # note.com stats のテーブル行を取得
        rows = page.evaluate("""
            () => {
                const results = [];

                // statsページのテーブル行
                const rows = document.querySelectorAll('table tr, [class*="stats"] [class*="row"], [class*="Stats"] [class*="Row"]');
                rows.forEach(row => {
                    const titleEl = row.querySelector('a[href*="/n/"]');
                    if (!titleEl) return;

                    const href = titleEl.getAttribute('href') || '';
                    const title = titleEl.textContent?.trim() || '';
                    const cells = row.querySelectorAll('td');

                    // 数値セルから統計を取得
                    const nums = Array.from(cells).map(c => c.textContent?.trim().replace(/,/g, '') || '0');

                    results.push({
                        title: title,
                        url: href,
                        raw_nums: nums,
                    });
                });

                // リスト形式のstats（別レイアウト）
                const items = document.querySelectorAll('[class*="noteItem"], [class*="NoteItem"], [class*="article-row"]');
                items.forEach(item => {
                    const titleEl = item.querySelector('a[href*="/n/"]');
                    if (!titleEl) return;

                    const title = titleEl.textContent?.trim() || '';
                    const href = titleEl.getAttribute('href') || '';

                    // ビュー数・スキ数・コメント数を探す
                    const numEls = item.querySelectorAll('[class*="count"], [class*="Count"], [class*="num"], [class*="Num"]');
                    const nums = Array.from(numEls).map(el => el.textContent?.trim().replace(/,/g, '') || '0');

                    if (title && !results.find(r => r.url === href)) {
                        results.push({ title, url: href, raw_nums: nums });
                    }
                });

                return results;
            }
        """)

        for row in rows:
            nums = [_parse_num(n) for n in row.get("raw_nums", [])]
            articles.append({
                "title": row["title"],
                "url": row["url"],
                "views": nums[0] if len(nums) > 0 else 0,
                "likes": nums[1] if len(nums) > 1 else 0,
                "comments": nums[2] if len(nums) > 2 else 0,
                "purchases": nums[3] if len(nums) > 3 else 0,
            })

    except Exception as e:
        logger.warning(f"statsページパース失敗: {e}")

    return articles


def _try_api_stats(page, existing: list) -> list:
    """note.com の内部APIから統計を補完取得"""
    try:
        response = page.evaluate("""
            async () => {
                try {
                    const r = await fetch('https://note.com/api/v2/stats/note?sort=view&page=1', {credentials: 'include'});
                    return await r.json();
                } catch(e) { return null; }
            }
        """)

        if not response or "data" not in response:
            return existing

        api_articles = []
        for item in response["data"].get("notes", []):
            api_articles.append({
                "title": item.get("name", ""),
                "url": item.get("noteUrl", ""),
                "views": item.get("viewCount", 0),
                "likes": item.get("likeCount", 0),
                "comments": item.get("commentCount", 0),
                "purchases": item.get("purchaseCount", 0),
            })
        logger.info(f"API統計取得: {len(api_articles)}件")
        return api_articles if api_articles else existing

    except Exception as e:
        logger.warning(f"API stats失敗: {e}")
        return existing


def _parse_num(s: str) -> int:
    try:
        return int(str(s).replace(",", "").replace("−", "0") or "0")
    except Exception:
        return 0


def analyze_and_update_strategy(articles: list[dict]) -> str:
    """Geminiで記事パフォーマンスを分析し、戦略テキストを生成"""
    if not articles:
        logger.warning("分析対象データなし")
        return ""

    gemini = GeminiClient()

    # 上位・下位記事を抽出
    sorted_by_views = sorted(articles, key=lambda x: x["views"], reverse=True)
    top5 = sorted_by_views[:5]
    bottom5 = sorted_by_views[-5:] if len(sorted_by_views) > 5 else []

    stats_text = "【高パフォーマンス記事（ビュー数上位）】\n"
    for a in top5:
        stats_text += (
            f"- タイトル: {a['title']}\n"
            f"  ビュー: {a['views']} / スキ: {a['likes']} / 購入: {a['purchases']}\n"
        )

    if bottom5:
        stats_text += "\n【低パフォーマンス記事（ビュー数下位）】\n"
        for a in bottom5:
            stats_text += (
                f"- タイトル: {a['title']}\n"
                f"  ビュー: {a['views']} / スキ: {a['likes']} / 購入: {a['purchases']}\n"
            )

    prompt = f"""あなたはnote.comの占い記事のマーケティング分析者です。
以下の記事パフォーマンスデータを分析し、次回以降の記事で実践すべき改善戦略を日本語で提案してください。

{stats_text}

以下の観点で分析してください：
1. 高パフォーマンス記事のタイトルパターン（どんな言葉・構造が効いているか）
2. 高パフォーマンス記事のコンテンツの共通点（星座・テーマ・時期）
3. 次回記事のタイトルで使うべきキーワード・避けるべきキーワード
4. 無料ティーザー部分で強調すべきポイント
5. 有料部分でより響く内容の方向性

出力形式：
- 箇条書きで簡潔に（合計200〜300文字）
- 即実践できる具体的なアドバイスのみ
- 分析の説明ではなく「次回はこうせよ」という指示形式で書く
"""

    strategy = gemini.generate(prompt, max_tokens=1024, temperature=0.7)
    logger.info(f"戦略生成完了: {len(strategy)}文字")
    return strategy


def save_stats(articles: list[dict]):
    """統計データをJSONファイルに保存"""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    stats_file = STATS_DIR / f"stats_{today}.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump({"date": today, "articles": articles}, f, ensure_ascii=False, indent=2)
    logger.info(f"統計保存: {stats_file}")


def save_strategy(strategy: str):
    """戦略テキストを保存（次回投稿時に読み込まれる）"""
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    with open(STRATEGY_FILE, "w", encoding="utf-8") as f:
        f.write(strategy)
    logger.info(f"戦略更新: {STRATEGY_FILE}")


def _wait(seconds: float):
    import random
    time.sleep(seconds + random.uniform(0, 0.3))


def main():
    logger.info("=== パフォーマンス分析開始 ===")

    # 1. note.com から統計取得
    articles = scrape_note_stats()

    if articles:
        save_stats(articles)

        # 2. Gemini で分析・戦略生成
        strategy = analyze_and_update_strategy(articles)
        if strategy:
            save_strategy(strategy)
            logger.info("戦略更新完了")
            print(f"\n=== 新しい戦略 ===\n{strategy}\n")
    else:
        logger.warning("統計データ取得失敗 → 前回の戦略を維持")

    logger.info("=== パフォーマンス分析完了 ===")


if __name__ == "__main__":
    main()
