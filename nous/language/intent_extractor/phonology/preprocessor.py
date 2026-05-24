"""Phase A.1 — Phonology (音韻層).

Responsibilities:
1. Unicode 正規化 (NFKC): 全角英数→半角、半角カタカナ→全角、互換文字統一
2. 制御文字 / 零幅文字 / BOM の除去
3. 空白正規化 (連続空白→単一、前後空白除去)
4. 文字種判定 (hiragana/katakana/kanji/ascii/digit/symbol)
5. 表記揺れ正規化 (orthographic_variants.yaml をクラスタ保存形態として適用)
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from ..types import CharSegment, PhonologyOutput

try:
    import yaml  # PyYAML
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False


_DATA_DIR = Path(__file__).parent / "data"

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")


def _classify_char(ch: str) -> str:
    """Return the character-type kind for a single character."""
    code = ord(ch)
    if 0x3040 <= code <= 0x309F:
        return "hiragana"
    if 0x30A0 <= code <= 0x30FF:
        return "katakana"
    if 0x4E00 <= code <= 0x9FFF:
        return "kanji"
    if ch.isdigit():
        return "digit"
    if ch.isascii() and ch.isalpha():
        return "ascii"
    if ch.isspace():
        return "space"
    if unicodedata.category(ch).startswith("P"):
        return "punct"
    if unicodedata.category(ch).startswith("S"):
        return "symbol"
    return "other"


def _segment(text: str) -> list[CharSegment]:
    """Group consecutive characters of the same kind into segments."""
    segments: list[CharSegment] = []
    if not text:
        return segments
    cur_kind = _classify_char(text[0])
    start = 0
    for i in range(1, len(text)):
        kind = _classify_char(text[i])
        if kind != cur_kind:
            segments.append(CharSegment(
                text=text[start:i], kind=cur_kind, start=start, end=i,
            ))
            cur_kind = kind
            start = i
    segments.append(CharSegment(
        text=text[start:], kind=cur_kind, start=start, end=len(text),
    ))
    return segments


class Phonology:
    """音韻層: 文字レベルの正規化と分節。"""

    def __init__(self,
                 variants_path: str | Path | None = None,
                 noise_path: str | Path | None = None) -> None:
        self._variants_path = Path(variants_path) if variants_path else _DATA_DIR / "orthographic_variants.yaml"
        self._noise_path = Path(noise_path) if noise_path else _DATA_DIR / "noise_chars.yaml"
        self._variant_map: dict[str, str] = {}
        self._noise_chars: set[str] = set()
        self._load_data()

    def _load_data(self) -> None:
        if not _YAML_OK:
            return
        if self._variants_path.exists():
            with self._variants_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for entry in data.get("variants", []):
                canonical = entry.get("canonical")
                if not canonical:
                    continue
                for alias in entry.get("aliases", []):
                    if alias and alias != canonical:
                        self._variant_map[alias] = canonical
        if self._noise_path.exists():
            with self._noise_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for ch in data.get("remove", []):
                if isinstance(ch, str):
                    self._noise_chars.add(ch)
            for ch in data.get("keep", []):
                self._noise_chars.discard(ch)

    def normalize(self, raw: str) -> PhonologyOutput:
        if raw is None:
            raw = ""
        removed: list[str] = []

        # 1. NFKC: 全角英数→半角、半角カナ→全角、互換文字統一
        nfkc = unicodedata.normalize("NFKC", raw)

        # 2. 制御文字除去
        if _CONTROL_RE.search(nfkc):
            removed.extend(_CONTROL_RE.findall(nfkc))
            nfkc = _CONTROL_RE.sub("", nfkc)

        # 3. ノイズ文字除去 (yaml 由来 + 既定零幅文字)
        if self._noise_chars:
            for ch in self._noise_chars:
                if ch in nfkc:
                    removed.append(ch)
                    nfkc = nfkc.replace(ch, "")

        # 4. 空白正規化
        nfkc = _WS_RE.sub(" ", nfkc).strip()

        # 5. 表記揺れ正規化 (クラスタ保存形態)
        if self._variant_map:
            # 長い alias を先に置換 (短い alias による副作用回避)
            for alias in sorted(self._variant_map.keys(), key=len, reverse=True):
                if alias in nfkc:
                    nfkc = nfkc.replace(alias, self._variant_map[alias])

        # 6. 文字種分節
        segments = _segment(nfkc)

        return PhonologyOutput(
            raw=raw,
            normalized=nfkc,
            char_segments=segments,
            noise_removed=removed,
            confidence=1.0 if nfkc else 0.0,
        )
