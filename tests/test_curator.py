"""Tests for Curator — checkout / retrieve / return cycle."""

import json
import pytest

from nous import KnowledgeStore, BookShelf
from nous.curator import Curator


@pytest.fixture
def shelf_with_manual(tmp_path):
    path = tmp_path / "manual.json"
    data = {
        "_meta": {"title": "規約"},
        "有給休暇": {"日数": "年10日", "申請方法": "上長承認", "category": "休暇"},
        "交通費": {"上限": "月3万円", "申請方法": "清算書提出", "category": "経費"},
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    shelf = BookShelf()
    shelf.load_book("manual", str(path))
    return shelf


def test_checkout_loads_entries_into_ks(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    loaded = cur.checkout("manual")
    assert len(loaded) == 2
    assert ks.access("manual::有給休暇", "日数") == "年10日"


def test_checkout_specific_keys(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    cur.checkout("manual", keys=["有給休暇"])
    assert ks.access("manual::有給休暇", "日数") == "年10日"
    assert ks.access("manual::交通費", "上限") is None


def test_checkout_unknown_book_returns_empty(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    assert cur.checkout("ghost") == []


def test_retrieve_finds_relevant(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    results = cur.retrieve("有給は何日")
    assert len(results) >= 1
    assert results[0]["key"] == "有給休暇"


def test_retrieve_does_not_modify_ks(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    cur.retrieve("有給")
    assert ks.fact_count() == 0


def test_best_match_returns_top(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    top = cur.best_match("有給休暇の日数")
    assert top is not None
    assert top["key"] == "有給休暇"


def test_best_match_below_threshold_returns_none(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    top = cur.best_match("xyzabc", min_score=0.99)
    assert top is None


def test_return_all_clears_ks(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    cur.checkout("manual")
    assert ks.fact_count() > 0
    returned = cur.return_all()
    assert returned == 2
    assert ks.fact_count() == 0


def test_return_all_preserves_unrelated_facts(shelf_with_manual):
    ks = KnowledgeStore()
    ks.store_fact("user_fact", "val", 123)
    cur = Curator(shelf_with_manual, ks)
    cur.checkout("manual")
    cur.return_all()
    assert ks.access("user_fact", "val") == 123


def test_checked_out_summary(shelf_with_manual):
    ks = KnowledgeStore()
    cur = Curator(shelf_with_manual, ks)
    cur.checkout("manual")
    assert cur.checked_out_summary() == {"manual": 2}
