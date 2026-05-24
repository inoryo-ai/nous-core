"""Tests for LanguageEngine — tokenize / parse / learn_pattern."""

from nous import KnowledgeStore, LanguageEngine


def _le():
    return LanguageEngine(KnowledgeStore())


def test_tokenize_english():
    le = _le()
    tokens = le.tokenize("How to calculate the price?")
    assert "calculate" in tokens
    assert "price" in tokens
    assert "the" not in tokens


def test_tokenize_japanese_no_vocab():
    le = _le()
    tokens = le.tokenize("有給休暇は何日ですか？")
    assert len(tokens) >= 1


def test_tokenize_japanese_with_vocab():
    wiki = {"freq_noun": {"有給": 10, "休暇": 8, "申請": 5}}
    le = LanguageEngine(KnowledgeStore(), wiki_patterns=wiki)
    tokens = le.tokenize("有給休暇の申請方法は？")
    assert "有給" in tokens
    assert "休暇" in tokens
    assert "申請" in tokens


def test_tokenize_deduplicates():
    le = _le()
    tokens = le.tokenize("price price price")
    assert tokens.count("price") == 1


def test_parse_ask_intent_jp():
    le = _le()
    r = le.parse("有給は何日ですか？")
    assert r["intent"] == "ask"


def test_parse_solve_intent_jp():
    le = _le()
    r = le.parse("100の2倍を計算してください")
    assert r["intent"] == "solve"


def test_parse_learn_intent_jp():
    le = _le()
    r = le.parse("契約書の書き方を教えてください")
    assert r["intent"] in ("learn", "ask")


def test_parse_create_intent_jp():
    le = _le()
    r = le.parse("提案書を作成してほしい")
    assert r["intent"] == "create"


def test_parse_returns_keywords():
    le = _le()
    r = le.parse("How to submit the report?")
    assert isinstance(r["keywords"], list)
    assert len(r["keywords"]) > 0


def test_parse_confidence_in_range():
    le = _le()
    r = le.parse("何か質問")
    assert 0.0 <= r["confidence"] <= 1.0


def test_learn_pattern_persisted():
    ks = KnowledgeStore()
    le = LanguageEngine(ks)
    pid = le.learn_pattern("売上を計算", "solve", target="売上")
    assert pid.startswith("lang_pattern_")
    assert ks.access(pid, "intent") == "solve"
    assert ks.access(pid, "target") == "売上"


def test_learn_and_match_pattern():
    ks = KnowledgeStore()
    le = LanguageEngine(ks)
    le.learn_pattern("今月の売上を計算して", "solve", target="売上")
    r = le.parse("今月の売上を計算して")
    assert r["intent"] == "solve"
    assert r["matched_pattern"] is not None
    assert r["confidence"] > 0.5


def test_parse_general_for_unknown():
    le = _le()
    r = le.parse("xyz abc def")
    assert r["intent"] == "general"


def test_pattern_count_grows():
    ks = KnowledgeStore()
    le = LanguageEngine(ks)
    assert le.pattern_count() == 0
    le.learn_pattern("a test", "ask")
    assert le.pattern_count() == 1
    le.learn_pattern("another", "solve")
    assert le.pattern_count() == 2


def test_summary_contains_counts():
    le = _le()
    s = le.summary()
    assert "LanguageEngine" in s
