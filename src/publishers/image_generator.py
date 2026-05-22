"""Pillowを使ったnoteカバー画像自動生成（1280×670px）"""

import random
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.utils.astrology_data import ELEMENT_COLORS, ELEMENT_ACCENT
from src.utils.logger import get_logger

logger = get_logger("image_generator")

WIDTH = 1280
HEIGHT = 670
FONT_PATH = Path("assets/fonts/NotoSansJP-Regular.ttf")
FONT_PATH_BOLD = Path("assets/fonts/NotoSansJP-Bold.ttf")

# 数秘術用グラデーション（ライフパスナンバー別）
NUMEROLOGY_COLORS = {
    1:  {"start": (180, 30, 10),  "end": (80, 10, 5),  "accent": (255, 200, 150)},
    2:  {"start": (180, 120, 160),"end": (80, 50, 90),  "accent": (255, 230, 240)},
    3:  {"start": (200, 160, 10), "end": (100, 70, 5),  "accent": (255, 240, 100)},
    4:  {"start": (30, 120, 60),  "end": (10, 50, 20),  "accent": (180, 255, 180)},
    5:  {"start": (20, 120, 180), "end": (10, 50, 100), "accent": (150, 230, 255)},
    6:  {"start": (150, 50, 170), "end": (60, 15, 80),  "accent": (255, 180, 255)},
    7:  {"start": (80, 20, 160),  "end": (30, 5, 80),   "accent": (210, 180, 255)},
    8:  {"start": (100, 70, 10),  "end": (40, 25, 5),   "accent": (255, 215, 0)},
    9:  {"start": (150, 100, 20), "end": (60, 30, 5),   "accent": (255, 240, 180)},
    11: {"start": (60, 60, 120),  "end": (20, 20, 60),  "accent": (220, 220, 255)},
    22: {"start": (40, 100, 40),  "end": (10, 40, 10),  "accent": (200, 255, 150)},
    33: {"start": (160, 80, 20),  "end": (60, 20, 5),   "accent": (255, 220, 160)},
}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_PATH_BOLD if bold else FONT_PATH
    if path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def _create_gradient(start_rgb: Tuple, end_rgb: Tuple, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    """上から下へのグラデーション背景を作成"""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / height
        r = int(start_rgb[0] * (1 - t) + end_rgb[0] * t)
        g = int(start_rgb[1] * (1 - t) + end_rgb[1] * t)
        b = int(start_rgb[2] * (1 - t) + end_rgb[2] * t)
        arr[y] = [r, g, b]
    return Image.fromarray(arr)


def _add_stars(draw: ImageDraw.Draw, count: int = 80, seed: int = 42):
    """背景に星を散りばめる"""
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, WIDTH)
        y = rng.randint(0, int(HEIGHT * 0.85))
        r = rng.randint(1, 3)
        alpha = rng.randint(80, 200)
        draw.ellipse(
            [x - r, y - r, x + r, y + r],
            fill=(255, 255, 255),
        )


def _add_bottom_banner(draw: ImageDraw.Draw, text: str, accent_color: Tuple):
    """下部バナーを追加"""
    # 半透明風の暗い帯（黒）
    draw.rectangle([0, HEIGHT - 90, WIDTH, HEIGHT], fill=(0, 0, 0))
    # 上辺にアクセントライン
    draw.rectangle([0, HEIGHT - 92, WIDTH, HEIGHT - 88], fill=accent_color)
    font = _load_font(32, bold=True)
    draw.text(
        (WIDTH // 2, HEIGHT - 45),
        text,
        font=font,
        fill=accent_color,
        anchor="mm",
    )


def _add_decorative_circle(draw: ImageDraw.Draw, accent_color: Tuple):
    """中央背後に装飾的な円を追加"""
    cx, cy = WIDTH // 2, HEIGHT // 2 - 20
    r = 220
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        outline=(*accent_color, 40),
        width=2,
    )
    r2 = 250
    draw.ellipse(
        [cx - r2, cy - r2, cx + r2, cy + r2],
        outline=(*accent_color, 20),
        width=1,
    )


class CoverImageGenerator:
    """noteカバー画像の自動生成"""

    def generate_daily(
        self,
        sign: dict,
        date_str: str,
        output_path: str,
    ) -> str:
        """日次運勢カバー画像を生成"""
        colors = ELEMENT_COLORS[sign["element"]]
        accent = ELEMENT_ACCENT[sign["element"]]

        img = _create_gradient(colors["bg_start"], colors["bg_end"])
        draw = ImageDraw.Draw(img)

        _add_stars(draw, 70, seed=hash(sign["en"] + date_str) % 1000)
        _add_decorative_circle(draw, accent)

        symbol_font = _load_font(120)
        draw.text((WIDTH // 2, 200), sign["symbol"], font=symbol_font, fill=(255, 255, 255), anchor="mm")

        name_font = _load_font(62, bold=True)
        draw.text((WIDTH // 2, 340), f"{sign['name']} 今日の運勢", font=name_font, fill=(255, 255, 255), anchor="mm")

        period_font = _load_font(34)
        draw.text((WIDTH // 2, 415), date_str, font=period_font, fill=accent, anchor="mm")

        _add_bottom_banner(draw, "今日の詳細鑑定 ¥300", accent)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", optimize=True)
        logger.info(f"日次カバー画像生成: {output_path}")
        return output_path

    def generate_weekly(
        self,
        sign: dict,
        week_label: str,
        output_path: str,
    ) -> str:
        """週次運勢カバー画像を生成"""
        colors = ELEMENT_COLORS[sign["element"]]
        accent = ELEMENT_ACCENT[sign["element"]]

        img = _create_gradient(colors["bg_start"], colors["bg_end"])
        draw = ImageDraw.Draw(img)

        _add_stars(draw, 90, seed=hash(sign["en"]) % 1000)
        _add_decorative_circle(draw, accent)

        # 星座シンボル（大）
        symbol_font = _load_font(140)
        draw.text((WIDTH // 2, 210), sign["symbol"], font=symbol_font, fill=(255, 255, 255), anchor="mm")

        # 星座名 + ラベル
        name_font = _load_font(68, bold=True)
        draw.text((WIDTH // 2, 355), f"{sign['name']} 週間運勢", font=name_font, fill=(255, 255, 255), anchor="mm")

        # 期間テキスト
        period_font = _load_font(34)
        draw.text((WIDTH // 2, 430), week_label, font=period_font, fill=accent, anchor="mm")

        _add_bottom_banner(draw, "詳細週間運勢 ¥980", accent)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", optimize=True)
        logger.info(f"週次カバー画像生成: {output_path}")
        return output_path

    def generate_monthly(
        self,
        sign: dict,
        month_str: str,
        output_path: str,
    ) -> str:
        """月次プレミアムカバー画像を生成"""
        colors = ELEMENT_COLORS[sign["element"]]
        # 月次は少し暗めに
        start = tuple(max(0, c - 30) for c in colors["bg_start"])
        end = tuple(max(0, c - 20) for c in colors["bg_end"])
        accent = ELEMENT_ACCENT[sign["element"]]

        img = _create_gradient(start, end)
        draw = ImageDraw.Draw(img)

        _add_stars(draw, 120, seed=hash(sign["en"] + "m") % 1000)
        _add_decorative_circle(draw, accent)

        # シンボル
        symbol_font = _load_font(130)
        draw.text((WIDTH // 2, 200), sign["symbol"], font=symbol_font, fill=(255, 255, 255), anchor="mm")

        # タイトル
        name_font = _load_font(64, bold=True)
        draw.text((WIDTH // 2, 340), f"{sign['name']} プレミアム月次鑑定", font=name_font, fill=(255, 255, 255), anchor="mm")

        # 月
        month_font = _load_font(38)
        draw.text((WIDTH // 2, 420), month_str, font=month_font, fill=accent, anchor="mm")

        _add_bottom_banner(draw, "プレミアム月次鑑定 ¥1,500", accent)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", optimize=True)
        logger.info(f"月次カバー画像生成: {output_path}")
        return output_path

    def generate_numerology(
        self,
        life_path_number: int,
        number_title: str,
        output_path: str,
    ) -> str:
        """数秘術カバー画像を生成"""
        colors = NUMEROLOGY_COLORS.get(life_path_number, NUMEROLOGY_COLORS[7])
        accent = colors["accent"]

        img = _create_gradient(colors["start"], colors["end"])
        draw = ImageDraw.Draw(img)

        _add_stars(draw, 100, seed=life_path_number * 37)

        # 数字（超大）
        num_font = _load_font(220, bold=True)
        draw.text((WIDTH // 2, 250), str(life_path_number), font=num_font, fill=accent, anchor="mm")

        # タイトル
        title_font = _load_font(52, bold=True)
        draw.text((WIDTH // 2, 420), f"ライフパスナンバー「{life_path_number}」", font=title_font, fill=(255, 255, 255), anchor="mm")

        # サブタイトル
        sub_font = _load_font(36)
        draw.text((WIDTH // 2, 480), f"〜{number_title}の魂〜", font=sub_font, fill=accent, anchor="mm")

        _add_bottom_banner(draw, "数秘術プレミアム鑑定書 ¥1,500", accent)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG", optimize=True)
        logger.info(f"数秘術カバー画像生成: {output_path}")
        return output_path
