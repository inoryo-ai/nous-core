"""Phase A.1 — pipeline orchestrator.

Connects 5 layers: phonology → morphology → syntax → semantics → pragmatics.
M1.1 では phonology のみ実体実装、他 4 層はパススルー。
"""

from __future__ import annotations

import time

from .morphology import Morphology
from .phonology import Phonology
from .pragmatics import Pragmatics
from .semantics import Semantics
from .syntax import Syntax
from .types import ContextFrame, IntentResult


class IntentExtractor:
    """End-to-end Japanese intent extractor (LLM-free)."""

    def __init__(self,
                 phonology: Phonology | None = None,
                 morphology: Morphology | None = None,
                 syntax: Syntax | None = None,
                 semantics: Semantics | None = None,
                 pragmatics: Pragmatics | None = None,
                 domain: str = "default") -> None:
        self.phonology = phonology or Phonology()
        self.morphology = morphology or Morphology()
        self.syntax = syntax or Syntax()
        self.semantics = semantics or Semantics()
        self.pragmatics = pragmatics or Pragmatics()
        self.domain = domain

    @classmethod
    def from_config(cls, domain: str = "default") -> "IntentExtractor":
        """Factory matching spec §3.1. Currently uses defaults; extend per-domain later."""
        return cls(domain=domain)

    def extract(self, text: str, context: ContextFrame | None = None) -> IntentResult:
        ctx = context or ContextFrame(domain=self.domain)
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        phon = self.phonology.normalize(text)
        timings["phonology_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        tokens = self.morphology.tokenize(phon.normalized)
        timings["morphology_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        syn = self.syntax.parse(tokens)
        timings["syntax_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        sem = self.semantics.map(syn)
        timings["semantics_ms"] = (time.perf_counter() - t0) * 1000

        # 語用層が syntax_out を参照できるよう backref を渡す
        sem._syntax_ref = syn  # type: ignore[attr-defined]

        t0 = time.perf_counter()
        result = self.pragmatics.infer(sem, ctx)
        timings["pragmatics_ms"] = (time.perf_counter() - t0) * 1000

        result.phonology_out = phon
        result.morphology_out = tokens
        result.syntax_out = syn
        result.semantics_out = sem
        result.trace.setdefault("timings", {}).update(timings)
        result.trace["raw"] = text
        result.trace["normalized"] = phon.normalized
        return result
