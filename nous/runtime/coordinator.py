"""NousRuntime — orchestrator for heterogeneous agents.

Hosts agents, dispatches tasks, manages shared memory and messaging. Unlike
the substrate-specific coordinator, this is a generic platform layer that
works with any Agent subclass (LLM, knowledge-based, hybrid).
"""
from __future__ import annotations

from typing import Any

from .agent import Agent, AgentResult
from .hippocampus import Hippocampus
from .messaging import MessageBus


class NousRuntime:
    """Multi-agent platform runtime.

    Responsibilities:
      - Register agents by name
      - Dispatch tasks (single agent, sequential pipeline, or by name lookup)
      - Provide shared Hippocampus (optional) and MessageBus
      - Track cumulative cost and execution log

    Usage:
        rt = NousRuntime(hippocampus=hippo)
        rt.register(my_agent)
        result = rt.dispatch('my_agent', task='do something')
        # Or run pipeline of agents in sequence:
        results = rt.pipeline([
            ('persona_analyzer', 'analyze 30s woman'),
            ('content_creator', 'make ad copy'),
        ])
    """

    def __init__(self, *,
                 hippocampus: Hippocampus | None = None,
                 msgbus: MessageBus | None = None):
        self.hippocampus = hippocampus
        self.msgbus = msgbus or MessageBus()
        self._agents: dict[str, Agent] = {}
        self._cumulative_cost = 0.0
        self._results: list[AgentResult] = []

    def register(self, agent: Agent) -> None:
        """Register an agent. Replaces any existing agent with the same name."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def names(self) -> list[str]:
        return list(self._agents)

    def dispatch(self, name: str, task: Any,
                 context: dict | None = None) -> AgentResult:
        """Run a single agent by name."""
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f'agent {name!r} not registered')
        result = agent.execute(task, context=context or {})
        self._track(result)
        return result

    def pipeline(self, steps: list[tuple[str, Any]],
                 propagate_outputs: bool = True) -> list[AgentResult]:
        """Run a sequence of (agent_name, task) steps, optionally propagating
        prior outputs into context for downstream agents."""
        results: list[AgentResult] = []
        ctx: dict = {}
        for name, task in steps:
            r = self.dispatch(name, task, context=dict(ctx))
            results.append(r)
            if propagate_outputs and r.ok:
                ctx[f'output_{name}'] = r.output
                ctx['latest_output'] = r.output
        return results

    def _track(self, result: AgentResult) -> None:
        self._cumulative_cost += result.cost_jpy
        self._results.append(result)

    @property
    def total_cost_jpy(self) -> float:
        return self._cumulative_cost

    def health_all(self) -> dict:
        return {
            'n_agents': len(self._agents),
            'agents': [a.health() for a in self._agents.values()],
            'cumulative_cost_jpy': round(self._cumulative_cost, 4),
            'n_dispatches': len(self._results),
            'hippocampus': {
                'enabled': self.hippocampus is not None,
                'n_patterns': (self.hippocampus.n_patterns
                                if self.hippocampus else 0),
            },
        }

    def reset_log(self) -> None:
        self._cumulative_cost = 0.0
        self._results.clear()
