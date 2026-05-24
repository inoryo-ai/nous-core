"""Phase B.1 — Response Composer.

ResponseStrategy + 検索結果 + IntentResult → 最終応答文。
"""

from __future__ import annotations

from pathlib import Path

from ..intent_extractor.types import IntentResult
from .types import KnowledgeChunk, ResponseResult, ResponseStrategy

try:
    import yaml
    _YAML_OK = True
except ImportError:  # pragma: no cover
    _YAML_OK = False


_TEMPLATES_PATH = Path(__file__).parent / "data" / "templates.yaml"


# category_hint → 日本語表示名
_CATEGORY_LABEL = {
    "ga4": "GA4 / 解析",
    "ec": "EC / 店舗",
    "sns": "SNS",
    "ad": "広告",
    "seo": "SEO",
    "web": "Web / LP",
    "marketing": "マーケティング",
    "course": "受講",
    "general": "一般",
    "social": "雑談",
}


class ResponseComposer:
    def __init__(self, templates_path: str | Path | None = None) -> None:
        self._templates_path = Path(templates_path) if templates_path else _TEMPLATES_PATH
        self._templates: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not _YAML_OK or not self._templates_path.exists():
            return
        with self._templates_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._templates = data.get("templates", {}) or {}

    def compose(self, strategy: ResponseStrategy,
                intent_result: IntentResult,
                chunks: list[KnowledgeChunk]) -> ResponseResult:
        # 検索 0 件の場合は *_no_hit テンプレへの自動降格
        template_id = strategy.template_id
        if strategy.needs_retrieval and not chunks:
            fallback = f"{template_id.replace('_polite', '')}_no_hit"
            if fallback in self._templates:
                template_id = fallback

        tpl = self._templates.get(template_id)
        if tpl is None:
            tpl = self._templates.get("ask_general_polite", {"body": "ご質問ありがとうございます。"})

        text = self._render(tpl, intent_result, chunks)
        return ResponseResult(
            text=text,
            intent=intent_result.intent,
            template_id=template_id,
            chunks=chunks,
            needs_clarification=template_id.startswith("clarify_"),
            trace={
                "strategy": template_id,
                "category_hint": intent_result.category_hint,
                "confidence": intent_result.confidence,
                "n_chunks": len(chunks),
            },
        )

    def _render(self, tpl: dict, intent_result: IntentResult,
                chunks: list[KnowledgeChunk]) -> str:
        body = tpl.get("body", "")
        # slots
        topic = self._pick_topic(intent_result)
        category_label = _CATEGORY_LABEL.get(intent_result.category_hint, intent_result.category_hint or "")
        chunks_block = self._format_chunks(chunks)
        first_title = chunks[0].title if chunks else ""
        return (body
                .replace("{topic}", topic or "ご質問の内容")
                .replace("{category}", category_label)
                .replace("{first_title}", first_title)
                .replace("{chunks}", chunks_block))

    def _pick_topic(self, intent_result: IntentResult) -> str:
        if intent_result.semantics_out:
            topic = intent_result.semantics_out.filled_schema.get("topic", "")
            if topic:
                return str(topic)
        if intent_result.category_hint:
            return _CATEGORY_LABEL.get(intent_result.category_hint,
                                       intent_result.category_hint)
        if intent_result.keywords:
            return intent_result.keywords[0]
        return ""

    def _format_chunks(self, chunks: list[KnowledgeChunk]) -> str:
        if not chunks:
            return ""
        lines = []
        for c in chunks:
            lines.append(f"・【{c.title}】")
            for body_line in c.body.split("\n"):
                lines.append(f"    {body_line}")
        return "\n".join(lines)
