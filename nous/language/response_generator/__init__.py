"""Phase B.1 — LLM-free 日本語応答生成。

3 層: Router (intent → strategy) → Retriever (knowledge 検索) → Composer (テンプレ合成)
"""

from .naturalizer import NaturalizerNano
from .pipeline import ResponseGenerator
from .retriever import KnowledgeRetriever
from .types import KnowledgeChunk, ResponseResult, ResponseStrategy

__all__ = [
    "ResponseGenerator",
    "ResponseResult",
    "ResponseStrategy",
    "KnowledgeChunk",
    "KnowledgeRetriever",
    "NaturalizerNano",
]
