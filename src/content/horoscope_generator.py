"""星座占いコンテンツ生成"""

import random
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple

from src.content.gemini_client import GeminiClient
from src.utils.date_utils import get_week_range_str, get_week_label, get_date_str, get_month_str
from src.utils.logger import get_logger

logger = get_logger("horoscope_generator")

PROMPT_DIR = Path(__file__).parent / "prompts"
PAID_BOUNDARY = "---PAID_BOUNDARY---"

# 引き込むタイトルワード（調査データに基づく）
WEEKLY_TITLE_PATTERNS = [
    "【{sign}】週間運勢 {week}｜{angle}",
    "{sign}さんへ。今週の正直な運勢 {week}",
    "【{sign}】{week} 当たりすぎ注意の週間占い",
    "{sign}の今週（{week}）｜{angle}",
    "【保存版】{sign}の週間運勢 {week}｜恋愛・仕事・金運",
]

WEEKLY_ANGLE_WORDS = [
    "恋愛・仕事・金運の全真実",
    "今週あなたに起きること",
    "転機が来る人・来ない人",
    "動くべき日・休むべき日",
    "彼の気持ちと仕事運の完全鑑定",
    "今週の運命的な分岐点",
    "天使の日はいつ？完全鑑定",
]

MONTHLY_TITLE_PATTERNS = [
    "【{sign}】{month} プレミアム月次鑑定｜{angle}",
    "{sign}さんへ。{month}の本当の運勢",
    "【{sign}・{month}】当たりすぎ注意の月次占い完全版",
    "【保存版】{sign}の{month}｜{angle}",
]

MONTHLY_ANGLE_WORDS = [
    "恋愛・仕事・財運 完全解説",
    "今月あなたの人生に何が起きるか",
    "転機の月？詳細鑑定で答えを出す",
    "今月こそ動くべき理由と戦略",
    "天体メッセージ×タロット完全版",
]


def _load_prompt(filename: str) -> str:
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")


def _random_stars(min_val: int = 2, max_val: int = 5) -> str:
    n = random.randint(min_val, max_val)
    return "★" * n + "☆" * (5 - n)


def generate_weekly_title(sign: dict, week_label: str) -> str:
    """週次記事の引き込むタイトルを生成（25〜30文字）"""
    pattern = random.choice(WEEKLY_TITLE_PATTERNS)
    angle = random.choice(WEEKLY_ANGLE_WORDS)
    title = pattern.format(
        sign=sign["name"],
        week=week_label,
        angle=angle,
    )
    return title


def generate_monthly_title(sign: dict, month_str: str) -> str:
    """月次記事の引き込むタイトルを生成"""
    pattern = random.choice(MONTHLY_TITLE_PATTERNS)
    angle = random.choice(MONTHLY_ANGLE_WORDS)
    title = pattern.format(
        sign=sign["name"],
        month=month_str,
        angle=angle,
    )
    return title


class HoroscopeGenerator:
    def __init__(self, client: GeminiClient):
        self._client = client

    def generate_daily(self, sign: dict, target_date: date = None) -> str:
        """日次占い（X投稿用・110〜130文字）"""
        if target_date is None:
            target_date = date.today()

        prompt_template = _load_prompt("daily_horoscope.txt")
        prompt = prompt_template.format(
            sign_name=sign["name"],
            symbol=sign["symbol"],
            period=sign["period"],
            element=sign["element"],
            ruling_planet=sign["ruling_planet"],
            keywords="・".join(sign["keywords"]),
            date_str=get_date_str(target_date),
        )

        content = self._client.generate(prompt, max_tokens=512, temperature=0.90)
        logger.info(f"[日次] {sign['name']} 生成完了: {len(content)}文字")
        return content

    def generate_weekly(
        self,
        sign: dict,
        week_start: date,
        week_end: date,
    ) -> Tuple[str, str]:
        """週次占い → (ティーザー, 有料コンテンツ) を返す"""
        week_range = get_week_range_str(week_start, week_end)
        week_label = get_week_label(week_start)

        prompt_template = _load_prompt("weekly_horoscope.txt")
        prompt = prompt_template.format(
            sign_name=sign["name"],
            symbol=sign["symbol"],
            period=sign["period"],
            element=sign["element"],
            ruling_planet=sign["ruling_planet"],
            keywords="・".join(sign["keywords"]),
            week_start=week_range.split("〜")[0],
            week_end=week_range.split("〜")[1],
            week_label=week_label,
            love_stars=_random_stars(2, 5),
            work_stars=_random_stars(2, 5),
            money_stars=_random_stars(2, 5),
            overall_stars=_random_stars(3, 5),
        )

        raw = self._client.generate(prompt, max_tokens=4096, temperature=0.87)
        teaser, paid = _split_content(raw)
        logger.info(
            f"[週次] {sign['name']} 生成完了: "
            f"ティーザー{len(teaser)}文字 / 有料{len(paid)}文字"
        )
        return teaser, paid

    def generate_monthly(
        self,
        sign: dict,
        target_date: date = None,
    ) -> Tuple[str, str]:
        """月次占い → (ティーザー, 有料コンテンツ) を返す"""
        if target_date is None:
            target_date = date.today()

        themes = [
            "自己成長と変容", "新しい出会いと縁", "財運と豊かさ",
            "創造性と表現", "愛と関係性の深化", "内なる声との対話",
            "転換と再生", "本当の自分を取り戻す",
        ]
        theme = random.choice(themes)

        # 週別カレンダー用の日付（月の各週末日）
        month_end = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        week1_end = min(7, month_end.day)
        week2_end = min(14, month_end.day)
        week3_end = min(21, month_end.day)

        prompt_template = _load_prompt("monthly_horoscope.txt")
        prompt = prompt_template.format(
            sign_name=sign["name"],
            symbol=sign["symbol"],
            period=sign["period"],
            element=sign["element"],
            ruling_planet=sign["ruling_planet"],
            keywords="・".join(sign["keywords"]),
            month_str=get_month_str(target_date),
            love_stars=_random_stars(2, 5),
            work_stars=_random_stars(2, 5),
            money_stars=_random_stars(2, 5),
            overall_stars=_random_stars(3, 5),
            theme=theme,
            week1_end=week1_end,
            week2_end=week2_end,
            week3_end=week3_end,
        )

        raw = self._client.generate(prompt, max_tokens=8192, temperature=0.85)
        teaser, paid = _split_content(raw)
        logger.info(
            f"[月次] {sign['name']} 生成完了: "
            f"ティーザー{len(teaser)}文字 / 有料{len(paid)}文字"
        )
        return teaser, paid


def _split_content(raw: str) -> Tuple[str, str]:
    """PAID_BOUNDARY で分割してティーザーと有料コンテンツを返す"""
    if PAID_BOUNDARY in raw:
        parts = raw.split(PAID_BOUNDARY, 1)
        return parts[0].strip(), parts[1].strip()
    logger.warning("PAID_BOUNDARY が見つかりません。先頭300文字をティーザーとして使用します。")
    return raw[:300], raw[300:]
