"""Phase B.1 — Knowledge Retriever.

IntentResult から (category_hint, keywords, search_terms, intent) を取り出し、
data/knowledge/*.yaml に格納された KnowledgeChunk をランキングして返す。

ランキングは TF-IDF などではなく、以下のシンプル重み:
- category 一致           +5
- intent が chunk.intents に含まれる  +2
- keyword/tag 完全一致 (per word)     +3
- keyword/title 部分一致              +1
- keyword/body 部分一致               +0.5
"""

from __future__ import annotations

from pathlib import Path

from ..intent_extractor.types import IntentResult
from .types import KnowledgeChunk

try:
    import yaml
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False


_DATA_DIR = Path(__file__).parent / "data" / "knowledge"


class KnowledgeRetriever:
    def __init__(self, knowledge_dir: str | Path | None = None) -> None:
        self._dir = Path(knowledge_dir) if knowledge_dir else _DATA_DIR
        self._chunks: list[KnowledgeChunk] = []
        self._load()

    def _load(self) -> None:
        if not _YAML_OK or not self._dir.exists():
            return
        for path in sorted(self._dir.glob("*.yaml")):
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            category = data.get("category", "")
            for entry in data.get("chunks", []) or []:
                cid = entry.get("id")
                if not cid:
                    continue
                self._chunks.append(KnowledgeChunk(
                    id=cid,
                    title=entry.get("title", ""),
                    body=entry.get("body", "").strip(),
                    category=entry.get("category", category),
                    intents=list(entry.get("intents", []) or []),
                    tags=list(entry.get("tags", []) or []),
                    aliases=list(entry.get("aliases", []) or []),
                ))

    # intent ごとの推奨返却数 (specific 系は 1, 情報系は複数)
    _TOP_K_BY_INTENT = {
        "withdraw": 1,
        "inquiry": 1,
        "ask_faq": 2,
        "ask_roadmap": 2,
        "ask_study": 2,
        "ask_lesson": 3,
        "ask_general": 3,
        "chat": 0,
    }

    def search(self, intent_result: IntentResult,
               top_k: int | None = None) -> list[KnowledgeChunk]:
        if not self._chunks:
            return []
        category = intent_result.category_hint
        intent = intent_result.intent
        if top_k is None:
            top_k = self._TOP_K_BY_INTENT.get(intent, 3)
        if top_k <= 0:
            return []
        keywords = [k for k in intent_result.keywords if k]
        if intent_result.semantics_out:
            for v in intent_result.semantics_out.filled_schema.values():
                if isinstance(v, str) and v not in keywords:
                    keywords.append(v)

        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in self._chunks:
            score = self._score(chunk, category, intent, keywords)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda t: t[0], reverse=True)

        # intent が chunk.intents に含まれるものを優先 (intent ミスマッチを除外)
        # ただし全件除外になる場合は緩めて category 一致だけで残す。
        intent_matched = [(s, c) for s, c in scored if intent in c.intents]
        if intent_matched:
            scored = intent_matched

        return [c for _, c in scored[:top_k]]

    def _score(self, chunk: KnowledgeChunk, category: str,
               intent: str, keywords: list[str]) -> float:
        score = 0.0
        if category and chunk.category == category:
            score += 5.0
        if intent and intent in chunk.intents:
            score += 2.0
        # tag 一致
        tag_set = set(chunk.tags) | set(chunk.aliases)
        title_lower = chunk.title
        body_lower = chunk.body
        for kw in keywords:
            if not kw:
                continue
            if kw in tag_set:
                score += 3.0
                continue
            if kw in title_lower:
                score += 1.0
                continue
            if kw in body_lower:
                score += 0.5
        return score
