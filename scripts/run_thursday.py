"""
毎週木曜 20:00 JST に実行: X に今週の注目星座・深掘り投稿を行う。
「木曜夜 × 感情に刺さるコンテンツ」は最もエンゲージメントが高い時間帯。
週次note記事への誘導を強化する。
"""

import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.content.gemini_client import GeminiClient
from src.publishers.twitter_publisher import TwitterPublisher
from src.utils.astrology_data import ZODIAC_SIGNS
from src.utils.date_utils import get_week_range, get_week_label
from src.utils.logger import get_logger

logger = get_logger("run_thursday")

# 木曜用の深掘りプロンプト（感情に刺さる「今週の見どころ」）
THURSDAY_PROMPT = """
あなたはプロの占い師です。今週の星座全体の傾向と、特に注目すべき3つのメッセージを
日本語でX（Twitter）に投稿する文章を書いてください。

【条件】
- 対象: 今週（{week_label}）
- 感情に刺さる深いメッセージ（「わかってもらえた感」を大切に）
- 木曜夜に読む人が感じる「週末に向けての期待・不安・希望」を反映させる
- 3つのメッセージをナンバリングして簡潔に
- 全体で250文字以内（ハッシュタグ含まない）
- 絵文字を効果的に使用（3〜5個）
- 最後に「詳細はnoteの週間運勢で▶」という自然な誘導を含める

【出力形式】
投稿文のみ出力。前置き不要。
"""


def main():
    today = date.today()
    week_start, _ = get_week_range(today)
    week_label = get_week_label(week_start)

    logger.info(f"=== 木曜深掘り投稿開始: {week_label} ===")

    note_weekly_url = os.environ.get(
        "WEEKLY_NOTE_URL",
        os.environ.get("NOTE_ACCOUNT_URL", "https://note.com"),
    )

    gemini = GeminiClient()
    publisher = TwitterPublisher()

    try:
        prompt = THURSDAY_PROMPT.format(week_label=week_label)
        content = gemini.generate(prompt, max_tokens=512, temperature=0.90)

        # note URLを末尾に追加
        tweet = f"{content}\n\n🔮 今週の詳細運勢 → {note_weekly_url}\n#占い #今週の運勢 #スピリチュアル #木曜日"

        if len(tweet) > 280:
            tweet = tweet[:275] + "…"

        tweet_id = publisher.post_text(tweet)
        logger.info(f"木曜深掘り投稿完了: tweet_id={tweet_id}")

    except Exception as e:
        logger.error(f"木曜深掘り投稿失敗: {e}")
        sys.exit(1)

    logger.info("=== 木曜深掘り投稿完了 ===")


if __name__ == "__main__":
    main()
