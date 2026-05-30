"""Gemini API ラッパー（新SDK google-genai、レート制限・リトライ・モデルフォールバック込み）"""

import os
import time

from google import genai
from google.genai import types

from src.utils.logger import get_logger

logger = get_logger("gemini_client")

# モデルは廃止されることがあるため複数候補を順に試す（先頭が優先）。
# 環境変数 GEMINI_MODEL で先頭を上書き可能。
# gemini-2.0-flash: 無料枠が潤沢（gemini-1.5-flashは廃止済みで404、2.5-flashは20req/日）
DEFAULT_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-001",
]


class GeminiClient:
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 10  # 秒

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        self._client = genai.Client(api_key=api_key)

        override = os.environ.get("GEMINI_MODEL")
        if override:
            self.models = [override] + [m for m in DEFAULT_MODELS if m != override]
        else:
            self.models = list(DEFAULT_MODELS)
        self.active_model = self.models[0]
        logger.info(f"GeminiClient 初期化完了: モデル候補={self.models}")

    def generate(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.85) -> str:
        """プロンプトを送信してテキストを生成する。

        モデルが見つからない/未対応(404)の場合は次の候補モデルへ自動フォールバックする。
        一時的なエラー(レート制限など)は指数バックオフでリトライする。
        """
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
        )

        last_error: Exception | None = None

        # active_model を先頭に、残り候補を後続にした順序で試す
        ordered = [self.active_model] + [m for m in self.models if m != self.active_model]

        for model_name in ordered:
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                    result = response.text.strip()
                    if model_name != self.active_model:
                        logger.info(f"モデル切替: {self.active_model} → {model_name}")
                        self.active_model = model_name
                    logger.debug(f"生成成功({model_name}): {len(result)}文字")
                    return result

                except Exception as e:
                    last_error = e
                    msg = str(e)
                    # 404 NOT_FOUND / 未対応モデル → リトライせず次のモデルへ
                    if "404" in msg or "NOT_FOUND" in msg or "not found" in msg or "not supported" in msg:
                        logger.warning(f"モデル {model_name} は利用不可(404)。次の候補へフォールバック")
                        break
                    # それ以外（レート制限・一時障害）→ バックオフしてリトライ
                    wait = self.RETRY_BASE_DELAY * (attempt + 1)
                    logger.warning(f"Gemini APIエラー({model_name} 試行{attempt + 1}/{self.MAX_RETRIES}): {e}")
                    if attempt < self.MAX_RETRIES - 1:
                        logger.info(f"{wait}秒後にリトライ...")
                        time.sleep(wait)

        raise RuntimeError(f"Gemini API 失敗（全モデル候補で失敗）: {last_error}") from last_error
