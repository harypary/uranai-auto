"""投稿ログ管理 — 重複投稿・未公開下書きの追跡"""

import json
from datetime import date
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent.parent / "output" / "post_log.json"
NOTE_USER_ID = "0928shoki"


class PostLogger:
    """
    投稿状態を output/post_log.json で管理する。

    エントリ構造:
      {
        "{type}_{period}_{sign_en}": {
          "draft_url": "https://editor.note.com/notes/.../edit/",
          "published_url": "https://note.com/0928shoki/n/...",
          "title": "...",
          "price": 980
        }
      }
    type: "daily" | "weekly" | "monthly"
    period: "2026-05-21" (daily) | "2026-05-19" (weekly=月曜日) | "2026-05" (monthly)
    """

    def __init__(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self):
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _key(self, post_type: str, period: str, sign_en: str) -> str:
        return f"{post_type}_{period}_{sign_en}"

    def is_published(self, post_type: str, period: str, sign_en: str) -> bool:
        """公開済みかどうか確認"""
        entry = self._data.get(self._key(post_type, period, sign_en), {})
        url = entry.get("published_url", "")
        return bool(url and f"note.com/{NOTE_USER_ID}/n/" in url)

    def get_draft_url(self, post_type: str, period: str, sign_en: str) -> str | None:
        """下書きURLを返す（なければNone）"""
        entry = self._data.get(self._key(post_type, period, sign_en), {})
        return entry.get("draft_url") or None

    def get_price(self, post_type: str, period: str, sign_en: str) -> int | None:
        entry = self._data.get(self._key(post_type, period, sign_en), {})
        return entry.get("price")

    def record_draft(
        self,
        post_type: str,
        period: str,
        sign_en: str,
        draft_url: str,
        title: str = "",
        price: int = 0,
    ):
        """下書き作成を記録"""
        key = self._key(post_type, period, sign_en)
        entry = self._data.get(key, {})
        entry["draft_url"] = draft_url
        entry["title"] = title
        entry["price"] = price
        self._data[key] = entry
        self._save()

    def record_published(
        self,
        post_type: str,
        period: str,
        sign_en: str,
        published_url: str,
    ):
        """公開完了を記録"""
        key = self._key(post_type, period, sign_en)
        entry = self._data.get(key, {})
        entry["published_url"] = published_url
        self._data[key] = entry
        self._save()


def infer_published(url: str) -> bool:
    """URLが公開済み記事URLかどうか判定"""
    return bool(url and f"note.com/{NOTE_USER_ID}/n/" in url)


def period_for(post_type: str, target_date: date) -> str:
    """投稿タイプと日付からperiod文字列を生成"""
    if post_type == "daily":
        return target_date.isoformat()
    elif post_type == "weekly":
        # 当週の月曜日
        monday = target_date - __import__("datetime").timedelta(days=target_date.weekday())
        return monday.isoformat()
    elif post_type == "monthly":
        return target_date.strftime("%Y-%m")
    return target_date.isoformat()
