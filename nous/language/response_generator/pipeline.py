"""Phase B.1 — Response Generator pipeline.

3-4 層:
  Router → Retriever → Composer [→ Naturalizer (optional)]

Naturalizer は nano LLM で chunks を自然言語に仕上げる任意 4 層目。
- 無し: 純 rules 出力 (高速・無料・テンプレ)
- 有り: rules で intent/検索を確定し、nano で文面のみ仕上げ (ハイブリッド)
"""

from __future__ import annotations

import time
from pathlib import Path

from ..intent_extractor.types import IntentResult
from .composer import ResponseComposer
from .retriever import KnowledgeRetriever
from .router import ResponseRouter
from .types import ResponseResult


class ResponseGenerator:
    def __init__(self,
                 router: ResponseRouter | None = None,
                 retriever: KnowledgeRetriever | None = None,
                 composer: ResponseComposer | None = None,
                 naturalizer=None,
                 low_confidence_threshold: float = 0.25,
                 knowledge_dir: str | Path | None = None,
                 templates_path: str | Path | None = None) -> None:
        self.router = router or ResponseRouter(low_confidence_threshold=low_confidence_threshold)
        self.retriever = retriever or KnowledgeRetriever(knowledge_dir=knowledge_dir)
        self.composer = composer or ResponseComposer(templates_path=templates_path)
        self.naturalizer = naturalizer  # None = pure rules

    @classmethod
    def from_config(cls, domain: str = "default") -> "ResponseGenerator":
        return cls()

    def generate(self, intent_result: IntentResult,
                 top_k: int | None = None,
                 user_text: str | None = None) -> ResponseResult:
        """top_k=None で intent ごとの推奨数 (retriever 内で決定)。
        user_text 指定で Naturalizer に渡す元入力を上書き可能。
        """
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        strategy = self.router.route(intent_result)
        timings["router_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        chunks = (self.retriever.search(intent_result, top_k=top_k)
                  if strategy.needs_retrieval else [])
        timings["retriever_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        result = self.composer.compose(strategy, intent_result, chunks)
        timings["composer_ms"] = (time.perf_counter() - t0) * 1000

        # Optional 4th layer: nano polish (only when chunks are present)
        if self.naturalizer is not None and chunks:
            t0 = time.perf_counter()
            polished, cost, tokens = self.naturalizer.polish(
                user_text or intent_result.trace.get("raw", ""),
                intent_result, chunks,
            )
            timings["naturalizer_ms"] = (time.perf_counter() - t0) * 1000
            if polished.strip():
                result.text = polished
                result.trace["naturalizer_cost_jpy"] = cost
                result.trace["naturalizer_tokens"] = tokens
                result.trace["naturalized"] = True

        result.trace["timings"] = timings
        return result

    async def generate_async(self, intent_result: IntentResult,
                              top_k: int | None = None,
                              user_text: str | None = None) -> ResponseResult:
        """非同期版。Naturalizer の polish_async を使う。"""
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        strategy = self.router.route(intent_result)
        timings["router_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        chunks = (self.retriever.search(intent_result, top_k=top_k)
                  if strategy.needs_retrieval else [])
        timings["retriever_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        result = self.composer.compose(strategy, intent_result, chunks)
        timings["composer_ms"] = (time.perf_counter() - t0) * 1000

        if self.naturalizer is not None and chunks:
            t0 = time.perf_counter()
            polished, cost, tokens = await self.naturalizer.polish_async(
                user_text or intent_result.trace.get("raw", ""),
                intent_result, chunks,
            )
            timings["naturalizer_ms"] = (time.perf_counter() - t0) * 1000
            if polished.strip():
                result.text = polished
                result.trace["naturalizer_cost_jpy"] = cost
                result.trace["naturalizer_tokens"] = tokens
                result.trace["naturalized"] = True

        result.trace["timings"] = timings
        return result
