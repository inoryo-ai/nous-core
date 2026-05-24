"""Tests for Brain — the top-level public API."""

import json
import pytest

from nous import Brain


@pytest.fixture
def manual_path(tmp_path):
    path = tmp_path / "manual.json"
    data = {
        "_meta": {"title": "社員規約"},
        "有給休暇": {
            "日数": "年10日（6ヶ月経過後）",
            "申請方法": "上長承認→人事システム",
        },
        "交通費": {
            "上限": "月3万円",
            "申請方法": "清算書提出",
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_brain_init_empty():
    brain = Brain()
    assert brain.books() == []
    assert brain.summary()["fact_count"] == 0


def test_brain_load_book(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    assert "manual" in brain.books()


def test_ask_returns_relevant_answer(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    r = brain.ask("有給休暇は何日ですか？")
    assert "年10日" in r.text
    assert r.source_book == "manual"
    assert r.source_key == "有給休暇"
    assert r.used_fallback is False


def test_ask_unknown_returns_fallback(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    r = brain.ask("xyz無関係のこと")
    assert r.used_fallback is True
    assert "登録された知識にありません" in r.text


def test_ask_returns_response_with_intent(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    r = brain.ask("有給は何日？")
    assert r.intent == "ask"


def test_ask_returns_trace(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    r = brain.ask("有給休暇の日数は？")
    trace = r.trace()
    assert trace["source_book"] == "manual"
    assert trace["source_key"] == "有給休暇"
    assert 0.0 <= trace["confidence"] <= 1.0


def test_chat_preserves_context(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    r1 = brain.chat("有給休暇について教えて")
    assert r1.source_key == "有給休暇"
    r2 = brain.chat("それの申請方法は？")
    assert r2.source_key == "有給休暇"


def test_clear_conversation(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    brain.chat("有給休暇について")
    brain.clear_conversation()
    assert brain.summary()["dialogue_turns"] == 0


def test_teach_adds_fact():
    brain = Brain()
    brain.teach("会社", "住所", "千葉県")
    assert brain.ks.access("会社", "住所") == "千葉県"


def test_learn_pattern_biases_parse():
    brain = Brain()
    brain.learn_pattern("今月の売上", "solve", target="売上")
    parsed = brain.language.parse("今月の売上")
    assert parsed["intent"] == "solve"


def test_summary_shape(manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)
    brain.ask("有給は？")
    s = brain.summary()
    assert s["book_count"] == 1
    assert s["dialogue_turns"] == 1
    assert "manual" in s["books"]


def test_multiple_books(tmp_path, manual_path):
    brain = Brain()
    brain.load_book("manual", manual_path)

    faq_path = tmp_path / "faq.json"
    faq_data = {"Q1": {"question": "問い合わせ窓口は？", "answer": "support@example.com"}}
    faq_path.write_text(json.dumps(faq_data, ensure_ascii=False), encoding="utf-8")
    brain.load_book("faq", str(faq_path))

    r = brain.ask("問い合わせ窓口")
    assert r.source_book == "faq"


def test_book_filter(manual_path, tmp_path):
    brain = Brain()
    brain.load_book("manual", manual_path)

    faq_path = tmp_path / "faq.json"
    faq_data = {"Q_有給": {"answer": "FAQ記載の有給情報"}}
    faq_path.write_text(json.dumps(faq_data, ensure_ascii=False), encoding="utf-8")
    brain.load_book("faq", str(faq_path))

    r = brain.ask("有給について", books=["faq"])
    assert r.source_book == "faq"
