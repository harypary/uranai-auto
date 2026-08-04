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

from src.content import content_cache
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
# 1回のGemini呼び出しで生成する星座数。12件を1回にまとめると出力トークン
# 上限(65,536)を超えて後半が欠落するため、4件ずつ3回に分ける。
BATCH_SIZE = int(os.environ.get("DAILY_BATCH_SIZE", "4"))
PRICE = 300
POST_TYPE = "daily"
HASHTAG_BASE = ["今日の運勢", "占い", "星座占い", "スピリチュアル", "開運"]
MAX_RETRIES = 2  # 1星座あたりの最大リトライ回数


def _fetch_published_signs_today(date_str: str) -> set:
    """note.comから「今日の日次記事が既にある星座」を取得する。

    post_log は GitHub Actions のキャッシュ管理のため、実行が並走したり
    キャッシュが復元できないと空になり、同じ星座を二重投稿してしまう。
    note.com 本体を正とすることで、キャッシュ状態に関わらず重複を防ぐ。
    タイトルに星座名と当日の日付文字列の両方を含むものだけを日次記事とみなす
    （週次・月次のタイトルは同じ日付文字列を含まないため誤検出しない）。
    """
    import requests
    note_user = os.environ.get("NOTE_USER_ID", "0928shoki")
    found = set()
    try:
        for page in range(1, 5):
            r = requests.get(
                f"https://note.com/api/v2/creators/{note_user}/contents",
                params={"kind": "note", "page": page},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
            )
            if r.status_code != 200:
                break
            data = r.json().get("data", {})
            contents = data.get("contents", [])
            for n in contents:
                title = n.get("name", "")
                if date_str not in title:
                    continue
                for s in ZODIAC_SIGNS:
                    if s["name"] in title:
                        found.add(s["en"])
                        break
            if data.get("isLastPage") or not contents:
                break
    except Exception as e:
        logger.warning(f"note.com の公開済み記事確認に失敗: {e}（post_logのみで判定します）")
    return found


def _generate_missing_in_batches(generator, plog, period, today, date_str, already_on_note) -> None:
    """未生成の星座をまとめて生成し、キャッシュへ保存する。

    星座ごとに個別APIを呼ぶとGemini無料枠（1モデル20リクエスト/日）を
    使い切るため、BATCH_SIZE星座ずつ1回の呼び出しで生成して回数を減らす。
    12星座を1回にまとめると出力トークン上限を超えて後半が欠落するため、
    分割して確実に全星座ぶんを取得する。
    """
    todo = [
        s for s in ZODIAC_SIGNS
        if not plog.is_published(POST_TYPE, period, s["en"])
        and s["en"] not in already_on_note
        and content_cache.load(POST_TYPE, period, s["en"]) is None
    ]
    if not todo:
        logger.info("バッチ生成: 生成が必要な星座はありません")
        return

    logger.info(f"バッチ生成開始: {len(todo)}星座を{BATCH_SIZE}件ずつ生成します")
    for i in range(0, len(todo), BATCH_SIZE):
        chunk = todo[i:i + BATCH_SIZE]
        names = "・".join(s["name"] for s in chunk)
        try:
            results = generator.generate_daily_batch(chunk, today)
        except Exception as e:
            logger.error(f"バッチ生成失敗({names}): {str(e)[:200]}")
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                logger.error("Gemini無料枠切れ。以降のバッチ生成を中止します。")
                return
            continue

        for sign in chunk:
            got = results.get(sign["en"])
            if not got:
                continue
            teaser, paid = got
            content_cache.save(
                POST_TYPE, period, sign["en"],
                teaser=teaser, paid=paid,
                title=generate_daily_title(sign, date_str),
            )
        logger.info(f"バッチ生成完了({names}): {len(results)}/{len(chunk)}件")


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

    # 新規投稿（生成済みキャッシュがあれば再生成せずquotaを節約）
    date_str = get_date_str(today)
    cached = content_cache.load(POST_TYPE, period, sign_en)
    if cached:
        teaser, paid, title = cached["teaser"], cached["paid"], cached["title"]
    else:
        # バッチ生成で用意できなかった星座のみ個別生成にフォールバック
        teaser, paid = generator.generate_daily(sign, today)
        title = generate_daily_title(sign, date_str)
        content_cache.save(POST_TYPE, period, sign_en, teaser=teaser, paid=paid, title=title)
    img_path = f"output/images/daily_{sign_en}_{today.isoformat()}.png"
    img_gen.generate_daily(sign, date_str, img_path)
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

    # note.com を正として今日公開済みの星座を取得（キャッシュ欠落・並走時の二重投稿を防ぐ）
    already_on_note = _fetch_published_signs_today(date_str)
    if already_on_note:
        logger.info(f"note.comで公開済みの星座: {len(already_on_note)}件")

    _generate_missing_in_batches(
        generator, plog, period, today, date_str, already_on_note
    )

    for i, sign in enumerate(ZODIAC_SIGNS):
        sign_en = sign["en"]

        # ── 重複チェック ──
        if plog.is_published(POST_TYPE, period, sign_en) or sign_en in already_on_note:
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
                # Gemini無料枠切れはリトライしても当日中は回復しない。
                # 再試行すると残り星座ぶんの枠まで浪費するため即座に打ち切る。
                if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                    logger.error("Gemini無料枠切れ。リトライせず次の星座へ進みます。")
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
