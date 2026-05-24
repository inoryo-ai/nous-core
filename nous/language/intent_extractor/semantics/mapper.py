"""Phase A.1 — Semantics (意味層).

Responsibilities:
1. 概念マッピング: token surface/lemma → canonical concept (クラスタ保存)
2. 関係抽出: 「の」助詞による所有/属性関係 (動的ゲート)
3. スキーマ呼び出し: 8 intent それぞれの schema slot 充足
4. 多義語の並列候補 (冗長): 複数 schema に同時にスコアを付ける
"""

from __future__ import annotations

from pathlib import Path

from ..types import Concept, Relation, SemanticsOutput, SyntaxOutput, Token

try:
    import yaml
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False


_DATA_DIR = Path(__file__).parent / "data"
_SCHEMA_DIR = _DATA_DIR / "schemas"


class Semantics:
    def __init__(self,
                 concepts_path: str | Path | None = None,
                 schemas_dir: str | Path | None = None,
                 relations_path: str | Path | None = None) -> None:
        self._concepts_path = Path(concepts_path) if concepts_path else _DATA_DIR / "concepts.yaml"
        self._schemas_dir = Path(schemas_dir) if schemas_dir else _SCHEMA_DIR
        self._relations_path = Path(relations_path) if relations_path else _DATA_DIR / "relations.yaml"
        # surface/lemma → (canonical, category)
        self._concept_lookup: dict[str, tuple[str, str]] = {}
        # schema_id → schema dict
        self._schemas: dict[str, dict] = {}
        # no relations rules
        self._no_rules: list[dict] = []
        self._load_data()

    def _load_data(self) -> None:
        if not _YAML_OK:
            return
        if self._concepts_path.exists():
            with self._concepts_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for entry in data.get("concepts", []):
                canonical = entry.get("canonical")
                if not canonical:
                    continue
                category = entry.get("category", "")
                for s in entry.get("surfaces", []):
                    if s:
                        self._concept_lookup[s] = (canonical, category)
        if self._schemas_dir.exists():
            for path in sorted(self._schemas_dir.glob("*.yaml")):
                with path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                sid = data.get("schema_id") or path.stem
                self._schemas[sid] = data
        if self._relations_path.exists():
            with self._relations_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._no_rules = data.get("no_relations", []) or []

    # ---- public API ----

    def map(self, syntax_out: SyntaxOutput) -> SemanticsOutput:
        if not syntax_out.tokens:
            return SemanticsOutput(confidence=0.0)
        concepts = self._extract_concepts(syntax_out.tokens)
        relations = self._extract_no_relations(syntax_out.tokens, concepts)
        schema_id, filled, schema_score = self._select_schema(syntax_out, concepts)
        confidence = self._compute_confidence(syntax_out, concepts, schema_id, schema_score)
        return SemanticsOutput(
            concepts=concepts,
            relations=relations,
            filled_schema=filled,
            schema_id=schema_id,
            confidence=confidence,
        )

    # ---- concept extraction ----

    def _extract_concepts(self, tokens: list[Token]) -> list[Concept]:
        """token → concept マッピング。否定された動詞 (negated=True) は社交系
        concept (了承等) を抑制する。"""
        out: list[Concept] = []
        for tok in tokens:
            negated = tok.features.get("negated", False)
            # 1. surface
            if tok.surface in self._concept_lookup:
                canon, cat = self._concept_lookup[tok.surface]
                if negated and cat == "social":
                    continue
                out.append(Concept(surface=tok.surface, canonical=canon, category=cat))
                continue
            # 2. lemma
            if tok.lemma in self._concept_lookup:
                canon, cat = self._concept_lookup[tok.lemma]
                if negated and cat == "social":
                    continue
                out.append(Concept(surface=tok.surface, canonical=canon, category=cat))
                continue
            # 3. 専門用語 (domain_terms) → そのまま canonical=surface, category=term category
            if tok.features.get("term_source"):
                out.append(Concept(
                    surface=tok.surface,
                    canonical=tok.lemma or tok.surface,
                    category=tok.features.get("category", ""),
                ))
        return out

    # ---- relations ----

    def _extract_no_relations(self, tokens: list[Token],
                              concepts: list[Concept]) -> list[Relation]:
        if not concepts:
            return []
        # token surface → concept index
        surf_to_concept = {c.surface: c for c in concepts}
        out: list[Relation] = []
        for i in range(len(tokens) - 2):
            tok = tokens[i]
            nxt = tokens[i + 1]
            nxt2 = tokens[i + 2]
            if nxt.surface == "の" and nxt.pos == "particle" \
                    and (nxt.function == "adnominal" or nxt.features.get("role") == "no"):
                left = surf_to_concept.get(tok.surface)
                right = surf_to_concept.get(nxt2.surface)
                if left or right:
                    out.append(Relation(kind="of", src=left, dst=right))
        return out

    # ---- schema selection ----

    def _select_schema(self, syntax_out: SyntaxOutput,
                       concepts: list[Concept]) -> tuple[str, dict, float]:
        """全 schema を (priority, score) で比較して最も高いものを採用。

        priority: schema の優先度 (action/social > meta > info > fallback)。
        score:    must_have + boost の重み合計 (must_have ヒット必須)。
        """
        if not self._schemas:
            return "", {}, 0.0
        concept_set = {c.canonical for c in concepts}
        best_id = ""
        best_key: tuple[int, float] = (-1, 0.0)
        best_score = 0.0
        best_filled: dict = {}
        for sid, schema in self._schemas.items():
            score = self._score_schema(schema, concept_set, syntax_out)
            if score <= 0.0:
                continue
            priority = int(schema.get("priority", 50))
            key = (priority, score)
            if key <= best_key:
                continue
            best_id = sid
            best_key = key
            best_score = score
            best_filled = self._fill_slots(schema, syntax_out, concepts)
        return best_id, best_filled, best_score

    def _score_schema(self, schema: dict, concept_set: set,
                      syntax_out: SyntaxOutput) -> float:
        """must_have があれば必須充足を確認、無ければ boost のみで判定。"""
        must = set((schema.get("must_have", {}) or {}).get("concepts", []) or [])
        if must and not (must & concept_set):
            return 0.0
        boost = set((schema.get("boost", {}) or {}).get("concepts", []) or [])
        # 旧 indicators との後方互換
        indicators = set((schema.get("indicators", {}) or {}).get("concepts", []) or [])
        boost |= indicators
        score = 0.0
        if must:
            score += 0.6 + 0.1 * (len(must & concept_set) - 1)
        boost_hit = len(boost & concept_set)
        if boost_hit:
            score += min(0.3, 0.1 * boost_hit)
        return score

    def _fill_slots(self, schema: dict, syntax_out: SyntaxOutput,
                    concepts: list[Concept]) -> dict:
        filled: dict = {}
        slots = schema.get("slots", {}) or {}
        for name, spec in slots.items():
            if not isinstance(spec, dict):
                continue
            source = spec.get("source", "")
            accept_cats = set(spec.get("accept_categories", []) or [])
            value = None
            # role-based source: wo|topic|no
            if source:
                role_options = source.split("|")
                for arg in syntax_out.arguments:
                    if arg.role in role_options and arg.text \
                            and not (arg.text in {"speaker_or_system", "speaker"}):
                        if accept_cats:
                            # concept side で category 一致を確認
                            cat = self._category_of(arg.text, concepts)
                            if cat in accept_cats or not cat:
                                value = arg.text
                                break
                        else:
                            value = arg.text
                            break
            # concept-based source
            if value is None and source == "concept":
                accept_concepts = set(spec.get("accept_concepts", []) or [])
                for c in concepts:
                    if c.canonical in accept_concepts:
                        value = c.canonical
                        break
            if value is not None:
                filled[name] = value
        return filled

    def _category_of(self, surface: str, concepts: list[Concept]) -> str:
        for c in concepts:
            if c.surface == surface:
                return c.category
        return ""

    # ---- confidence ----

    def _compute_confidence(self, syntax_out: SyntaxOutput,
                            concepts: list[Concept],
                            schema_id: str, schema_score: float) -> float:
        if not syntax_out.tokens:
            return 0.0
        score = 0.3
        if concepts:
            score += min(0.3, 0.1 * len(concepts))
        if schema_id:
            score += min(0.4, schema_score)
        return round(min(1.0, score), 4)
