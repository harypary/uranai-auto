"""数秘術の計算ロジック"""

from datetime import date


MASTER_NUMBERS = {11, 22, 33}


def _reduce_to_single(n: int) -> int:
    """マスターナンバーを無視して1桁に還元"""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def _reduce_with_master(n: int) -> int:
    """11, 22, 33 を保持しながら還元"""
    while n > 33:
        n = sum(int(d) for d in str(n))
    if n in MASTER_NUMBERS:
        return n
    return _reduce_to_single(n)


def calculate_life_path_number(birthdate: date) -> int:
    """
    ライフパスナンバーを計算する。
    各パーツ（年・月・日）を個別に還元してから合算する方式。
    マスターナンバー（11, 22, 33）は約分しない。
    """
    y = _reduce_to_single(birthdate.year)
    m = _reduce_to_single(birthdate.month)
    d = _reduce_to_single(birthdate.day)
    return _reduce_with_master(y + m + d)


def calculate_destiny_number(full_name_reading: str) -> int:
    """
    デスティニーナンバー（運命数）をひらがな読みから計算する。
    ひらがなの50音順に番号を割り振る方式。
    """
    # あ行=1, か行=2, さ行=3, た行=4, な行=5,
    # は行=6, ま行=7, や行=8, ら行=9, わ行=0
    KANA_MAP = {
        "あ": 1, "い": 1, "う": 1, "え": 1, "お": 1,
        "か": 2, "き": 2, "く": 2, "け": 2, "こ": 2,
        "が": 2, "ぎ": 2, "ぐ": 2, "げ": 2, "ご": 2,
        "さ": 3, "し": 3, "す": 3, "せ": 3, "そ": 3,
        "ざ": 3, "じ": 3, "ず": 3, "ぜ": 3, "ぞ": 3,
        "た": 4, "ち": 4, "つ": 4, "て": 4, "と": 4,
        "だ": 4, "ぢ": 4, "づ": 4, "で": 4, "ど": 4,
        "な": 5, "に": 5, "ぬ": 5, "ね": 5, "の": 5,
        "は": 6, "ひ": 6, "ふ": 6, "へ": 6, "ほ": 6,
        "ば": 6, "び": 6, "ぶ": 6, "べ": 6, "ぼ": 6,
        "ぱ": 6, "ぴ": 6, "ぷ": 6, "ぺ": 6, "ぽ": 6,
        "ま": 7, "み": 7, "む": 7, "め": 7, "も": 7,
        "や": 8, "ゆ": 8, "よ": 8,
        "ら": 9, "り": 9, "る": 9, "れ": 9, "ろ": 9,
        "わ": 0, "を": 0, "ん": 0,
    }
    total = sum(KANA_MAP.get(c, 0) for c in full_name_reading)
    return _reduce_with_master(total)


# ライフパスナンバーの意味辞書
LIFE_PATH_MEANINGS = {
    1: {
        "title": "リーダー",
        "summary": "開拓者・独立心・強い意志力を持つ先駆者",
        "color": "赤・オレンジ",
        "stone": "ルビー・ガーネット",
        "lucky_day": "日曜日",
    },
    2: {
        "title": "協調者",
        "summary": "感受性豊かなパートナーシップと外交力の持ち主",
        "color": "白・クリーム・ピンク",
        "stone": "ムーンストーン・ローズクォーツ",
        "lucky_day": "月曜日",
    },
    3: {
        "title": "表現者",
        "summary": "創造性あふれるコミュニケーターで楽観主義の象徴",
        "color": "黄・ゴールド",
        "stone": "シトリン・アンバー",
        "lucky_day": "木曜日",
    },
    4: {
        "title": "建設者",
        "summary": "勤勉で安定を好む現実的な実行力の持ち主",
        "color": "緑・茶・グレー",
        "stone": "エメラルド・ジェイド",
        "lucky_day": "土曜日",
    },
    5: {
        "title": "自由人",
        "summary": "変化と冒険を愛する多才で自由奔放な魂",
        "color": "青・ターコイズ",
        "stone": "ターコイズ・アクアマリン",
        "lucky_day": "水曜日",
    },
    6: {
        "title": "養育者",
        "summary": "責任感と愛情深い家庭的な調和をもたらす守護者",
        "color": "ピンク・インディゴ",
        "stone": "ラピスラズリ・ローズクォーツ",
        "lucky_day": "金曜日",
    },
    7: {
        "title": "求道者",
        "summary": "分析力と神秘への探求心を持つ内省の哲学者",
        "color": "紫・バイオレット",
        "stone": "アメジスト・チャロアイト",
        "lucky_day": "月曜日",
    },
    8: {
        "title": "達成者",
        "summary": "物質的成功と権力を引き寄せる財運の波乗り師",
        "color": "金・黒・深紅",
        "stone": "オニキス・パイライト",
        "lucky_day": "土曜日",
    },
    9: {
        "title": "完成者",
        "summary": "博愛と知恵で人生を総括する奉仕の大いなる魂",
        "color": "金・白・虹色",
        "stone": "ダイヤモンド・オパール",
        "lucky_day": "火曜日",
    },
    11: {
        "title": "光の使者",
        "summary": "マスターナンバー：鋭い直感と精神的使命を持つ啓示者",
        "color": "銀・白・パール",
        "stone": "ムーンストーン・クリアクォーツ",
        "lucky_day": "月曜日",
    },
    22: {
        "title": "偉大な建設者",
        "summary": "マスターナンバー：壮大な夢を現実に変える超実践者",
        "color": "金・深緑",
        "stone": "エメラルド・ゴールデンタイガーアイ",
        "lucky_day": "土曜日",
    },
    33: {
        "title": "奉仕の師",
        "summary": "マスターナンバー：無条件の愛と癒しをもたらす宇宙の教師",
        "color": "白・ゴールド・虹",
        "stone": "セレナイト・ローズクォーツ",
        "lucky_day": "金曜日",
    },
}

# 全有効ライフパスナンバーのリスト
ALL_LIFE_PATH_NUMBERS = list(range(1, 10)) + [11, 22, 33]
