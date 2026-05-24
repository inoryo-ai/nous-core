"""Agent ABC — generic agent abstraction for NOUS Runtime.

An agent is anything that can take a task and produce a structured result.
Concrete agent types include:
  - LLMAgent (uses an LLM for thinking)
  - KnowledgeAgent (uses BookShelf retrieval)
  - HybridAgent (combines both)

The runtime treats all agents uniformly via the execute() interface.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Structured result returned by an agent's execute() call."""
    agent: str
    task: Any
    output: Any
    cost_jpy: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None
    meta: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


class Agent:
    """Generic agent base class.

    Subclasses must:
      - Set NAME class attribute (or pass `name` to __init__)
      - Implement _think(task, context) -> output

    The execute() wrapper handles logging, timing, and error capture so
    subclasses focus only on the task logic.
    """
    NAME: str = 'agent'

    def __init__(self, *, name: str | None = None,
                 description: str = ''):
        self.name = name or self.NAME
        self.description = description
        self.private_state: dict = {}

    def execute(self, task: Any,
                context: dict | None = None) -> AgentResult:
        """Run the agent on a task. Returns AgentResult with timing/error capture."""
        context = context or {}
        t0 = time.perf_counter()
        try:
            output = self._think(task, context)
            latency_ms = (time.perf_counter() - t0) * 1000
            return AgentResult(
                agent=self.name, task=task, output=output,
                latency_ms=latency_ms,
                cost_jpy=context.get('_cost_jpy', 0.0),
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            return AgentResult(
                agent=self.name, task=task, output=None,
                latency_ms=latency_ms,
                error=f'{type(e).__name__}: {e}',
            )

    def _think(self, task: Any, context: dict) -> Any:
        """Override: produce a structured output from the task and context."""
        raise NotImplementedError(
            f'{self.__class__.__name__} must implement _think()')

    def health(self) -> dict:
        return {
            'name': self.name,
            'class': self.__class__.__name__,
            'description': self.description,
        }

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name={self.name!r})'
