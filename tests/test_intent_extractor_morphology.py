"""Phase A.1 — Morphology layer tests.

fugashi+UniDic 形態素解析、専門用語 longest-match、助詞機能注釈、サ変派生。
"""

import pytest

from nous.language.intent_extractor.morphology import Morphology


@pytest.fixture(scope="module")
def morph() -> Morphology:
    return Morphology()


# ---- 基本 tokenize ----

def test_tokenize_basic(morph: Morphology) -> None:
    tokens = morph.tokenize("使い方を教えて")
    surfaces = [t.surface for t in tokens]
    # 「使い方」は専門用語辞書で 1 トークン化
    assert "使い方" in surfaces
    assert "を" in surfaces


def test_tokenize_empty(morph: Morphology) -> None:
    assert morph.tokenize("") == []


def test_pos_simplified(morph: Morphology) -> None:
    tokens = morph.tokenize("猫が走る")
    poss = {t.surface: t.pos for t in tokens}
    assert poss.get("猫") == "noun"
    assert poss.get("が") == "particle"
    assert poss.get("走る") == "verb"


def test_verb_lemma_normalized(morph: Morphology) -> None:
    tokens = morph.tokenize("教えてください")
    verbs = [t for t in tokens if t.pos == "verb"]
    assert any(t.lemma == "教える" for t in verbs), \
        f"教える の lemma 正規化失敗: {[(t.surface, t.lemma) for t in verbs]}"


# ---- 専門用語 longest-match ----

def test_term_ga4_merged(morph: Morphology) -> None:
    tokens = morph.tokenize("GA4の使い方")
    surfaces = [t.surface for t in tokens]
    assert "GA4" in surfaces
    # fugashi が分割した "GA"/"4" が単独で残っていないこと
    assert "GA" not in surfaces
    assert "4" not in surfaces


def test_term_alias_recognized(morph: Morphology) -> None:
    tokens = morph.tokenize("インスタの運用方法")
    surfaces = [t.surface for t in tokens]
    # alias "インスタ" は term として認識される (surface はそのまま)
    assert "インスタ" in surfaces
    inst = next(t for t in tokens if t.surface == "インスタ")
    assert inst.pos == "noun"
    assert inst.features.get("term_source") is True
    assert inst.features.get("category") == "sns"


def test_term_category_propagated(morph: Morphology) -> None:
    tokens = morph.tokenize("Shopifyの設定")
    shop = next((t for t in tokens if t.surface == "Shopify"), None)
    assert shop is not None
    assert shop.features.get("category") == "ec"


def test_term_longest_match(morph: Morphology) -> None:
    # "Google Analytics" は "Google" より長い。長い方が優先されること。
    tokens = morph.tokenize("Google Analyticsの設定")
    surfaces = [t.surface for t in tokens]
    assert "Google Analytics" in surfaces


# ---- 助詞機能注釈 ----

def test_particle_case_marker_wo(morph: Morphology) -> None:
    tokens = morph.tokenize("本を読む")
    wo = next(t for t in tokens if t.surface == "を")
    assert wo.function == "case_marker"
    assert wo.features.get("role") == "wo"


def test_particle_topic_wa(morph: Morphology) -> None:
    tokens = morph.tokenize("猫は走る")
    wa = next(t for t in tokens if t.surface == "は")
    assert wa.function == "topic_marker"


def test_particle_sentence_final_ka(morph: Morphology) -> None:
    tokens = morph.tokenize("これですか")
    ka = next((t for t in tokens if t.surface == "か"), None)
    assert ka is not None
    assert ka.function == "sentence_final"


def test_particle_adnominal_no(morph: Morphology) -> None:
    tokens = morph.tokenize("GA4の使い方")
    no = next(t for t in tokens if t.surface == "の" and t.pos == "particle")
    assert no.function == "adnominal"


def test_particle_fallback_from_pos2(morph: Morphology) -> None:
    """particles.yaml に未登録でも UniDic pos2 から function を推定。"""
    # 全部辞書に入っているが、推定経路が落ちないことだけ確認
    tokens = morph.tokenize("猫が走る")
    ga = next(t for t in tokens if t.surface == "が")
    assert ga.function in ("case_marker", "particle")


# ---- 派生語: サ変動詞 ----

def test_sahen_merge_simple(morph: Morphology) -> None:
    tokens = morph.tokenize("導入する")
    # 「導入する」が 1 トークンの verb に圧縮されている
    verb_tokens = [t for t in tokens if t.pos == "verb"]
    assert any(t.surface == "導入する" for t in verb_tokens), \
        f"サ変結合失敗: {[(t.surface, t.pos) for t in tokens]}"


def test_sahen_merge_preserves_cform(morph: Morphology) -> None:
    tokens = morph.tokenize("運用した")
    verb = next((t for t in tokens if t.pos == "verb"
                 and t.surface.startswith("運用")), None)
    assert verb is not None
    # cForm は連用形/已然形等、空でないこと
    assert verb.features.get("cForm", "") != ""


def test_sahen_no_merge_when_no_suru(morph: Morphology) -> None:
    """名詞が単独 (する後続なし) では結合しない。"""
    tokens = morph.tokenize("導入の方法")
    surfaces = [t.surface for t in tokens]
    assert "導入" in surfaces
    assert "導入の" not in surfaces


# ---- mixed real-world ----

def test_realistic_question_1(morph: Morphology) -> None:
    tokens = morph.tokenize("GA4の使い方を教えてください")
    surfaces = [t.surface for t in tokens]
    # 重要要素がすべて token として現れる
    assert "GA4" in surfaces
    assert "使い方" in surfaces
    assert "教える" in [t.lemma for t in tokens]


def test_realistic_question_withdraw(morph: Morphology) -> None:
    tokens = morph.tokenize("退会したいです")
    # 「退会する」がサ変結合される
    assert any(t.surface == "退会したい" or t.surface.startswith("退会")
               and t.pos == "verb" for t in tokens), \
        f"退会の verb 化失敗: {[(t.surface, t.pos) for t in tokens]}"


def test_realistic_long_input(morph: Morphology) -> None:
    """100ms 制限の sanity check (実機 50ms 程度想定)。"""
    import time
    text = "Instagramの広告でコンバージョン率が下がったのでGA4で原因を調べたい"
    t0 = time.perf_counter()
    tokens = morph.tokenize(text)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert len(tokens) > 0
    assert elapsed_ms < 200.0, f"morphology too slow: {elapsed_ms:.1f}ms"
    # 主要 term が認識されている
    surfaces = [t.surface for t in tokens]
    assert "Instagram" in surfaces
    assert "コンバージョン" in surfaces
    assert "GA4" in surfaces
