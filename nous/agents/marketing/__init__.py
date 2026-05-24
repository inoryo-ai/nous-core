"""Marketing agents — 9-agent marketing team running on NOUS Runtime.

Reference implementation of Katsumata's AI clone marketing organization:
Commander + 8 specialists (Persona, Pitch, Content, Ad, Line, LP, Retention, Referral).
"""
from .prompts import PROMPTS
from .specialists import (
    PersonaAnalyzerAgent,
    PitchDesignerAgent,
    ContentCreatorAgent,
    AdManagerAgent,
    LineNurturerAgent,
    LpOptimizerAgent,
    RetentionEnhancerAgent,
    ReferralAmplifierAgent,
)
from .commander import build_marketing_runtime, run_full_pipeline, DEFAULT_PIPELINE

__all__ = [
    'PROMPTS',
    'PersonaAnalyzerAgent',
    'PitchDesignerAgent',
    'ContentCreatorAgent',
    'AdManagerAgent',
    'LineNurturerAgent',
    'LpOptimizerAgent',
    'RetentionEnhancerAgent',
    'ReferralAmplifierAgent',
    'build_marketing_runtime',
    'run_full_pipeline',
    'DEFAULT_PIPELINE',
]
