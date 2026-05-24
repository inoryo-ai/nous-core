"""LLMAgent — base class for LLM-driven agents.

Provides:
  - Role prompt management
  - Structured JSON output parsing
  - Cost tracking (gpt-4o-mini default)
  - Optional context propagation from prior agents

Requires `openai` package; raises ImportError on construction otherwise.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ..runtime.agent import Agent


# OpenAI gpt-4o-mini pricing (USD/1M tokens), USD→JPY at 150
INPUT_PER_1M_USD = 0.15
OUTPUT_PER_1M_USD = 0.60
USD_TO_JPY = 150.0


def _estimate_cost_jpy(usage) -> float:
    if not usage:
        return 0.0
    in_cost = (usage.prompt_tokens / 1_000_000) * INPUT_PER_1M_USD
    out_cost = (usage.completion_tokens / 1_000_000) * OUTPUT_PER_1M_USD
    return (in_cost + out_cost) * USD_TO_JPY


class LLMAgent(Agent):
    """Generic LLM-backed agent.

    Subclasses set ROLE_PROMPT (system prompt for the role) and override
    _build_user_prompt() if they need custom context formatting.
    """
    ROLE_PROMPT: str = 'You are a helpful AI assistant.'

    def __init__(self, *,
                 name: str | None = None,
                 description: str = '',
                 role_prompt: str | None = None,
                 model: str | None = None,
                 max_tokens: int = 800,
                 temperature: float = 0.4,
                 json_mode: bool = True,
                 api_key: str | None = None,
                 client=None):
        super().__init__(name=name, description=description)
        self.role_prompt = role_prompt or self.ROLE_PROMPT
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.json_mode = json_mode
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    'LLMAgent requires `openai` package. '
                    'Install with: pip install openai') from e
            api_key = api_key or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise RuntimeError(
                    'OPENAI_API_KEY not set and no client provided')
            client = OpenAI(api_key=api_key)
        self.client = client

    def _think(self, task, context):
        """Build prompt, call LLM, parse output."""
        user_prompt = self._build_user_prompt(task, context)
        kwargs = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': self.role_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }
        if self.json_mode:
            kwargs['response_format'] = {'type': 'json_object'}

        resp = self.client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ''
        cost = _estimate_cost_jpy(resp.usage)
        # Stash cost in context so execute() can attach to result
        context['_cost_jpy'] = cost

        if self.json_mode:
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                return {'_raw': text, '_error': str(e)}
        return text

    def _build_user_prompt(self, task, context: dict) -> str:
        """Override to customize prompt construction.

        Default: render task + relevant context keys (those not starting with `_`).
        """
        parts = [f'タスク: {task if isinstance(task, str) else json.dumps(task, ensure_ascii=False)}']
        for key, value in context.items():
            if key.startswith('_'):
                continue
            if isinstance(value, (dict, list)):
                parts.append(f'\n{key}:\n{json.dumps(value, ensure_ascii=False, indent=2)}')
            else:
                parts.append(f'\n{key}: {value}')
        return '\n\n'.join(parts)
