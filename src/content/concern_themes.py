"""悩み特化の高単価記事（常設販売）のテーマ定義。

検索流入が強く、悩みが深い人ほど課金する領域。星座×テーマで個別感を出す。
手書きの初期テーマは CONCERN_THEMES に定義。全テーマが公開済みになると
Geminiが新テーマを自動生成し data/concern_themes_dynamic.json に追記される。
"""

import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
DYNAMIC_THEMES_FILE = _ROOT / "data" / "concern_themes_dynamic.json"
# リポジトリへのコミットは PAT の権限次第で失敗する（403）ため、Actions キャッシュで
# 運ばれる output/ 配下にも同じ内容を書き、どちらか残っていればテーマを失わないようにする。
DYNAMIC_THEMES_CACHE = _ROOT / "output" / "concern_themes_dynamic.json"
_DYNAMIC_FILES = (DYNAMIC_THEMES_FILE, DYNAMIC_THEMES_CACHE)

CONCERN_THEMES = [
    {
        "key": "reunion",
        "title": "復縁占い｜あの人とやり直せる？",
        "audience": "別れたあの人ともう一度やり直したい、でも可能性があるのか不安",
        "keyword": "復縁の可能性",
        "core_question": "あの人と復縁できるのか、できるとしたらいつ・どうすればいいのか",
        "bullets": "・あの人があなたに今抱いている本当の気持ち\n・復縁できる可能性と、その時期\n・あなたが今すぐすべきこと／してはいけないこと",
        "hashtags": ["復縁", "復縁占い", "恋愛占い", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "marriage_timing",
        "title": "結婚時期占い｜あなたが結婚する時期",
        "audience": "自分がいつ結婚できるのか、本当に結婚できるのか知りたい",
        "keyword": "結婚の時期",
        "core_question": "あなたが結婚する時期はいつか、どんな相手と結ばれるのか",
        "bullets": "・あなたが結婚に最も近づく時期\n・あなたと結ばれる運命の相手の特徴\n・結婚運を引き寄せるために今できること",
        "hashtags": ["結婚占い", "結婚時期", "恋愛占い", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "compatibility",
        "title": "相性占い｜好きなあの人との相性",
        "audience": "気になるあの人との相性が良いのか、どう縁を深めればいいのか知りたい",
        "keyword": "あの人との相性",
        "core_question": "あなたと気になる相手の相性はどうなのか、縁を深めるにはどうすべきか",
        "bullets": "・あなたとあの人の本当の相性\n・二人の縁を深める鍵となる行動\n・関係が動き出す時期",
        "hashtags": ["相性占い", "恋愛占い", "占い", "星座占い", "片思い"],
        "price": 1780,
    },
    {
        "key": "career",
        "title": "転職・天職占い｜あなたの本当の才能と動くべき時期",
        "audience": "今の仕事を続けるべきか転職すべきか迷っている、自分の天職を知りたい",
        "keyword": "仕事と天職",
        "core_question": "あなたが転職すべきか、あなたの本当の才能と天職、動くべき時期はいつか",
        "bullets": "・あなたに眠る本当の才能・天職\n・転職すべきか、留まるべきか\n・キャリアが大きく動く時期",
        "hashtags": ["転職占い", "仕事占い", "天職", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "money_luck",
        "title": "金運占い｜あなたにお金が入ってくる流れ",
        "audience": "お金の不安から解放されたい、自分の金運と豊かになる方法を知りたい",
        "keyword": "金運の流れ",
        "core_question": "あなたの金運はこれからどうなるのか、お金を引き寄せるにはどうすべきか",
        "bullets": "・あなたの金運が上昇する時期\n・あなたにお金が入ってくる流れの作り方\n・避けるべき金運を下げる行動",
        "hashtags": ["金運", "金運アップ", "占い", "星座占い", "開運"],
        "price": 1780,
    },
]


# 恋愛に絞った特化テーマ（日曜枠）。恋愛は占いで最も需要が大きく、悩みが深いほど課金される。
LOVE_THEMES = [
    {
        "key": "love_his_feelings",
        "group": "love",
        "title": "あの人の本音占い｜今あなたをどう思っている？",
        "audience": "好きな人が自分をどう思っているのか分からず、関係が進まないまま苦しい",
        "keyword": "あの人の本音",
        "core_question": "あの人が今あなたに抱いている本当の気持ちは何か、関係は進むのか",
        "bullets": "・あの人が今あなたに抱いている本当の感情\n・あの人があなたに言えずにいること\n・二人の関係が動き出す時期とあなたが取るべき行動",
        "hashtags": ["恋愛占い", "片思い", "本音", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "love_unrequited",
        "group": "love",
        "title": "片思い成就占い｜この恋は叶う？",
        "audience": "片思いが報われるのか、諦めるべきなのか分からず動けない",
        "keyword": "片思いの行方",
        "core_question": "この片思いは叶うのか、叶うとしたらいつ・何をすればいいのか",
        "bullets": "・この恋が叶う可能性と、その時期\n・あの人の心が動く瞬間ときっかけ\n・今のあなたがやってはいけないこと",
        "hashtags": ["片思い", "恋愛占い", "恋愛成就", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "love_should_i_leave",
        "group": "love",
        "title": "別れるべきか占い｜この人と続けていい？",
        "audience": "今の相手と続けるべきか別れるべきか、何年も迷い続けている",
        "keyword": "別れの決断",
        "core_question": "この相手と続けるべきか別れるべきか、星はどちらを示しているのか",
        "bullets": "・この関係が今あなたにもたらしているもの\n・続けた場合と別れた場合、それぞれの未来\n・決断すべき時期の見極め方",
        "hashtags": ["恋愛占い", "別れ", "恋愛相談", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "love_silence",
        "group": "love",
        "title": "音信不通占い｜あの人から連絡は来る？",
        "audience": "連絡が途絶えたあの人を待ち続けていて、毎日スマホを見てしまう",
        "keyword": "音信不通の理由",
        "core_question": "あの人が連絡をくれない理由は何か、また連絡は来るのか",
        "bullets": "・あの人が連絡をくれない本当の理由\n・再びつながりが戻る時期\n・待つべきか、あなたから動くべきか",
        "hashtags": ["音信不通", "恋愛占い", "復縁", "占い", "星座占い"],
        "price": 1980,
    },
    {
        "key": "love_destiny",
        "group": "love",
        "title": "運命の相手占い｜あなたが出会う人の正体",
        "audience": "本当に自分を愛してくれる相手にまだ出会えていないと感じている",
        "keyword": "運命の相手",
        "core_question": "あなたの運命の相手はどんな人で、いつどこで出会うのか",
        "bullets": "・あなたの運命の相手の特徴（外見・性格・環境）\n・出会いが訪れる時期と場所\n・その出会いを逃さないためにすべきこと",
        "hashtags": ["運命の人", "恋愛占い", "出会い", "占い", "星座占い"],
        "price": 1980,
    },
]

_GROUPS = {"general": CONCERN_THEMES, "love": LOVE_THEMES}


def load_dynamic_themes() -> list[dict]:
    """自動生成された動的テーマを読み込む（リポジトリ側とキャッシュ側をkeyでマージ）。"""
    merged: list[dict] = []
    seen = set()
    for path in _DYNAMIC_FILES:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for t in data:
            key = t.get("key") if isinstance(t, dict) else None
            if key and key not in seen:
                merged.append(t)
                seen.add(key)
    return merged


def load_all_themes(group: str = "general") -> list[dict]:
    """指定グループの手書き＋動的テーマを、keyの重複を除いて返す。

    group を持たない既存の動的テーマは "general" として扱う（後方互換）。
    """
    themes = list(_GROUPS.get(group, CONCERN_THEMES))
    seen = {t["key"] for t in themes}
    for t in load_dynamic_themes():
        if t.get("key") and t["key"] not in seen and t.get("group", "general") == group:
            themes.append(t)
            seen.add(t["key"])
    return themes


def save_dynamic_theme(theme: dict) -> None:
    """動的テーマを1件追記し、リポジトリ側とキャッシュ側の両方へ保存する。"""
    current = load_dynamic_themes()
    current.append(theme)
    body = json.dumps(current, ensure_ascii=False, indent=2)
    for path in _DYNAMIC_FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def get_theme(key: str) -> dict | None:
    for group in _GROUPS:
        for t in load_all_themes(group):
            if t["key"] == key:
                return t
    return None
