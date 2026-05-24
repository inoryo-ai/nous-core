"""StudentAssistantAgent — wraps a Brain + LLM into a student-facing agent.

Generic learning-platform assistant: takes a student question, extracts intent
via an LLM, retrieves relevant lessons via NOUS Brain, and naturalizes the
response via the LLM again.

Example instantiation:
    agent = StudentAssistantAgent(
        brain=Brain(loaded with course books),
        intent_prompt=COURSE_INTENT_PROMPT,
        naturalize_prompt=COURSE_NATURALIZE_PROMPT,
        url_domain='example.com',
    )
"""
from __future__ import annotations

import json
import re
from typing import Any

from .llm import LLMAgent, _estimate_cost_jpy
from ..runtime.agent import AgentResult


URL_PATTERN = re.compile(r'https?://[^\s\)\]\u3000、。「」\'"`]+')


def sanitize_urls(text: str, allowed_domain: str = '') -> tuple[str, int]:
    """Remove URLs whose host doesn't match allowed_domain. Returns (text, n_removed).

    If allowed_domain is empty, no URLs are removed.
    """
    if not allowed_domain:
        return text, 0
    removed = 0

    def repl(m):
        nonlocal removed
        url = m.group(0)
        if allowed_domain in url:
            return url
        removed += 1
        return '[URL省略]'
    return URL_PATTERN.sub(repl, text), removed


class StudentAssistantAgent(LLMAgent):
    """Two-stage agent: intent extraction → retrieval → naturalization.

    Default prompts are placeholders; pass intent_prompt and naturalize_prompt
    for the specific domain.
    """
    NAME = 'student_assistant'

    DEFAULT_INTENT_PROMPT = """\
あなたは学習プラットフォームのAIアシスタントです。
受講生の質問の意図を抽出し、JSONで返してください。

スキーマ:
{
  "intent": "ask_lesson | ask_general | chat",
  "category_hint": "...",
  "search_terms": "..."
}
"""

    DEFAULT_NATURALIZE_PROMPT = """\
あなたは優しい学習サポートAIです。
NOUS検索結果を、受講生に向けて2-4文の自然な日本語で返してください。
URL省略禁止、敬語ベース。
"""

    def __init__(self, *,
                 brain,
                 name: str | None = None,
                 description: str = '',
                 intent_prompt: str | None = None,
                 naturalize_prompt: str | None = None,
                 url_domain: str = '',
                 books_by_intent: dict | None = None,
                 model: str | None = None,
                 client=None,
                 api_key: str | None = None):
        # We override _think entirely so role_prompt is unused, but parent ctor
        # still requires a value.
        super().__init__(
            name=name, description=description,
            role_prompt=intent_prompt or self.DEFAULT_INTENT_PROMPT,
            model=model, client=client, api_key=api_key, json_mode=False,
        )
        self.brain = brain
        self.intent_prompt = intent_prompt or self.DEFAULT_INTENT_PROMPT
        self.naturalize_prompt = naturalize_prompt or self.DEFAULT_NATURALIZE_PROMPT
        self.url_domain = url_domain
        self.books_by_intent = books_by_intent or {}

    def _think(self, task, context):
        user_text = task if isinstance(task, str) else task.get('text', '')
        if not user_text:
            return {'text': '', 'intent': 'chat', 'used_fallback': True}

        # Stage 1: intent extraction
        intent_data, cost1 = self._extract_intent(user_text)
        intent = intent_data.get('intent', 'chat')
        category_hint = intent_data.get('category_hint', '').strip()
        search_terms = intent_data.get('search_terms', '').strip() or user_text
        query = (f'{category_hint} {search_terms}'.strip()
                 if category_hint and category_hint not in search_terms
                 else search_terms)
        target_books = self.books_by_intent.get(intent)

        # Stage 2: retrieval
        candidates = self.brain.curator.retrieve(
            query, limit=3, books=target_books)
        used_fallback = len(candidates) == 0

        # Stage 3: naturalize
        if used_fallback:
            final_text = ('申し訳ありません、こちらの内容は現在の知識にございませんでした。'
                          '運営にお繋ぎしましょうか？')
            cost2 = 0.0
        else:
            final_text, cost2 = self._naturalize(
                user_text, candidates, intent_data)

        total_cost = cost1 + cost2
        context['_cost_jpy'] = total_cost

        top = candidates[0] if candidates else None
        return {
            'text': final_text,
            'intent': intent,
            'source_book': top['book'] if top else '',
            'source_key': top['key'] if top else '',
            'confidence': top['score'] if top else 0.0,
            'used_fallback': used_fallback,
            'nano_intent': intent_data,
            'cost_jpy': total_cost,
        }

    def _extract_intent(self, user_text: str) -> tuple[dict, float]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.intent_prompt},
                {'role': 'user', 'content': user_text},
            ],
            max_tokens=200,
            temperature=0.1,
            response_format={'type': 'json_object'},
        )
        content = resp.choices[0].message.content
        cost = _estimate_cost_jpy(resp.usage)
        try:
            return json.loads(content), cost
        except json.JSONDecodeError:
            return {'intent': 'chat', 'category_hint': '',
                    'search_terms': user_text}, cost

    def _naturalize(self, user_text: str, candidates: list,
                    intent_data: dict) -> tuple[str, float]:
        def find_url(entry):
            if not isinstance(entry, dict):
                return None
            for key in ('受講ページ', '参照URL', '動画URL'):
                v = entry.get(key)
                if isinstance(v, str) and v.startswith('http'):
                    return v
            return None

        candidate_text = ''
        for i, c in enumerate(candidates[:3], 1):
            entry = c['entry']
            url_present = find_url(entry)
            entry_str = json.dumps(entry, ensure_ascii=False, indent=2) \
                if isinstance(entry, dict) else str(entry)
            url_note = (f'\nこの候補のURL: {url_present}'
                        if url_present
                        else '\nこの候補にURLは含まれていません。'
                             '応答にURLを書かないでください。')
            candidate_text += (f'\n【候補{i}】 (book={c["book"]}, key={c["key"]}, '
                                f'score={c["score"]:.2f}){url_note}\n{entry_str}\n')

        user_prompt = (
            f'受講生の質問: {user_text}\n'
            f'抽出した意図: {json.dumps(intent_data, ensure_ascii=False)}\n\n'
            f'NOUS検索結果（実在する候補・上位3つ）:{candidate_text}\n\n'
            f'これを自然に整形してください。複数候補は箇条書き、URL省略禁止。'
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': self.naturalize_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            max_tokens=600,
            temperature=0.4,
        )
        text = resp.choices[0].message.content
        text, removed = sanitize_urls(text, allowed_domain=self.url_domain)
        if removed:
            text += (f'\n[システム注: ハルシネーション防止のため'
                     f'外部ドメインのURL{removed}件を除去しました]')
        return text, _estimate_cost_jpy(resp.usage)
