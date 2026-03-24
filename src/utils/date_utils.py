"""日付ユーティリティ"""

from datetime import date, timedelta


def get_week_range(base_date: date = None):
    """月曜始まりの週の開始日・終了日を返す"""
    if base_date is None:
        base_date = date.today()
    monday = base_date - timedelta(days=base_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_week_range_str(start: date, end: date) -> str:
    """週範囲の日本語表記を返す（例: 2026年3月23日（月）〜3月29日（日））"""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    start_wd = weekdays[start.weekday()]
    end_wd = weekdays[end.weekday()]
    return (
        f"{start.year}年{start.month}月{start.day}日（{start_wd}）"
        f"〜{end.month}月{end.day}日（{end_wd}）"
    )


def get_week_label(start: date) -> str:
    """週ラベルを返す（例: 2026年3月第4週）"""
    week_num = (start.day - 1) // 7 + 1
    return f"{start.year}年{start.month}月第{week_num}週"


def get_month_str(target_date: date = None) -> str:
    """月の日本語表記（例: 2026年4月）"""
    if target_date is None:
        target_date = date.today()
    return f"{target_date.year}年{target_date.month}月"


def get_date_str(target_date: date = None) -> str:
    """日付の日本語表記（例: 2026年3月22日（日））"""
    if target_date is None:
        target_date = date.today()
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wd = weekdays[target_date.weekday()]
    return f"{target_date.year}年{target_date.month}月{target_date.day}日（{wd}）"
