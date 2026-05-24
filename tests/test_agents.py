"""Tests for nous.agents — LLMAgent + marketing specialists.

These tests use a stub OpenAI client (no real API call) to verify the
agent wiring without requiring credentials or making expensive requests.
"""
import json
from unittest.mock import MagicMock

import pytest

from nous.runtime import NousRuntime
from nous.agents import LLMAgent
from nous.agents.marketing import build_marketing_runtime
from nous.agents.marketing.specialists import (
    PersonaAnalyzerAgent, PitchDesignerAgent, ContentCreatorAgent,
    AdManagerAgent, LineNurturerAgent, LpOptimizerAgent,
    RetentionEnhancerAgent, ReferralAmplifierAgent, ALL_SPECIALISTS,
)


class _StubClient:
    """Mimics openai.OpenAI just enough for LLMAgent.

    The completions.create() method returns whatever JSON is set as
    `next_payload`.
    """
    def __init__(self, payload: dict | str):
        self.next_payload = payload
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = self._create
        self._call_count = 0

    def _create(self, **kwargs):
        self._call_count += 1
        text = (json.dumps(self.next_payload, ensure_ascii=False)
                if isinstance(self.next_payload, dict)
                else str(self.next_payload))
        # Build a response object similar to OpenAI's
        msg = MagicMock()
        msg.content = text
        choice = MagicMock()
        choice.message = msg
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        return resp


class TestLLMAgent:
    def test_json_mode_parses(self):
        client = _StubClient({'result': 42})
        a = LLMAgent(name='t', client=client)
        r = a.execute('do something')
        assert r.ok
        assert r.output == {'result': 42}
        assert r.cost_jpy > 0

    def test_invalid_json_returns_error_dict(self):
        client = _StubClient('not json')
        a = LLMAgent(name='t', client=client)
        r = a.execute('do something')
        # invalid json should still complete; output contains _error
        assert r.ok  # _think doesn't raise
        assert isinstance(r.output, dict)
        assert '_error' in r.output

    def test_text_mode(self):
        client = _StubClient('plain text response')
        a = LLMAgent(name='t', client=client, json_mode=False)
        r = a.execute('hi')
        assert r.output == 'plain text response'


class TestSpecialists:
    @pytest.mark.parametrize('cls', ALL_SPECIALISTS)
    def test_specialist_constructible(self, cls):
        client = _StubClient({'placeholder': True})
        a = cls(client=client)
        assert a.role_prompt  # role prompt is set
        assert a.name == cls.NAME

    def test_persona_analyzer_runs(self):
        payload = {
            'name': '副業マインド30代女性',
            'demographics': {'age': '30s', 'gender': 'F'},
            'pain_points': ['時間がない'],
        }
        client = _StubClient(payload)
        a = PersonaAnalyzerAgent(client=client)
        r = a.execute('30代女性副業希望')
        assert r.ok
        assert r.output['name'] == '副業マインド30代女性'


class TestRuntimeIntegration:
    def test_build_marketing_runtime(self):
        # Override OPENAI_API_KEY via stub client for each agent
        rt = NousRuntime()
        for cls in ALL_SPECIALISTS:
            rt.register(cls(client=_StubClient({'ok': True})))
        names = rt.names()
        assert len(names) == 8
        assert 'PersonaAnalyzer' in names
        assert 'ContentCreator' in names

    def test_pipeline_chains_outputs(self):
        rt = NousRuntime()
        rt.register(PersonaAnalyzerAgent(
            client=_StubClient({'name': 'persona', 'pain_points': ['x']})))
        rt.register(PitchDesignerAgent(
            client=_StubClient({'pitches': [{'headline': 'h'}]})))
        results = rt.pipeline([
            ('PersonaAnalyzer', 'seed'),
            ('PitchDesigner', 'design pitches'),
        ])
        assert len(results) == 2
        assert results[0].ok
        assert results[1].ok
