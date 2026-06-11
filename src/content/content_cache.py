"""生成済みコンテンツのディスクキャッシュ。

Gemini無料枠は1モデル20リクエスト/日しかないため、一度生成した記事は
公開に失敗しても捨てずに再利用する。ワークフローの再試行（同一ジョブ内で
最大3回スクリプトを実行）でも output/ は残るので、2回目以降は生成をスキップできる。
"""

import json
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("content_cache")

CACHE_DIR = Path("output/content_cache")


def _path(post_type: str, period: str, key: str) -> Path:
    safe = f"{post_type}_{period}_{key}".replace("/", "-")
    return CACHE_DIR / f"{safe}.json"


def load(post_type: str, period: str, key: str) -> dict | None:
    """キャッシュ済みコンテンツを返す。なければ None。"""
    p = _path(post_type, period, key)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("teaser") and data.get("paid"):
                logger.info(f"生成キャッシュ再利用: {p.name}（Gemini呼び出しを節約）")
                return data
        except Exception:
            pass
    return None


def save(post_type: str, period: str, key: str, **fields) -> None:
    """生成直後のコンテンツを保存する。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(post_type, period, key)
    p.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
