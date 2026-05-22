"""数秘術コンテンツ生成"""

from pathlib import Path
from typing import Tuple

from src.content.gemini_client import GeminiClient
from src.utils.numerology_calc import LIFE_PATH_MEANINGS
from src.utils.logger import get_logger

logger = get_logger("numerology_generator")

PROMPT_DIR = Path(__file__).parent / "prompts"
PAID_BOUNDARY = "---PAID_BOUNDARY---"
STRATEGY_FILE = Path(__file__).parent.parent.parent / "output" / "strategy" / "current_strategy.txt"


def _load_strategy() -> str:
    try:
        if STRATEGY_FILE.exists():
            text = STRATEGY_FILE.read_text(encoding="utf-8").strip()
            if text:
                return f"【過去の販売データから導いた戦略】\n{text}\n"
    except Exception:
        pass
    return ""


class NumerologyGenerator:
    def __init__(self, client: GeminiClient):
        self._client = client

    def generate_life_path_article(self, life_path_number: int) -> Tuple[str, str]:
        """ライフパスナンバーの鑑定記事 → (ティーザー, 有料コンテンツ)"""
        if life_path_number not in LIFE_PATH_MEANINGS:
            raise ValueError(f"無効なライフパスナンバー: {life_path_number}")

        info = LIFE_PATH_MEANINGS[life_path_number]
        prompt_template = (PROMPT_DIR / "numerology.txt").read_text(encoding="utf-8")

        prompt = prompt_template.format(
            life_path_number=life_path_number,
            number_title=info["title"],
            number_summary=info["summary"],
            lucky_color=info["color"],
            lucky_stone=info["stone"],
            strategy_context=_load_strategy(),
        )

        raw = self._client.generate(prompt, max_tokens=8192, temperature=0.82)

        if PAID_BOUNDARY in raw:
            parts = raw.split(PAID_BOUNDARY, 1)
            teaser, paid = parts[0].strip(), parts[1].strip()
        else:
            logger.warning(f"LP{life_path_number}: PAID_BOUNDARY なし。先頭250文字をティーザーとして使用。")
            teaser, paid = raw[:250], raw[250:]

        logger.info(
            f"[数秘] LP{life_path_number}({info['title']}) 生成完了: "
            f"ティーザー{len(teaser)}文字 / 有料{len(paid)}文字"
        )
        return teaser, paid
