"""X（Twitter）自動投稿モジュール（tweepy v2）"""

import os

import tweepy

from src.utils.logger import get_logger

logger = get_logger("twitter_publisher")


class TwitterPublisher:
    def __init__(self):
        self._client = tweepy.Client(
            consumer_key=os.environ.get("TWITTER_API_KEY"),
            consumer_secret=os.environ.get("TWITTER_API_SECRET"),
            access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.environ.get("TWITTER_ACCESS_TOKEN_SECRET"),
        )

    def post_daily_horoscope(
        self,
        sign: dict,
        content: str,
        note_weekly_url: str,
    ) -> str:
        """日次占いをXに投稿。末尾にnote週次記事URLを添付する。"""
        hashtags = f"\n#{sign['name']} #占い #今日の運勢 #星座占い #スピリチュアル"
        note_link = f"\n\n✨ 詳細週間運勢▶\n{note_weekly_url}"

        tweet = content + note_link + hashtags

        # X の文字数制限: 280文字（日本語は概ね1文字2カウント相当）
        # ※tweepy は実際の文字数カウントを自動処理するので長めに許容
        if len(tweet) > 280:
            allowance = 280 - len(note_link) - len(hashtags) - 3
            tweet = content[:allowance] + "…" + note_link + hashtags

        response = self._client.create_tweet(text=tweet)
        tweet_id = response.data["id"]
        logger.info(f"[X投稿] {sign['name']}: tweet_id={tweet_id}")
        return tweet_id

    def post_text(self, text: str) -> str:
        """汎用テキスト投稿"""
        response = self._client.create_tweet(text=text)
        tweet_id = response.data["id"]
        logger.info(f"[X投稿] tweet_id={tweet_id}")
        return tweet_id
