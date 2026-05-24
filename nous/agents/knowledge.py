"""KnowledgeAgent — agent that uses NOUS BookShelf for fact retrieval.

This is the abstraction behind student-assistant style agents: take a query,
retrieve top candidates from the BookShelf, optionally have an LLM naturalize
the response. Subclasses can override _retrieve and _format.
"""
from __future__ import annotations

from ..runtime.agent import Agent


class KnowledgeAgent(Agent):
    """Agent that retrieves facts from a NOUS Brain (BookShelf-backed).

    Lightweight default: returns the top-k retrieval as raw structured output.
    Subclasses can override _format() to add LLM-based naturalization.
    """
    NAME = 'knowledge_agent'

    def __init__(self, *,
                 name: str | None = None,
                 description: str = '',
                 brain=None,
                 top_k: int = 3,
                 books_filter: list[str] | None = None):
        super().__init__(name=name, description=description)
        self.brain = brain
        self.top_k = top_k
        self.books_filter = books_filter

    def _think(self, task, context):
        if self.brain is None:
            raise RuntimeError(
                f'{self.name}: no Brain instance attached. Pass brain= '
                'when constructing the agent.')
        # task is expected to be a query string (or dict with 'query')
        query = task if isinstance(task, str) else task.get('query', '')
        candidates = self._retrieve(query)
        return self._format(query, candidates, context)

    def _retrieve(self, query: str):
        """Default retrieval: Brain.curator.retrieve(top_k, books_filter)."""
        return self.brain.curator.retrieve(
            query, limit=self.top_k, books=self.books_filter)

    def _format(self, query: str, candidates: list, context: dict):
        """Default: return retrieval results as a structured dict.

        Override to add naturalization (LLM rewriting) etc.
        """
        return {
            'query': query,
            'candidates': [
                {
                    'book': c.get('book', '?'),
                    'key': c.get('key', '?'),
                    'score': float(c.get('score', 0)),
                    'entry': c.get('entry'),
                }
                for c in candidates
            ],
        }
