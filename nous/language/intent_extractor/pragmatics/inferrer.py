"""Phase A.1 — Pragmatics (語用層).

Responsibilities:
1. 発話機能 (speech_act) 分類: greeting/thanks/request/question/inquiry/...
2. intent 確定: (schema_id, speech_act, context) → 8 種類のうち 1 つ
3. category_hint 決定: token.features.category を優先順で集約
4. keywords / search_terms 抽出
5. 全層 confidence の集約

設計原則:
- speech_act は patterns.yaml のルール優先順で最初に match したもの
- intent は schema_id をベースに、空の場合のみ speech_act fallback
"""

from __future__ import annotations

from pathlib import Path

from ..types import ContextFrame, IntentResult, SemanticsOutput, Token

try:
    import yaml
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False


_DATA_DIR = Path(__file__).parent / "data"


class Pragmatics:
    def __init__(self,
                 speech_act_patterns_path: str | Path | None = None,
                 intent_routing_path: str | Path | None = None,
                 domain_context_path: str | Path | None = None) -> None:
        self._patterns_path = Path(speech_act_patterns_path) if speech_act_patterns_path else _DATA_DIR / "speech_act_patterns.yaml"
        self._routing_path = Path(intent_routing_path) if intent_routing_path else _DATA_DIR / "intent_routing.yaml"
        self._domain_path = Path(domain_context_path) if domain_context_path else _DATA_DIR / "domain_context.yaml"
        self._rules: list[dict] = []
        self._routes: dict[str, str] = {}
        self._fallback: list[dict] = []
        self._category_priority: list[str] = []
        self._load_data()

    def _load_data(self) -> None:
        if not _YAML_OK:
            return
        if self._patterns_path.exists():
            with self._patterns_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._rules = data.get("rules", []) or []
        if self._routing_path.exists():
            with self._routing_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for entry in data.get("routes", []) or []:
                sid = entry.get("schema_id")
                intent = entry.get("intent")
                if sid and intent:
                    self._routes[sid] = intent
            self._fallback = data.get("fallback", []) or []
        if self._domain_path.exists():
            with self._domain_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._category_priority = data.get("category_priority", []) or []

    # ---- public API ----

    def infer(self, semantics_out: SemanticsOutput,
              context: ContextFrame | None = None) -> IntentResult:
        ctx = context or ContextFrame()
        syntax_out = self._extract_syntax_from_semantics(semantics_out)

        speech_act = self._classify_speech_act(semantics_out, syntax_out)
        intent = self._route_intent(semantics_out.schema_id, speech_act)
        category_hint = self._pick_category_hint(syntax_out)
        keywords = self._extract_keywords(syntax_out)
        search_terms = self._build_search_terms(semantics_out, keywords)
        confidence = self._aggregate_confidence(syntax_out, semantics_out)

        return IntentResult(
            intent=intent,
            category_hint=category_hint,
            keywords=keywords,
            search_terms=search_terms,
            confidence=confidence,
            speech_act=speech_act,
            trace={
                "schema_id": semantics_out.schema_id,
                "filled": dict(semantics_out.filled_schema),
                "last_intent": ctx.last_intent,
                "domain": ctx.domain,
            },
        )

    # ---- speech act ----

    def _classify_speech_act(self, sem: SemanticsOutput,
                             syntax_out) -> str:
        concept_canons = {c.canonical for c in sem.concepts}
        lemmas = {t.lemma for t in (syntax_out.tokens if syntax_out else [])}
        surfaces = {t.surface for t in (syntax_out.tokens if syntax_out else [])}
        sentence_type = syntax_out.sentence_type if syntax_out else "declarative"
        predicate_cform = ""
        if syntax_out and syntax_out.predicate is not None:
            predicate_cform = syntax_out.predicate.features.get("cForm", "")

        for rule in self._rules:
            cond = rule.get("conditions", {}) or {}
            if cond.get("sentence_type") and cond["sentence_type"] != sentence_type:
                continue
            req_lemmas = cond.get("contains_lemma") or []
            if req_lemmas and not (set(req_lemmas) & lemmas):
                continue
            req_canon = cond.get("contains_canonical") or []
            if req_canon and not (set(req_canon) & concept_canons):
                continue
            req_surface = cond.get("contains_surface") or []
            if req_surface and not (set(req_surface) & surfaces):
                continue
            req_cform = cond.get("predicate_cform") or []
            if req_cform and predicate_cform not in req_cform:
                continue
            return rule.get("speech_act", "statement")
        return "statement"

    # ---- intent routing ----

    def _route_intent(self, schema_id: str, speech_act: str) -> str:
        if schema_id and schema_id in self._routes:
            return self._routes[schema_id]
        # fallback by speech_act
        for entry in self._fallback:
            target = entry.get("when_speech_act")
            if target == speech_act or target == "*":
                return entry.get("intent", "ask_general")
        return "ask_general"

    # ---- category hint ----

    def _pick_category_hint(self, syntax_out) -> str:
        if syntax_out is None:
            return ""
        present: set[str] = set()
        for tok in syntax_out.tokens:
            cat = tok.features.get("category")
            if cat:
                present.add(cat)
        for cat in self._category_priority:
            if cat in present:
                return cat
        return next(iter(present), "")

    # ---- keywords / search terms ----

    def _extract_keywords(self, syntax_out) -> list[str]:
        if syntax_out is None:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for tok in syntax_out.tokens:
            if tok.pos in {"noun", "pron", "verb", "adj"} \
                    and tok.surface not in seen \
                    and len(tok.surface) >= 1:
                seen.add(tok.surface)
                # 補助動詞は除外
                pos2 = tok.features.get("pos2", "")
                if pos2 in {"非自立可能", "形式名詞"}:
                    continue
                out.append(tok.surface)
        return out

    def _build_search_terms(self, sem: SemanticsOutput,
                            keywords: list[str]) -> str:
        # filled_schema の topic を優先、なければ keywords を連結
        topic = sem.filled_schema.get("topic")
        if topic:
            return str(topic) + (" " + " ".join(k for k in keywords if k != topic) if keywords else "")
        return " ".join(keywords)

    # ---- confidence aggregation ----

    def _aggregate_confidence(self, syntax_out, sem: SemanticsOutput) -> float:
        if syntax_out is None or not syntax_out.tokens:
            return 0.0
        # 各層の信頼度の min を取りつつ、底上げ
        syn_conf = max(0.0, syntax_out.confidence)
        sem_conf = max(0.0, sem.confidence)
        # schema 確定なら底上げ
        boost = 0.0
        if sem.schema_id:
            boost += 0.1
        agg = min(syn_conf, sem_conf) + boost
        return round(min(1.0, agg), 4)

    # ---- helpers ----

    def _extract_syntax_from_semantics(self, sem: SemanticsOutput):
        """SemanticsOutput には syntax_out 直参照がないので、IntentExtractor 側で
        補完する。M5 単体テスト用には None を許容する。"""
        # mapper.py は syntax_out を直接保持しないため、pipeline.py 側で
        # IntentResult.syntax_out にセットされる。ここでは隠し属性経由でアクセス。
        return getattr(sem, "_syntax_ref", None)
