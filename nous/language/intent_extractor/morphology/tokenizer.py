"""Phase A.1 — Morphology (形態層).

Responsibilities:
1. fugashi+UniDic で形態素解析
2. UniDic pos1 を簡略 POS に正規化 (noun/verb/adj/particle/aux/...)
3. domain_terms.yaml の専門用語を longest-match で先取り (クラスタ保存)
4. particles.yaml で助詞に機能ラベル (case_marker/topic_marker/sentence_final/...)
5. derivation.py で派生語ルール (例: 名詞+する → サ変動詞)
"""

from __future__ import annotations

from pathlib import Path

from ..types import Token

try:
    import yaml
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False

try:
    import fugashi  # type: ignore
    _FUGASHI_OK = True
except ImportError:  # pragma: no cover
    _FUGASHI_OK = False


_DATA_DIR = Path(__file__).parent / "data"


# UniDic pos1 → simplified POS
_POS1_MAP = {
    "名詞": "noun",
    "代名詞": "pron",
    "動詞": "verb",
    "形容詞": "adj",
    "形状詞": "adj",      # ナ形容詞・形容動詞
    "副詞": "adv",
    "連体詞": "det",
    "接続詞": "conj",
    "感動詞": "interj",
    "助詞": "particle",
    "助動詞": "aux",
    "接頭辞": "prefix",
    "接尾辞": "suffix",
    "記号": "sym",
    "補助記号": "punct",
    "空白": "space",
}


def _simplify_pos(pos1: str) -> str:
    return _POS1_MAP.get(pos1, "other")


class _Term:
    __slots__ = ("surface", "lemma", "pos", "category")

    def __init__(self, surface: str, lemma: str, pos: str, category: str) -> None:
        self.surface = surface
        self.lemma = lemma
        self.pos = pos
        self.category = category


class Morphology:
    """形態層: fugashi + 専門用語辞書 + 助詞機能注釈。"""

    def __init__(self,
                 terms_path: str | Path | None = None,
                 particles_path: str | Path | None = None) -> None:
        self._terms_path = Path(terms_path) if terms_path else _DATA_DIR / "domain_terms.yaml"
        self._particles_path = Path(particles_path) if particles_path else _DATA_DIR / "particles.yaml"
        self._terms: dict[str, _Term] = {}
        self._term_keys_sorted: list[str] = []
        self._particles: dict[str, dict] = {}
        self._tagger: object | None = None
        self._load_data()

    def _load_data(self) -> None:
        if not _YAML_OK:
            return
        if self._terms_path.exists():
            with self._terms_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for entry in data.get("terms", []):
                surface = entry.get("surface")
                if not surface:
                    continue
                term = _Term(
                    surface=surface,
                    lemma=entry.get("lemma") or surface,
                    pos=entry.get("pos", "noun"),
                    category=entry.get("category", "general"),
                )
                self._terms[surface] = term
                for alias in entry.get("aliases", []):
                    if alias and alias not in self._terms:
                        self._terms[alias] = term
            # 長い表記優先 (longest match)
            self._term_keys_sorted = sorted(self._terms.keys(), key=len, reverse=True)
        if self._particles_path.exists():
            with self._particles_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._particles = data.get("particles", {}) or {}

    def _ensure_tagger(self):
        if self._tagger is None:
            if not _FUGASHI_OK:
                raise RuntimeError(
                    "fugashi が import できません。`pip install fugashi unidic-lite` を実行してください。"
                )
            self._tagger = fugashi.Tagger()
        return self._tagger

    # ---- term matching ----

    def _scan_terms(self, text: str) -> list[tuple[int, int, _Term]]:
        """text 内で最長一致する term span を非重複で抽出。"""
        spans: list[tuple[int, int, _Term]] = []
        i = 0
        n = len(text)
        while i < n:
            matched = False
            for key in self._term_keys_sorted:
                klen = len(key)
                if klen == 0 or i + klen > n:
                    continue
                if text[i:i + klen] == key:
                    spans.append((i, i + klen, self._terms[key]))
                    i += klen
                    matched = True
                    break
            if not matched:
                i += 1
        return spans

    # ---- fugashi → Token ----

    def _fugashi_tokens(self, text: str) -> list[Token]:
        if not text:
            return []
        tagger = self._ensure_tagger()
        out: list[Token] = []
        for w in tagger(text):  # type: ignore[operator]
            feat = w.feature
            pos1 = feat.pos1 or ""
            pos2 = feat.pos2 or ""
            simple_pos = _simplify_pos(pos1)
            lemma = (getattr(feat, "lemma", None)
                     or getattr(feat, "orthBase", None)
                     or w.surface)
            tok = Token(
                surface=w.surface,
                lemma=lemma,
                pos=simple_pos,
                pos_detail=f"{pos1}/{pos2}",
                features={
                    "pos1": pos1,
                    "pos2": pos2,
                    "pos3": feat.pos3 or "",
                    "pos4": feat.pos4 or "",
                    "cType": getattr(feat, "cType", "") or "",
                    "cForm": getattr(feat, "cForm", "") or "",
                },
            )
            if simple_pos == "particle":
                self._annotate_particle(tok, pos2)
            out.append(tok)
        return out

    def _annotate_particle(self, tok: Token, pos2: str) -> None:
        entries = self._particles.get(tok.surface)
        if entries:
            # 同表層の複数機能を when_pos2 で曖昧解消 (上から優先)
            chosen = None
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                wanted = entry.get("when_pos2", "*")
                if wanted == "*" or wanted == pos2:
                    chosen = entry
                    break
            if chosen is not None:
                tok.function = chosen.get("function", "")
                role = chosen.get("role")
                if role:
                    tok.features["role"] = role
                if "notes" in chosen:
                    tok.features["notes"] = chosen["notes"]
                return
        # fallback: UniDic pos2 から推定
        if pos2 == "格助詞":
            tok.function = "case_marker"
        elif pos2 == "係助詞":
            tok.function = "topic_marker"
        elif pos2 == "終助詞":
            tok.function = "sentence_final"
        elif pos2 == "接続助詞":
            tok.function = "conjunctive"
        elif pos2 == "副助詞":
            tok.function = "focus"
        elif pos2 == "準体助詞":
            tok.function = "nominalizer"
        else:
            tok.function = "particle"

    # ---- public API ----

    def tokenize(self, normalized: str) -> list[Token]:
        if not normalized:
            return []
        if not self._term_keys_sorted:
            # 専門用語辞書なし → 全文 fugashi
            return self._apply_derivation(self._fugashi_tokens(normalized))

        spans = self._scan_terms(normalized)
        tokens: list[Token] = []
        cursor = 0
        for start, end, term in spans:
            if start > cursor:
                tokens.extend(self._fugashi_tokens(normalized[cursor:start]))
            tokens.append(Token(
                surface=normalized[start:end],
                lemma=term.lemma,
                pos=term.pos,
                pos_detail=f"term/{term.category}",
                features={"term_source": True, "category": term.category},
            ))
            cursor = end
        if cursor < len(normalized):
            tokens.extend(self._fugashi_tokens(normalized[cursor:]))
        return self._apply_derivation(tokens)

    # ---- derivation ----

    def _apply_derivation(self, tokens: list[Token]) -> list[Token]:
        """名詞 + する/した/して... → サ変動詞として 1 トークンに圧縮。"""
        if len(tokens) < 2:
            return tokens
        from .derivation import merge_sahen
        return merge_sahen(tokens)
