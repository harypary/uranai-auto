"""
note.com の販売実績・PV・スキを取得し、Gemini で「売れた文章の傾向」を分析して
output/strategy/current_strategy.txt を更新する（次回以降の生成プロンプトに注入される）。

投稿ワークフロー（daily/weekly）の完了後に実行される。
- PV・スキ: /api/v1/stats/pv（セッションで取得可）
- 売上: /api/v1/stats/sales は本人確認が必要で取れないため、ダッシュボードを「全期間×売上順」にして表から読む
"""

import base64
import json
import os
import re
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
MAX_PV_PAGES = 100


def _load_storage_state() -> dict | None:
    session_b64 = os.environ.get("NOTE_SESSION_B64", "").strip()
    if session_b64:
        return json.loads(base64.b64decode(session_b64).decode("utf-8"))
    session_file = Path("output/note_session.json")
    if session_file.exists():
        return json.loads(session_file.read_text(encoding="utf-8"))
    return None


def _fetch_json(page, url: str) -> dict | None:
    res = page.evaluate(
        """async (u) => {
            const r = await fetch(u, {credentials: 'include'});
            return {status: r.status, text: await r.text()};
        }""",
        url,
    )
    if res["status"] != 200:
        return None
    try:
        return json.loads(res["text"])
    except Exception:
        return None


def _fetch_pv_stats(page) -> list[dict]:
    articles = {}
    for pg in range(1, MAX_PV_PAGES + 1):
        body = _fetch_json(page, f"/api/v1/stats/pv?filter=all&page={pg}&sort=pv")
        if not body:
            break
        data = body.get("data", {})
        notes = data.get("note_stats", [])
        for n in notes:
            articles[n["key"]] = {
                "key": n["key"],
                "title": n.get("name", ""),
                "url": f"https://note.com/{NOTE_USER_ID}/n/{n['key']}",
                "views": n.get("read_count", 0),
                "likes": n.get("like_count", 0),
                "sales_yen": 0,
            }
        if data.get("last_page") or not notes:
            break
    return list(articles.values())


def _parse_int(s: str) -> int:
    s = s.replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _fetch_sales_from_dashboard(page) -> dict[str, int]:
    """ダッシュボードの記事表を「全期間・売上順」にし、{タイトル: 売上円} を返す。"""
    page.goto("https://note.com/dashboard", wait_until="networkidle", timeout=60000)
    time.sleep(4)
    for value in ("ALL", "SALES_DESC"):
        selected = False
        for sel in page.query_selector_all("select"):
            options = sel.evaluate("e => Array.from(e.options).map(o => o.value)")
            if value in options:
                sel.select_option(value)
                selected = True
                time.sleep(5)
                break
        if not selected:
            logger.warning(f"ダッシュボードの選択肢 {value} が見つかりません（画面変更の可能性）")
            return {}

    lines = page.inner_text("body").split("\n")
    sales = {}
    for i, line in enumerate(lines):
        if line.strip() != "公開中":
            continue
        title = next((lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()), "")
        row = next((lines[j] for j in range(i + 1, min(i + 4, len(lines))) if "\t" in lines[j]), "")
        cells = row.strip().split("\t")
        if not title or len(cells) < 5:
            continue
        yen = _parse_int(cells[-1])
        if yen <= 0:
            break  # 売上順なので以降は売上なし
        sales[title] = yen
    return sales


def scrape_note_stats() -> list[dict]:
    storage_state = _load_storage_state()
    if not storage_state:
        logger.error("セッションが見つかりません")
        return []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(viewport={"width": 1400, "height": 1000}, storage_state=storage_state)
        page = context.new_page()
        try:
            page.goto("https://note.com/dashboard", wait_until="networkidle", timeout=60000)
            if not _fetch_json(page, "/api/v2/current_user/email"):
                logger.error("セッション期限切れ: 統計を取得できません")
                return []

            articles = _fetch_pv_stats(page)
            logger.info(f"PV統計取得: {len(articles)}件")

            try:
                sales = _fetch_sales_from_dashboard(page)
            except Exception as e:
                logger.warning(f"売上取得失敗: {e}")
                sales = {}
            logger.info(f"売上のある記事: {len(sales)}件 / 合計{sum(sales.values())}円")

            by_title = {a["title"]: a for a in articles}
            for title, yen in sales.items():
                if title in by_title:
                    by_title[title]["sales_yen"] = yen
                else:
                    articles.append({"key": "", "title": title, "url": "", "views": 0, "likes": 0, "sales_yen": yen})
            return articles
        except Exception as e:
            logger.error(f"stats取得失敗: {e}")
            return []
        finally:
            browser.close()


def _free_part(key: str, limit: int = 500) -> str:
    """売れた記事の無料部分（購入の決め手になった文章）を取得する"""
    if not key:
        return ""
    import requests
    try:
        r = requests.get(f"https://note.com/api/v3/notes/{key}", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        body = r.json().get("data", {}).get("body") or ""
        text = re.sub(r"\n+", "\n", re.sub(r"<[^>]+>", "\n", body)).strip()
        return text[:limit]
    except Exception:
        return ""


def analyze_and_update_strategy(articles: list[dict]) -> str:
    sold = sorted([a for a in articles if a["sales_yen"] > 0], key=lambda a: -a["sales_yen"])
    unsold = [a for a in articles if a["sales_yen"] == 0]
    top_views = sorted(unsold, key=lambda a: (-a["views"], -a["likes"]))[:8]

    def _line(a: dict) -> str:
        return f"- {a['title']}（PV {a['views']} / スキ {a['likes']} / 売上 {a['sales_yen']}円）\n"

    sold_text = ""
    for a in sold[:6]:
        sold_text += _line(a)
        excerpt = _free_part(a["key"])
        if excerpt:
            sold_text += f"  【無料部分の冒頭】\n  {excerpt.replace(chr(10), chr(10) + '  ')}\n"

    prompt = f"""あなたはnote.comの有料占い記事の販売分析者です。
実データから「どんな文章なら買われるか」を読み取り、次回以降の記事の書き手への指示を作ってください。

【実際に購入された記事（タイトル・数値・購入前に読まれた無料部分）】
{sold_text or "（まだ購入なし）"}

【読まれたが購入されなかった記事（PV上位）】
{"".join(_line(a) for a in top_views)}

分析の観点：
1. 購入された記事の無料部分に共通する書き方（具体性・感情への触れ方・寸止めの位置・スコアや目次の見せ方）
2. 読まれたのに買われなかった記事との違い
3. タイトルで効いている言葉と、避けるべき言葉

出力形式：
- 「次回はこうせよ」という指示だけを箇条書きで6〜8個（合計300〜400文字）
- 実データから言えることだけを書く。サンプルが少ない場合は断定しすぎない
"""
    gemini = GeminiClient()
    strategy = gemini.generate(prompt, max_tokens=4096, temperature=0.5)
    logger.info(f"戦略生成完了: {len(strategy)}文字")
    return strategy


def save_stats(articles: list[dict]):
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    stats_file = STATS_DIR / f"stats_{today}.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump({"date": today, "articles": articles}, f, ensure_ascii=False, indent=2)
    logger.info(f"統計保存: {stats_file}")


def save_strategy(strategy: str):
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    with open(STRATEGY_FILE, "w", encoding="utf-8") as f:
        f.write(strategy)
    logger.info(f"戦略更新: {STRATEGY_FILE}")


def main():
    logger.info("=== パフォーマンス分析開始 ===")

    articles = scrape_note_stats()
    if not articles:
        logger.warning("統計データ取得失敗 → 前回の戦略を維持")
        return

    save_stats(articles)
    strategy = analyze_and_update_strategy(articles)
    if strategy:
        save_strategy(strategy)
        print(f"\n=== 新しい戦略 ===\n{strategy}\n")

    logger.info("=== パフォーマンス分析完了 ===")


if __name__ == "__main__":
    main()
