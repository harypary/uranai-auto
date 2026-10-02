"""既存の悩みテーマが全て公開済みになったとき、Geminiで新しい悩みテーマを自動生成する。

これにより悩み特化カタログが尽きることなく、永遠に新テーマを積み増せる。
生成テーマは data/concern_themes_dynamic.json に永続化され、リポジトリにコミットされる。
"""

import json
import re

from src.content.gemini_client import GeminiClient
from src.utils.logger import get_logger

logger = get_logger("concern_theme_generator")

NEW_THEME_PRICE = 1980

_LOVE_CONSTRAINT = "- 必ず恋愛領域（片思い・復縁・結婚・不安・すれ違い・別れ・出会い）のテーマにすること"
_GENERAL_CONSTRAINT = "- 恋愛・結婚・仕事・お金・人間関係・人生・健康運など、課金されやすい領域から選ぶこと"

_PROMPT = """あなたは占い・スピリチュアル系の有料note記事を企画するプロの編集者です。
日本の検索ユーザーが「お金を払ってでも占ってほしい」と切実に悩む、新しい鑑定テーマを1つ考えてください。

【すでにある（重複NG）テーマ】
{existing}

【条件】
- 上のテーマと内容が被らない、新しい切り口の悩みであること
- 検索流入が見込め、悩みが深く課金されやすい領域であること
{extra_constraint}
- 星座占いで12星座それぞれに個別鑑定できるテーマであること

【出力】以下のJSONだけを出力してください。前後に説明文やコードブロック記号を付けないこと。
{{
  "key": "英小文字とアンダースコアのみの短いスラッグ（例: love_triangle）",
  "title": "記事タイトル（占い｜で始まる魅力的な見出し。例: 略奪愛占い｜あの人を本当に奪える？）",
  "audience": "この記事を読む人の切実な状況を1文で",
  "keyword": "鑑定の中心となる短いキーワード（例: 略奪愛の可能性）",
  "core_question": "読者が最も知りたい問いを1文で",
  "bullets": "この鑑定で視えることを3つ、それぞれ『・』で始め『\\n』で区切った1つの文字列で",
  "hashtags": ["関連ハッシュタグを5個。最後は必ず 星座占い"]
}}
"""

_REQUIRED_KEYS = ("key", "title", "audience", "keyword", "core_question", "bullets", "hashtags")


def _extract_json(raw: str) -> dict:
    """Gemini出力からJSONオブジェクトを取り出す。コードフェンスや前置きを許容する。"""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSONが見つかりません: {raw[:200]}")
    # Geminiが文字列内に生の改行を混ぜることがあるため strict=False で許容
    return json.loads(text[start : end + 1], strict=False)


def _slugify(key: str, fallback_index: int) -> str:
    key = re.sub(r"[^a-z0-9_]", "", (key or "").lower().replace(" ", "_"))
    return key or f"dyn_{fallback_index}"


def generate_new_theme(
    gemini: GeminiClient, existing_themes: list[dict], group: str = "general"
) -> dict:
    """既存テーマと被らない新しい悩みテーマを1つ生成して返す。

    group="love" のときは恋愛領域に限定したテーマを生成する。
    """
    existing_titles = [t.get("title", "") for t in existing_themes]
    existing_keys = {t.get("key", "") for t in existing_themes}

    prompt = _PROMPT.format(
        existing="\n".join(f"- {t}" for t in existing_titles) or "（なし）",
        extra_constraint=_LOVE_CONSTRAINT if group == "love" else _GENERAL_CONSTRAINT,
    )
    # 思考型モデル（gemini-3.x系）は出力枠を思考に使うため、1024トークンではJSONが
    # 書き切れず途中で切れる。枠を広げ、それでも壊れていれば作り直す。
    data = None
    last_error: Exception | None = None
    for attempt in range(3):
        raw = gemini.generate(prompt, max_tokens=8192, temperature=0.95)
        try:
            candidate = _extract_json(raw)
            missing = [k for k in _REQUIRED_KEYS if k not in candidate]
            if missing:
                raise ValueError(f"必須キー不足 {missing}")
            data = candidate
            break
        except Exception as e:
            last_error = e
            logger.warning(
                f"新テーマJSONの解析に失敗 (試行{attempt + 1}/3): {str(e)[:150]} / 応答先頭={raw[:120]!r}"
            )
    if data is None:
        raise ValueError(f"新テーマを生成できませんでした: {last_error}")

    # キーの正規化＋重複回避
    base_key = _slugify(str(data["key"]), len(existing_themes))
    key = base_key
    suffix = 2
    while key in existing_keys:
        key = f"{base_key}_{suffix}"
        suffix += 1
    data["key"] = key

    # hashtags が文字列で返ってきた場合に配列化
    if isinstance(data["hashtags"], str):
        data["hashtags"] = [h.strip() for h in re.split(r"[,、\s]+", data["hashtags"]) if h.strip()]
    # note の入力欄は「#」不要。「#星座占い」と「星座占い」が二重に入らないよう正規化する
    tags = []
    for h in data["hashtags"]:
        t = str(h).lstrip("#").strip()
        if t and t not in tags:
            tags.append(t)
    if "星座占い" not in tags:
        tags.append("星座占い")
    data["hashtags"] = tags[:5]

    data["price"] = NEW_THEME_PRICE
    data["group"] = group

    logger.info(f"新テーマ生成[{group}]: {data['key']} / {data['title']} (¥{data['price']})")
    return data
