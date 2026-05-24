"""Tests for Book / WritableBook / BookShelf."""

import json
import pytest

from nous import Book, BookShelf
from nous.bookshelf import WritableBook


@pytest.fixture
def manual_book_path(tmp_path):
    path = tmp_path / "manual.json"
    data = {
        "_meta": {"title": "社員規約", "version": "1.0"},
        "有給休暇": {
            "日数": "年10日（6ヶ月経過後）",
            "申請方法": "上長承認→人事システム登録",
            "category": "休暇",
        },
        "交通費": {
            "上限": "月3万円",
            "申請方法": "毎月末に清算書提出",
            "category": "経費",
        },
        "リモートワーク": {
            "条件": "入社6ヶ月以降、週3日まで",
            "申請方法": "前月15日までに申請",
            "category": "働き方",
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_book_lazy_load(manual_book_path):
    book = Book("manual", manual_book_path)
    assert book._data is None
    _ = book.data
    assert book._data is not None


def test_book_meta(manual_book_path):
    book = Book("manual", manual_book_path)
    assert book.meta["title"] == "社員規約"


def test_book_get(manual_book_path):
    book = Book("manual", manual_book_path)
    entry = book.get("有給休暇")
    assert entry["日数"] == "年10日（6ヶ月経過後）"


def test_book_keys_excludes_meta(manual_book_path):
    book = Book("manual", manual_book_path)
    keys = book.keys()
    assert "_meta" not in keys
    assert "有給休暇" in keys


def test_book_len(manual_book_path):
    book = Book("manual", manual_book_path)
    assert len(book) == 3


def test_book_query_by_condition(manual_book_path):
    book = Book("manual", manual_book_path)
    results = book.query(lambda k, v: v.get("category") == "休暇")
    assert len(results) == 1
    assert results[0][0] == "有給休暇"


def test_book_search_text_finds_match(manual_book_path):
    book = Book("manual", manual_book_path)
    results = book.search_text("有給", limit=3)
    assert len(results) >= 1
    assert results[0][0] == "有給休暇"


def test_book_search_text_by_value(manual_book_path):
    book = Book("manual", manual_book_path)
    results = book.search_text("月3万円", limit=3)
    assert any(k == "交通費" for k, _, _ in results)


def test_writable_book_add_and_save(tmp_path):
    path = tmp_path / "wb.json"
    path.write_text("{}", encoding="utf-8")
    wb = WritableBook("wb", str(path))
    wb.add_entry("新ルール", {"policy": "XYZ"})
    wb.save()

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["新ルール"]["policy"] == "XYZ"


def test_writable_book_update(tmp_path):
    path = tmp_path / "wb.json"
    path.write_text(json.dumps({"A": {"v": 1}}), encoding="utf-8")
    wb = WritableBook("wb", str(path))
    wb.update_entry("A", {"v": 2})
    wb.save()
    assert json.loads(path.read_text(encoding="utf-8"))["A"]["v"] == 2


def test_writable_book_delete(tmp_path):
    path = tmp_path / "wb.json"
    path.write_text(json.dumps({"A": 1, "B": 2}), encoding="utf-8")
    wb = WritableBook("wb", str(path))
    wb.delete_entry("A")
    wb.save()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "A" not in saved
    assert "B" in saved


def test_bookshelf_register_and_get(manual_book_path):
    shelf = BookShelf()
    shelf.load_book("manual", manual_book_path)
    assert "manual" in shelf
    assert shelf.get("manual") is not None


def test_bookshelf_search_across(tmp_path, manual_book_path):
    shelf = BookShelf()
    shelf.load_book("manual", manual_book_path)

    faq_path = tmp_path / "faq.json"
    faq_path.write_text(json.dumps({
        "Q1": {"question": "有給の残日数は？", "answer": "マイページで確認"}
    }, ensure_ascii=False), encoding="utf-8")
    shelf.load_book("faq", str(faq_path))

    results = shelf.search("有給", limit=5)
    assert len(results) >= 2
    book_names = {r[0] for r in results}
    assert "manual" in book_names
    assert "faq" in book_names


def test_bookshelf_names(manual_book_path):
    shelf = BookShelf()
    shelf.load_book("manual", manual_book_path)
    assert shelf.names() == ["manual"]
