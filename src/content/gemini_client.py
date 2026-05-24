"""Gemini API ラッパー（新SDK google-genai、レート制限・リトライ込み）"""

import os
import time

from google import genai
from google.genai import types

from src.utils.logger import get_logger

logger = get_logger("gemini_client")


class GeminiClient:
    MODEL = "gemini-1.5-flash"  # 無料枠1500req/日（2.5-flashは20req/日のため変更）
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 10  # 秒

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")
        self._client = genai.Client(api_key=api_key)
        logger.info(f"GeminiClient 初期化完了: {self.MODEL}")

    def generate(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.85) -> str:
        """プロンプトを送信してテキストを生成する"""
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
        )

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=self.MODEL,
                    contents=prompt,
                    config=config,
                )
                result = response.text.strip()
                logger.debug(f"生成成功: {len(result)}文字")
                return result

            except Exception as e:
                wait = self.RETRY_BASE_DELAY * (attempt + 1)
                logger.warning(f"Gemini API エラー (試行{attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    logger.info(f"{wait}秒後にリトライ...")
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"Gemini API 失敗（{self.MAX_RETRIES}回試行）: {e}") from e

        raise RuntimeError("到達不能コード")
