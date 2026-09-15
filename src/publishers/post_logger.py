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


def fetch_published_signs(marker: str, max_pages: int = 8) -> set:
    """note.com 上で、タイトルに marker（日次なら日付、週次なら週ラベル）と星座名の両方を含む
    公開記事の星座(en)を返す。

    post_log は Actions キャッシュ管理のため並走・復元失敗で空になり二重投稿を招く。
    note.com 本体を正として重複を防ぐ。
    """
    import requests
    from src.utils.astrology_data import ZODIAC_SIGNS
    from src.utils.logger import get_logger

    found = set()
    try:
        for page in range(1, max_pages + 1):
            r = requests.get(
                f"https://note.com/api/v2/creators/{NOTE_USER_ID}/contents",
                params={"kind": "note", "page": page},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
            )
            if r.status_code != 200:
                break
            data = r.json().get("data", {})
            contents = data.get("contents", [])
            for n in contents:
                title = n.get("name", "")
                if marker not in title:
                    continue
                for s in ZODIAC_SIGNS:
                    if s["name"] in title:
                        found.add(s["en"])
                        break
            if data.get("isLastPage") or not contents:
                break
    except Exception as e:
        get_logger("post_logger").warning(f"note.com の公開済み記事確認に失敗: {e}（post_logのみで判定します）")
    return found


def fetch_published_titles(marker: str, max_pages: int = 3) -> list:
    """note.com 上で、タイトルに marker を含む公開記事のタイトル一覧を返す。"""
    import requests

    titles = []
    try:
        for page in range(1, max_pages + 1):
            r = requests.get(
                f"https://note.com/api/v2/creators/{NOTE_USER_ID}/contents",
                params={"kind": "note", "page": page},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
            )
            if r.status_code != 200:
                break
            data = r.json().get("data", {})
            contents = data.get("contents", [])
            titles += [n.get("name", "") for n in contents if marker in n.get("name", "")]
            if data.get("isLastPage") or not contents:
                break
    except Exception:
        pass
    return titles


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
