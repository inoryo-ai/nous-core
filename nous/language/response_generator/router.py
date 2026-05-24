"""Phase B.1 — Response Router.

IntentResult → ResponseStrategy.
intent + speech_act + confidence + history を見て、どのテンプレを使うか決める。
"""

from __future__ import annotations

from ..intent_extractor.types import IntentResult
from .types import ResponseStrategy


# confidence がこれを下回ると clarify テンプレに分岐
_LOW_CONFIDENCE = 0.25


class ResponseRouter:
    """ルール優先順:
    1. confidence < _LOW_CONFIDENCE → clarify_low_confidence
    2. intent=chat の場合は speech_act で分岐 (greeting/thanks/acknowledgment)
    3. それ以外は intent ごとに polite テンプレ (knowledge 検索を要求)
    """

    def __init__(self, low_confidence_threshold: float = _LOW_CONFIDENCE) -> None:
        self.low_confidence_threshold = low_confidence_threshold

    def route(self, intent_result: IntentResult) -> ResponseStrategy:
        intent = intent_result.intent
        speech_act = intent_result.speech_act
        confidence = intent_result.confidence

        if intent == "chat":
            # 社交系: 不確かでも応答できる (clarify しない)
            if speech_act == "greeting":
                return ResponseStrategy(template_id="chat_greeting",
                                        needs_retrieval=False,
                                        politeness="polite",
                                        require_followup=True)
            if speech_act == "thanks":
                return ResponseStrategy(template_id="chat_thanks",
                                        needs_retrieval=False)
            if speech_act == "acknowledgment":
                return ResponseStrategy(template_id="chat_acknowledgment",
                                        needs_retrieval=False)
            return ResponseStrategy(template_id="chat_acknowledgment",
                                    needs_retrieval=False)

        # 非 chat で信頼度が低い → 確認に誘導
        if confidence < self.low_confidence_threshold:
            return ResponseStrategy(
                template_id="clarify_low_confidence",
                needs_retrieval=False,
                politeness="polite",
                fallback_reason=f"confidence {confidence} below {self.low_confidence_threshold}",
            )

        # 通常: intent → polite テンプレ
        template_map = {
            "ask_lesson":  "ask_lesson_polite",
            "ask_roadmap": "ask_roadmap_polite",
            "ask_faq":     "ask_faq_polite",
            "ask_study":   "ask_study_polite",
            "ask_general": "ask_general_polite",
            "withdraw":    "withdraw_polite",
            "inquiry":     "inquiry_polite",
        }
        template_id = template_map.get(intent, "ask_general_polite")
        return ResponseStrategy(
            template_id=template_id,
            needs_retrieval=intent not in {"inquiry"},
            politeness="polite",
        )
