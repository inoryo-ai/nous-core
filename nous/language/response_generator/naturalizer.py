"""Phase B.1+ — Naturalizer (nano-based natural language polish).

rules-based ルーター+リトリーバーが選んだ KnowledgeChunk と元のユーザー質問を
nano LLM に渡し、自然な日本語に整形させる。

設計境界:
- intent 判定 / chunk 選択は rules で確定済みのため、nano は再判定しない
- nano は与えられた chunks の情報を自然文に整形するだけ (役割を限定)
- chunks が空のときは nano を呼ばずテンプレで返す (コスト 0)

これにより:
- 旧パイプラインの「intent抽出 nano呼び出し」を削減 (~50%コスト減)
- intent 精度は rules の 100% を維持
- 応答文の自然さは nano の品質を維持
"""

from __future__ import annotations

import os

from ..intent_extractor.types import IntentResult
from .types import KnowledgeChunk, ResponseResult


_DEFAULT_PROMPT = """あなたは優しい学習サポートAIアシスタントです。
以下の検索結果を、受講生に向けて2-4文の自然な日本語に整形してください。
- 必ず「提示理由」を1文添える（例: 「カテゴリXに該当しますので」）
- 講座名・項目名は、候補の「項目名」フィールドに書かれた値を一字一句そのまま使ってください。書き換え・短縮・推測・捏造は厳禁です
- URL は候補に書かれている値を一字一句そのまま使ってください。創作・推測・短縮は厳禁です
- URL を書く時は「文末に半角スペース + URL」だけ。「URLは X です」のような変数代入風テンプレは禁止
- 複数候補は箇条書きで示してください
- 応答に書いてはいけないもの: 「候補1」「---」などのシステム区切り、JSON ラベル
- 押し付けでなく「いかがでしょう」「お役立てください」のトーン、絵文字なし、敬語ベース
"""


class NaturalizerNano:
    """nano LLM で chunks を自然言語に整形する。

    Args:
        model: OpenAI モデル名 (デフォルト gpt-4.1-nano)
        api_key: 明示指定。None なら環境変数 OPENAI_API_KEY を使う
        prompt: system prompt。None でデフォルト
        max_tokens: 応答長制限
        temperature: 生成温度
        async_mode: True なら ask_async で使う AsyncOpenAI を初期化
    """

    def __init__(self,
                 model: str = "gpt-4.1-nano",
                 api_key: str | None = None,
                 prompt: str | None = None,
                 max_tokens: int = 600,
                 temperature: float = 0.4,
                 async_mode: bool = False) -> None:
        from openai import AsyncOpenAI, OpenAI

        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.prompt = prompt or _DEFAULT_PROMPT
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key) if not async_mode else None
        self.async_client = AsyncOpenAI(api_key=api_key) if async_mode else None
        self._last_cost_jpy = 0.0

    @property
    def last_cost_jpy(self) -> float:
        return self._last_cost_jpy

    # ---- sync ----

    def polish(self, user_text: str, intent_result: IntentResult,
               chunks: list[KnowledgeChunk]) -> tuple[str, float, int]:
        """chunks を自然言語に整形。

        Returns: (polished_text, cost_jpy, prompt_tokens)
        """
        if not chunks:
            return "", 0.0, 0
        if self.client is None:
            raise RuntimeError("NaturalizerNano was initialized for async mode")
        user_prompt = self._build_user_prompt(user_text, intent_result, chunks)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        text = resp.choices[0].message.content or ""
        cost = self._estimate_cost(resp.usage)
        self._last_cost_jpy = cost
        return text, cost, resp.usage.total_tokens

    # ---- async ----

    async def polish_async(self, user_text: str, intent_result: IntentResult,
                            chunks: list[KnowledgeChunk]) -> tuple[str, float, int]:
        if not chunks:
            return "", 0.0, 0
        if self.async_client is None:
            raise RuntimeError("NaturalizerNano was initialized for sync mode")
        user_prompt = self._build_user_prompt(user_text, intent_result, chunks)
        resp = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        text = resp.choices[0].message.content or ""
        cost = self._estimate_cost(resp.usage)
        self._last_cost_jpy = cost
        return text, cost, resp.usage.total_tokens

    # ---- helpers ----

    def _build_user_prompt(self, user_text: str, intent_result: IntentResult,
                           chunks: list[KnowledgeChunk]) -> str:
        chunk_block = ""
        for i, c in enumerate(chunks[:3], 1):
            chunk_block += f"\n--- 候補{i} ---\n項目名: {c.title}\n本文:\n{c.body}\n"
        intent_info = (f"intent={intent_result.intent}"
                       + (f", category={intent_result.category_hint}"
                          if intent_result.category_hint else ""))
        return (
            f"受講生の質問: {user_text}\n"
            f"確定した意図: {intent_info}\n\n"
            f"検索結果（実在する候補）:{chunk_block}\n\n"
            f"これを自然に整形してください。複数候補は箇条書き、URL省略禁止。"
        )

    def _estimate_cost(self, usage) -> float:
        """gpt-4.1-nano price (2026 時点):
           input: $0.10 / 1M tokens, output: $0.40 / 1M tokens
           JPY 換算: 1 USD ≈ 150 JPY (概算)
        """
        if usage is None:
            return 0.0
        in_tok = getattr(usage, "prompt_tokens", 0)
        out_tok = getattr(usage, "completion_tokens", 0)
        usd = in_tok / 1_000_000 * 0.10 + out_tok / 1_000_000 * 0.40
        return round(usd * 150, 4)
