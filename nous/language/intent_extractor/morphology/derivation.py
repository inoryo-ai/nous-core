"""Phase A.1 — 派生語ルール (morphology / クラスタ保存)。

fugashi が「導入/する」のように分けるサ変動詞 (noun + する) を 1 トークンに復元する。
ルールは最小限から開始し、必要に応じて拡張する。
"""

from __future__ import annotations

from ..types import Token


_SAHEN_LEMMAS = {"する", "為る"}
# サ変動詞の正規 lemma は常に「する」(ひらがな) に統一する。
# fugashi/UniDic は「為る」を返すことがある。
_SAHEN_LEMMA_CANONICAL = "する"


def merge_sahen(tokens: list[Token]) -> list[Token]:
    """名詞 + 「する」系動詞 → 1 つの verb トークンに圧縮。

    例: [導入(noun), する(verb)] → [導入する(verb, lemma='導入する')]
    名詞側が辞書側の専門用語 (term_source) でも対象にする。
    結合 lemma は「為る」を「する」に正規化する。
    """
    if len(tokens) < 2:
        return tokens
    out: list[Token] = []
    i = 0
    while i < len(tokens):
        cur = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if (nxt is not None
                and cur.pos == "noun"
                and nxt.pos == "verb"
                and nxt.lemma in _SAHEN_LEMMAS):
            merged = Token(
                surface=cur.surface + nxt.surface,
                lemma=cur.lemma + _SAHEN_LEMMA_CANONICAL,
                pos="verb",
                pos_detail="サ変/合成",
                function="",
                features={
                    **cur.features,
                    "sahen_base": cur.lemma,
                    "cForm": nxt.features.get("cForm", ""),
                    "cType": "サ変",
                },
            )
            out.append(merged)
            i += 2
        else:
            out.append(cur)
            i += 1
    return out
