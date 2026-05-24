"""Tests for KnowledgeStore — 4 atomic operations + fact lifecycle."""

from nous.knowledge import KnowledgeStore


def test_store_and_access_numeric():
    ks = KnowledgeStore()
    ks.store_fact("apple", "price", 100)
    assert ks.access("apple", "price") == 100


def test_store_and_access_string():
    ks = KnowledgeStore()
    ks.store_fact("company", "policy", "休暇は年10日付与")
    assert ks.access("company", "policy") == "休暇は年10日付与"


def test_access_missing_returns_none():
    ks = KnowledgeStore()
    assert ks.access("nonexistent", "x") is None


def test_equal_atomic():
    assert KnowledgeStore.equal(5, 5) is True
    assert KnowledgeStore.equal(5, 6) is False
    assert KnowledgeStore.equal("a", "a") is True


def test_greater_atomic():
    assert KnowledgeStore.greater(5, 3) is True
    assert KnowledgeStore.greater(3, 5) is False
    assert KnowledgeStore.greater(None, 5) is None


def test_similar_numeric():
    assert KnowledgeStore.similar(5, 5) == 1.0
    assert KnowledgeStore.similar(5, 10) == 0.5
    assert KnowledgeStore.similar(None, 5) == 0.0


def test_similar_string():
    s = KnowledgeStore.similar("hello", "hello")
    assert s == 1.0
    s = KnowledgeStore.similar("hello", "world")
    assert 0.0 <= s < 1.0


def test_contradiction_detection():
    ks = KnowledgeStore()
    ks.store_fact("x", "p", 1, conf=1.0)
    r = ks.store_fact("x", "p", 2, conf=1.0)
    assert r == "contradiction"


def test_higher_confidence_overwrites():
    ks = KnowledgeStore()
    ks.store_fact("x", "p", 1, conf=0.3)
    ks.store_fact("x", "p", 2, conf=0.9)
    assert ks.access("x", "p") == 2


def test_find_all_with_property():
    ks = KnowledgeStore()
    ks.store_fact("apple", "color", "red")
    ks.store_fact("banana", "color", "yellow")
    ks.store_fact("apple", "price", 100)
    results = ks.find_all_with_property("color")
    assert len(results) == 2
    colors = {c: v for c, v, _ in results}
    assert colors == {"apple": "red", "banana": "yellow"}


def test_find_properties():
    ks = KnowledgeStore()
    ks.store_fact("apple", "color", "red")
    ks.store_fact("apple", "price", 100)
    ks.store_fact("banana", "color", "yellow")
    props = ks.find_properties("apple")
    assert props == {"color": "red", "price": 100}


def test_lookup_returns_value_and_confidence():
    ks = KnowledgeStore()
    ks.store_fact("x", "p", "val", conf=0.8)
    v, c = ks.lookup("x", "p")
    assert v == "val"
    assert c == 0.8


def test_categories():
    ks = KnowledgeStore()
    ks.store_category("apple", "fruit")
    ks.store_category("apple", "red")
    ks.store_category("apple", "fruit")  # dedup
    assert ks.get_categories("apple") == ["fruit", "red"]


def test_rules():
    ks = KnowledgeStore()
    ks.store_rule("if_hot", "drink_water", conf=0.9)
    result, conf = ks.find_rule("if_hot")
    assert result == "drink_water"
    assert conf == 0.9


def test_summary():
    ks = KnowledgeStore()
    ks.store_fact("x", "p", 1)
    ks.store_fact("y", "q", 2)
    s = ks.summary()
    assert "Facts: 2" in s
    assert "Concepts: 2" in s
