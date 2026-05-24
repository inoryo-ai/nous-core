"""Tests for Brain plugin hooks: register / ordering / skipped callbacks."""

import json
import pytest
from nous import Brain


@pytest.fixture
def manual_path(tmp_path):
    path = tmp_path / "m.json"
    data = {
        "有給休暇": {"日数": "年10日", "申請方法": "上長承認"},
        "交通費": {"上限": "月3万円"},
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# ---------- register / unregister ----------

def test_register_returns_plugin():
    brain = Brain()
    class P:
        pass
    p = P()
    result = brain.register(p)
    assert result is p
    assert p in brain.plugins()


def test_register_multiple_preserves_order():
    brain = Brain()
    class P:
        pass
    a, b, c = P(), P(), P()
    brain.register(a)
    brain.register(b)
    brain.register(c)
    assert brain.plugins() == [a, b, c]


def test_unregister_removes_plugin():
    brain = Brain()
    class P:
        pass
    p = P()
    brain.register(p)
    brain.unregister(p)
    assert p not in brain.plugins()


def test_unregister_missing_is_silent():
    brain = Brain()
    class P:
        pass
    brain.unregister(P())  # no exception


def test_summary_reports_plugin_count():
    brain = Brain()
    class P:
        pass
    brain.register(P())
    brain.register(P())
    assert brain.summary()["plugin_count"] == 2


# ---------- no-plugin baseline ----------

def test_ask_without_plugins_unchanged(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)
    r = brain.ask("有給は何日？")
    assert r.source_key == "有給休暇"


def test_missing_callbacks_do_not_error(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)
    class Empty:
        pass
    brain.register(Empty())
    r = brain.ask("有給は何日？")
    assert r.source_key == "有給休暇"


# ---------- before_parse ----------

def test_before_parse_transforms_input(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)

    class Synonym:
        def before_parse(self, text):
            return text.replace("バケーション", "有給")

    brain.register(Synonym())
    r = brain.ask("バケーションは何日？")
    assert r.source_key == "有給休暇"


# ---------- after_parse ----------

def test_after_parse_mutates_intent(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)
    seen = {}

    class Forcer:
        def after_parse(self, parsed):
            seen["intent"] = parsed["intent"]
            parsed["intent"] = "solve"
            return parsed

    brain.register(Forcer())
    r = brain.ask("有給は何日？")
    assert r.intent == "solve"
    assert "intent" in seen


# ---------- before_search ----------

def test_before_search_rewrites_query(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)
    captured = []

    class Expand:
        def before_search(self, q):
            captured.append(q)
            return q + " 休暇"

    brain.register(Expand())
    r = brain.ask("有給")
    assert r.source_key == "有給休暇"
    assert len(captured) == 1


# ---------- after_search ----------

def test_after_search_can_reject_match(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)

    class Reject:
        def after_search(self, match):
            return None

    brain.register(Reject())
    r = brain.ask("有給は何日？")
    assert r.used_fallback is True
    assert r.source_book == ""


def test_after_search_can_modify_match(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)

    class Boost:
        def after_search(self, match):
            if match:
                match["score"] = 0.99
            return match

    brain.register(Boost())
    r = brain.ask("有給は何日？")
    assert r.confidence == 0.99


# ---------- before_compose ----------

def test_before_compose_receives_intent_and_match(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)
    captured = {}

    class Spy:
        def before_compose(self, intent, match):
            captured["intent"] = intent
            captured["match_key"] = match["key"] if match else None
            return intent, match

    brain.register(Spy())
    brain.ask("有給は何日？")
    assert captured["intent"] in ("ask", "general")
    assert captured["match_key"] == "有給休暇"


def test_before_compose_can_override_intent(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)

    class Override:
        def before_compose(self, intent, match):
            return "create", match

    brain.register(Override())
    r = brain.ask("有給")
    assert r.intent == "create"


# ---------- after_compose ----------

def test_after_compose_can_append_to_text(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)

    class Disclaimer:
        def after_compose(self, response):
            response.text += "\n※ 最終判断は担当者へ"
            return response

    brain.register(Disclaimer())
    r = brain.ask("有給は何日？")
    assert r.text.endswith("※ 最終判断は担当者へ")


# ---------- ordering ----------

def test_plugins_run_in_registration_order(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)
    order = []

    class A:
        def before_parse(self, t):
            order.append("A")
            return t
    class B:
        def before_parse(self, t):
            order.append("B")
            return t
    class C:
        def before_parse(self, t):
            order.append("C")
            return t

    brain.register(A())
    brain.register(B())
    brain.register(C())
    brain.ask("有給")
    assert order == ["A", "B", "C"]


def test_before_parse_output_feeds_next_plugin(manual_path):
    brain = Brain()
    brain.load_book("m", manual_path)

    class UpcaseKata:
        def before_parse(self, text):
            return text.replace("バケーション", "有給")
    class Suffix:
        def before_parse(self, text):
            return text + "について"

    brain.register(UpcaseKata())
    brain.register(Suffix())
    r = brain.ask("バケーション")
    assert r.source_key == "有給休暇"
