"""8 specialist agents subclassing LLMAgent with role-specific prompts."""
from __future__ import annotations

from ..llm import LLMAgent
from .prompts import PROMPTS


class PersonaAnalyzerAgent(LLMAgent):
    NAME = 'PersonaAnalyzer'
    ROLE_PROMPT = PROMPTS['PersonaAnalyzer']


class PitchDesignerAgent(LLMAgent):
    NAME = 'PitchDesigner'
    ROLE_PROMPT = PROMPTS['PitchDesigner']


class ContentCreatorAgent(LLMAgent):
    NAME = 'ContentCreator'
    ROLE_PROMPT = PROMPTS['ContentCreator']


class AdManagerAgent(LLMAgent):
    NAME = 'AdManager'
    ROLE_PROMPT = PROMPTS['AdManager']


class LineNurturerAgent(LLMAgent):
    NAME = 'LineNurturer'
    ROLE_PROMPT = PROMPTS['LineNurturer']


class LpOptimizerAgent(LLMAgent):
    NAME = 'LpOptimizer'
    ROLE_PROMPT = PROMPTS['LpOptimizer']


class RetentionEnhancerAgent(LLMAgent):
    NAME = 'RetentionEnhancer'
    ROLE_PROMPT = PROMPTS['RetentionEnhancer']


class ReferralAmplifierAgent(LLMAgent):
    NAME = 'ReferralAmplifier'
    ROLE_PROMPT = PROMPTS['ReferralAmplifier']


ALL_SPECIALISTS = [
    PersonaAnalyzerAgent,
    PitchDesignerAgent,
    ContentCreatorAgent,
    AdManagerAgent,
    LineNurturerAgent,
    LpOptimizerAgent,
    RetentionEnhancerAgent,
    ReferralAmplifierAgent,
]
