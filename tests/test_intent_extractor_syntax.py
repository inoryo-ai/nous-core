"""Phase A.1 — Syntax layer tests."""

import pytest

from nous.language.intent_extractor.morphology import Morphology
from nous.language.intent_extractor.syntax import Syntax


@pytest.fixture(scope="module")
def morph() -> Morphology:
    return Morphology()


@pytest.fixture(scope="module")
def syn() -> Syntax:
    return Syntax()


def _parse(morph: Morphology, syn: Syntax, text: str):
    return syn.parse(morph.tokenize(text))


# ---- 述語同定 ----

def test_predicate_verb_at_end(morph, syn) -> None:
    out = _parse(morph, syn, "猫が走る")
    assert out.predicate is not None
    assert out.predicate.lemma == "走る"


def test_predicate_with_polite_aux(morph, syn) -> None:
    out = _parse(morph, syn, "猫が走ります")
    assert out.predicate is not None
    # 動詞「走る」が述語、または「ます」でも可
    assert out.predicate.lemma in ("走る", "ます")


def test_predicate_empty_input(morph, syn) -> None:
    out = syn.parse([])
    assert out.predicate is None
    assert out.confidence == 0.0


# ---- sentence type ----

def test_interrogative_with_ka(morph, syn) -> None:
    out = _parse(morph, syn, "これは何ですか")
    assert out.sentence_type == "interrogative"


def test_interrogative_with_question_mark(morph, syn) -> None:
    out = _parse(morph, syn, "本当?")
    assert out.sentence_type == "interrogative"


def test_interrogative_wh_word(morph, syn) -> None:
    out = _parse(morph, syn, "GA4の使い方を教えて")
    # 「教えて」は依頼形 (imperative)、wh は無いので imperative または interrogative にならない
    assert out.sentence_type in ("imperative", "declarative")


def test_imperative_te_kudasai(morph, syn) -> None:
    out = _parse(morph, syn, "教えてください")
    assert out.sentence_type == "imperative"


def test_declarative_default(morph, syn) -> None:
    out = _parse(morph, syn, "猫が走る")
    assert out.sentence_type == "declarative"


# ---- arguments (格役割) ----

def test_argument_subject_ga(morph, syn) -> None:
    out = _parse(morph, syn, "猫が走る")
    roles = [a.role for a in out.arguments]
    assert "ga" in roles


def test_argument_object_wo(morph, syn) -> None:
    out = _parse(morph, syn, "本を読む")
    roles = [a.role for a in out.arguments]
    assert "wo" in roles


def test_argument_topic_ha(morph, syn) -> None:
    out = _parse(morph, syn, "猫は走る")
    roles = [a.role for a in out.arguments]
    assert "topic" in roles


def test_argument_multiple_cases(morph, syn) -> None:
    out = _parse(morph, syn, "GA4の使い方を教えて")
    roles = [a.role for a in out.arguments]
    # 「を」がある
    assert "wo" in roles


def test_argument_head_text_contains_term(morph, syn) -> None:
    out = _parse(morph, syn, "GA4の使い方を教えて")
    wo_args = [a for a in out.arguments if a.role == "wo"]
    assert wo_args
    # head_text に「使い方」が含まれる
    assert "使い方" in wo_args[0].text


# ---- ellipsis / defaults ----

def test_ellipsis_fills_ga_for_oshieru(morph, syn) -> None:
    out = _parse(morph, syn, "GA4の使い方を教えて")
    roles = {a.role for a in out.arguments}
    # 「教える」の defaults: ga="speaker_or_system", ni="speaker"
    assert "ga" in roles or "ni" in roles


def test_ellipsis_no_overwrite(morph, syn) -> None:
    out = _parse(morph, syn, "私がGA4の使い方を教える")
    ga_args = [a for a in out.arguments if a.role == "ga"]
    # ga が既にある → defaults で上書きされない
    assert len(ga_args) == 1
    assert ga_args[0].text != "speaker_or_system"


# ---- confidence ----

def test_confidence_scales_with_completeness(morph, syn) -> None:
    full = _parse(morph, syn, "GA4の使い方を教えてください")
    bare = _parse(morph, syn, "教える")
    assert full.confidence > bare.confidence
    assert 0.0 < full.confidence <= 1.0
