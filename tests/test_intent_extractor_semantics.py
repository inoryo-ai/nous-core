"""Phase A.1 — Semantics layer tests."""

import pytest

from nous.language.intent_extractor.morphology import Morphology
from nous.language.intent_extractor.semantics import Semantics
from nous.language.intent_extractor.syntax import Syntax


@pytest.fixture(scope="module")
def morph() -> Morphology:
    return Morphology()


@pytest.fixture(scope="module")
def syn() -> Syntax:
    return Syntax()


@pytest.fixture(scope="module")
def sem() -> Semantics:
    return Semantics()


def _run(morph, syn, sem, text):
    tokens = morph.tokenize(text)
    syn_out = syn.parse(tokens)
    return sem.map(syn_out)


# ---- concept extraction ----

def test_concept_oshieru_to_kyoji(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "教えてください")
    canons = [c.canonical for c in out.concepts]
    assert "教示要求" in canons


def test_concept_term_passthrough(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "GA4の使い方")
    canons = [c.canonical for c in out.concepts]
    assert "GA4" in canons
    assert "操作方法" in canons


def test_concept_synonyms_collapsed(morph, syn, sem) -> None:
    a = _run(morph, syn, sem, "退会したい")
    b = _run(morph, syn, sem, "解約したい")
    canons_a = {c.canonical for c in a.concepts}
    canons_b = {c.canonical for c in b.concepts}
    assert "退会" in canons_a
    assert "退会" in canons_b


# ---- relations ----

def test_relation_of(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "GA4の使い方")
    assert out.relations
    rel = out.relations[0]
    assert rel.kind == "of"
    assert rel.src is not None and rel.src.surface == "GA4"


# ---- schema selection ----

def test_schema_ask_lesson(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "GA4の使い方を教えてください")
    assert out.schema_id == "ask_lesson"
    assert out.filled_schema.get("topic", "").find("使い方") != -1 \
           or out.filled_schema.get("topic", "").find("GA4") != -1


def test_schema_withdraw(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "退会したいです")
    assert out.schema_id == "withdraw"


def test_schema_chat_greeting(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "こんにちは")
    assert out.schema_id == "chat"


def test_schema_chat_thanks(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "ありがとうございます")
    assert out.schema_id == "chat"


def test_schema_roadmap(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "ロードマップを教えて")
    assert out.schema_id == "ask_roadmap"


def test_schema_inquiry(morph, syn, sem) -> None:
    out = _run(morph, syn, sem, "問い合わせしたい")
    assert out.schema_id == "inquiry"


# ---- confidence ----

def test_confidence_higher_with_schema(morph, syn, sem) -> None:
    full = _run(morph, syn, sem, "GA4の使い方を教えてください")
    sparse = _run(morph, syn, sem, "あいうえお")
    assert full.confidence > sparse.confidence
    assert 0.0 <= sparse.confidence
    assert full.confidence <= 1.0


def test_confidence_empty(morph, syn, sem) -> None:
    out = sem.map(syn.parse([]))
    assert out.confidence == 0.0
