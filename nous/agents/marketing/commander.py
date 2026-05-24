"""Marketing Commander — convenience builder for the marketing runtime.

Exposes ``build_marketing_runtime`` which constructs a NousRuntime with all
8 specialist agents pre-registered, ready to dispatch.

Usage:
    from nous.agents.marketing import build_marketing_runtime
    rt = build_marketing_runtime()
    results = rt.pipeline([
        ('PersonaAnalyzer', '30代女性副業希望'),
        ('PitchDesigner',   '前段の出力を踏まえ訴求3つ作成'),
        ('ContentCreator',  '前段の訴求でSNS投稿とLPコピー作成'),
        ...
    ])
"""
from __future__ import annotations

from ...runtime.coordinator import NousRuntime
from .specialists import ALL_SPECIALISTS


DEFAULT_PIPELINE = [
    'PersonaAnalyzer',
    'PitchDesigner',
    'ContentCreator',
    'AdManager',
    'LineNurturer',
    'LpOptimizer',
    'RetentionEnhancer',
    'ReferralAmplifier',
]


def build_marketing_runtime(*, hippocampus=None, msgbus=None,
                             llm_kwargs: dict | None = None) -> NousRuntime:
    """Build a NousRuntime with all 8 marketing specialists registered.

    llm_kwargs: passed to each LLMAgent (e.g. model, temperature, api_key).
    """
    rt = NousRuntime(hippocampus=hippocampus, msgbus=msgbus)
    llm_kwargs = llm_kwargs or {}
    for cls in ALL_SPECIALISTS:
        rt.register(cls(**llm_kwargs))
    return rt


def run_full_pipeline(rt: NousRuntime, seed_description: str,
                      stages: list[str] | None = None) -> dict:
    """Run all 8 stages with seed description as starting context.

    Returns dict with outputs by agent name and total cost.
    """
    stages = stages or list(DEFAULT_PIPELINE)
    outputs = {}
    ctx: dict = {'seed_description': seed_description}
    for i, name in enumerate(stages):
        if i == 0 and name == 'PersonaAnalyzer':
            task = f'次の人物像を深掘りしてペルソナを構築してください: {seed_description}'
        else:
            task = '前段までの結果を踏まえ、あなたの専門領域の出力を作ってください'
        result = rt.dispatch(name, task, context=dict(ctx))
        outputs[name] = result.output
        if result.ok:
            # Propagate output to context for downstream
            if name == 'PersonaAnalyzer':
                ctx['latest_persona'] = result.output
            elif name == 'PitchDesigner':
                ctx['latest_pitches'] = (result.output.get('pitches', [])
                                          if isinstance(result.output, dict)
                                          else [])
            elif name == 'ContentCreator':
                ctx['latest_contents'] = result.output
            ctx[f'output_{name}'] = result.output
    return {
        'outputs': outputs,
        'total_cost_jpy': rt.total_cost_jpy,
        'errors': [a for a in stages
                   if isinstance(outputs.get(a), dict)
                   and outputs.get(a, {}).get('_error')],
    }
