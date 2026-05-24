"""Phase A.1 — Syntax (統語層).

Responsibilities:
1. 述語の同定: 文末の動詞/形容詞/コピュラ
2. 助詞 role → 格役割 (Argument)
3. 項充足 (verb_frames.yaml に基づく必須格チェック)
4. sentence_type 判定: declarative / interrogative / imperative / exclamative
5. 省略補完: defaults からの補填

設計原則:
- 形態層 Token を読み取り専用で使う (副作用なし)
- 構造選択 (case_markers via particles.yaml) と動的ゲート (verb frame) を分離
"""

from __future__ import annotations

from pathlib import Path

from ..types import Argument, SyntaxOutput, Token

try:
    import yaml
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False


_DATA_DIR = Path(__file__).parent / "data"


_PREDICATE_POS = {"verb", "adj"}
_AUX_LEMMAS_DESIRE = {"たい", "たがる", "ほしい", "欲しい"}
_AUX_LEMMAS_POLITE = {"ます", "です"}
_AUX_LEMMAS_NEG = {"ない", "ぬ", "ず", "まい"}
_IMPERATIVE_CFORMS = {"命令形", "命令形-一般", "命令形-一般-促音便"}
# 補助動詞・非自立動詞 (本動詞ではなく文末機能を担う): pos2 で判定
_LIGHT_VERB_POS2 = {"非自立可能", "形式名詞"}
# よく出る補助動詞 lemma — 本動詞があれば skip
_LIGHT_VERB_LEMMAS = {"下さる", "しまう", "おく", "ある", "いる", "みる",
                       "いく", "くる", "いただく", "もらう", "あげる", "やる"}


class Syntax:
    """統語層: 述語/格役割/sentence_type/省略補完。"""

    def __init__(self,
                 verb_frames_path: str | Path | None = None) -> None:
        self._frames_path = Path(verb_frames_path) if verb_frames_path else _DATA_DIR / "verb_frames.yaml"
        self._frames: dict[str, dict] = {}
        self._load_data()

    def _load_data(self) -> None:
        if not _YAML_OK or not self._frames_path.exists():
            return
        with self._frames_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._frames = data.get("frames", {}) or {}

    # ---- public API ----

    def parse(self, tokens: list[Token]) -> SyntaxOutput:
        if not tokens:
            return SyntaxOutput(tokens=[], predicate=None, arguments=[],
                                sentence_type="declarative", confidence=0.0)

        # 否定マーキング: aux「ない」「ません」「ぬ」が verb/adj に続いたら negated フラグ
        self._mark_negation(tokens)

        predicate, predicate_idx = self._find_predicate(tokens)
        sentence_type = self._detect_sentence_type(tokens, predicate)
        arguments = self._extract_arguments(tokens, predicate_idx)
        arguments = self._fill_defaults(arguments, predicate)

        confidence = self._compute_confidence(predicate, arguments, tokens)

        return SyntaxOutput(
            tokens=list(tokens),
            predicate=predicate,
            arguments=arguments,
            sentence_type=sentence_type,
            confidence=confidence,
        )

    def _mark_negation(self, tokens: list[Token]) -> None:
        """否定 aux (ない/ません/ぬ/まい) が verb/adj に後続したら、その verb/adj に
        features['negated']=True を立てる。

        例: わかり/ません → わかり は negated。
            分から/ない → 分から は negated。
        間に助詞や aux が挟まる場合は近い verb/adj に伝播 (連体修飾節は対象外)。
        """
        for i, tok in enumerate(tokens):
            if tok.pos != "aux":
                continue
            if tok.lemma not in _AUX_LEMMAS_NEG:
                continue
            # 直前の verb/adj を探す (aux 連鎖を超えて遡る)
            for j in range(i - 1, -1, -1):
                cand = tokens[j]
                if cand.pos in _PREDICATE_POS:
                    cand.features["negated"] = True
                    break
                if cand.pos in {"aux", "particle"}:
                    continue
                break

    # ---- predicate ----

    def _find_predicate(self, tokens: list[Token]) -> tuple[Token | None, int]:
        """文末から走査して本動詞を採用。補助動詞は飛ばし、より前の本動詞を取る。

        サ変合成済みトークン (e.g. 退会する) もそのまま述語として採用。
        """
        # Pass 1: 文末から非補助動詞を探す
        for i in range(len(tokens) - 1, -1, -1):
            tok = tokens[i]
            if tok.pos in _PREDICATE_POS:
                if self._is_light_verb(tok):
                    continue
                return tok, i
            if tok.pos == "aux" and tok.lemma in _AUX_LEMMAS_POLITE:
                return tok, i
        # Pass 2: 補助動詞しかなければ最後の verb を採用
        for i in range(len(tokens) - 1, -1, -1):
            if tokens[i].pos in _PREDICATE_POS:
                return tokens[i], i
        # Pass 3: 名詞文
        for i in range(len(tokens) - 1, -1, -1):
            if tokens[i].pos in {"noun", "pron"}:
                return tokens[i], i
        return None, -1

    def _is_light_verb(self, tok: Token) -> bool:
        if tok.lemma in _LIGHT_VERB_LEMMAS:
            return True
        if tok.features.get("pos2", "") in _LIGHT_VERB_POS2:
            return True
        return False

    # ---- sentence type ----

    def _detect_sentence_type(self, tokens: list[Token],
                              predicate: Token | None) -> str:
        # 1. 終助詞「か」または「?」「？」 → interrogative
        for tok in tokens:
            if tok.pos == "particle" and tok.surface == "か" \
                    and tok.function == "sentence_final":
                return "interrogative"
            if tok.surface in {"?", "？"}:
                return "interrogative"
        # 2. 述語の cForm が命令形 → imperative
        if predicate is not None:
            cform = predicate.features.get("cForm", "")
            if cform in _IMPERATIVE_CFORMS:
                return "imperative"
        # 3. 「て」+ 「ください」「ほしい」 形式 → imperative (request)
        for i, tok in enumerate(tokens[:-1]):
            if tok.surface == "て" and tok.pos == "particle":
                nxt = tokens[i + 1]
                if nxt.lemma in {"下さる", "ください", "ほしい", "欲しい"}:
                    return "imperative"
        # 4. WH 疑問詞 + 述語 → interrogative
        wh_words = {"何", "なに", "どこ", "誰", "だれ", "いつ", "どう", "なぜ",
                    "どれ", "どの", "どちら", "なん"}
        for tok in tokens:
            if tok.surface in wh_words or tok.lemma in wh_words:
                return "interrogative"
        return "declarative"

    # ---- arguments ----

    def _extract_arguments(self, tokens: list[Token],
                           predicate_idx: int) -> list[Argument]:
        """各 case_marker の直前トークンを項として登録。"""
        args: list[Argument] = []
        n = len(tokens)
        # 述語より後の助詞は対象外 (基本日本語の主節構造を想定)
        upper = predicate_idx if predicate_idx >= 0 else n
        for i in range(upper):
            tok = tokens[i]
            if tok.pos != "particle":
                continue
            role = tok.features.get("role")
            if not role and tok.function == "topic_marker":
                role = "topic"
            if not role:
                continue
            # 直前の content head を取得 (連続 noun は連結)
            head, head_text = self._head_before(tokens, i)
            if head is None:
                continue
            args.append(Argument(role=role, head_token=head, text=head_text))
        return args

    def _head_before(self, tokens: list[Token], idx: int) -> tuple[Token | None, str]:
        """idx の直前にある content head (noun/pron/proper) を取得。

        連続する noun/suffix は連結して 1 つの head とみなす。
        """
        if idx == 0:
            return None, ""
        # back-scan
        j = idx - 1
        end = j
        while j >= 0 and tokens[j].pos in {"noun", "pron", "suffix"}:
            j -= 1
        start = j + 1
        if start > end:
            return None, ""
        head = tokens[end]  # 連続 head の最後尾を代表
        text = "".join(t.surface for t in tokens[start:end + 1])
        return head, text

    # ---- ellipsis (defaults fill) ----

    def _fill_defaults(self, args: list[Argument],
                       predicate: Token | None) -> list[Argument]:
        if predicate is None:
            return args
        frame = self._frames.get(predicate.lemma)
        if not frame:
            return args
        existing_roles = {a.role for a in args}
        for role, default_value in (frame.get("defaults") or {}).items():
            if role in existing_roles:
                continue
            args.append(Argument(role=role, head_token=None, text=str(default_value)))
        return args

    # ---- confidence ----

    def _compute_confidence(self, predicate: Token | None,
                            args: list[Argument],
                            tokens: list[Token]) -> float:
        if predicate is None or not tokens:
            return 0.0
        score = 0.5  # base
        if predicate.pos in _PREDICATE_POS:
            score += 0.2
        # 実引数のみ (defaults 補完は除外)
        real_args = [a for a in args if a.head_token is not None]
        if real_args:
            # 数に応じて段階的に加算 (最大 +0.15)
            score += min(0.15, 0.05 * len(real_args))
        # 必須格カバレッジ (実引数ベース)
        frame = self._frames.get(predicate.lemma) if self._frames else None
        if frame:
            required = set(frame.get("roles", []))
            if required:
                real_roles = {a.role for a in real_args}
                hit = len(required & real_roles)
                score += 0.15 * (hit / len(required))
            else:
                score += 0.05
        return round(min(1.0, score), 4)
