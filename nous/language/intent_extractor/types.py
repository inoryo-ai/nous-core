"""Phase A.1 — Data classes shared across 5 layers.

Each layer's output is a frozen dataclass so downstream layers can rely on
shape stability. `IntentResult` carries the full trace for debugging.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CharSegment:
    """A contiguous run of one character type."""
    text: str
    kind: str  # "hiragana" | "katakana" | "kanji" | "ascii" | "digit" | "symbol" | "other"
    start: int
    end: int


@dataclass
class PhonologyOutput:
    raw: str
    normalized: str
    char_segments: list[CharSegment] = field(default_factory=list)
    noise_removed: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class Token:
    surface: str
    lemma: str
    pos: str            # 品詞: noun, verb, particle, aux, adj, adv, conj, det, num, sym, other
    pos_detail: str = ""
    function: str = ""  # 機能: case_marker, topic_marker, sentence_final, etc.
    features: dict = field(default_factory=dict)


@dataclass
class Argument:
    role: str           # "ga" | "wo" | "ni" | "de" | "to" | "kara" | "made" | "topic" | ...
    head_token: Token | None = None
    text: str = ""


@dataclass
class SyntaxOutput:
    tokens: list[Token]
    predicate: Token | None
    arguments: list[Argument] = field(default_factory=list)
    sentence_type: str = "declarative"  # declarative | interrogative | imperative | exclamative
    confidence: float = 0.0


@dataclass
class Concept:
    surface: str
    canonical: str
    category: str = ""
    score: float = 1.0


@dataclass
class Relation:
    kind: str           # "has", "of", "by", "in", ...
    src: Concept | None
    dst: Concept | None


@dataclass
class SemanticsOutput:
    concepts: list[Concept] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    filled_schema: dict = field(default_factory=dict)
    schema_id: str = ""
    confidence: float = 0.0


@dataclass
class IntentResult:
    intent: str
    category_hint: str = ""
    keywords: list[str] = field(default_factory=list)
    search_terms: str = ""
    confidence: float = 0.0
    speech_act: str = ""           # question | request | command | thanks | greeting | statement
    trace: dict = field(default_factory=dict)

    # Upstream layer outputs preserved for audit / debugging
    phonology_out: PhonologyOutput | None = None
    morphology_out: list[Token] = field(default_factory=list)
    syntax_out: SyntaxOutput | None = None
    semantics_out: SemanticsOutput | None = None


@dataclass
class ContextFrame:
    """Dialogue-level context handed down from DialogueManager."""
    user_id: str = ""
    history: list[str] = field(default_factory=list)
    last_intent: str = ""
    domain: str = "default"
