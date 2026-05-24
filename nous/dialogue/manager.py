"""DialogueManager — multi-turn conversation context.

Tracks recent turns so follow-up questions ("それは？" / "もっと詳しく")
can resolve against previous context. No persistence — lives for one session.
"""

from collections import deque


class DialogueManager:
    """Minimal conversation memory for one session."""

    def __init__(self, history_size=10):
        self._history = deque(maxlen=history_size)
        self._last_topic = None

    def record(self, user_text, intent, topic, response_text):
        """Store one turn."""
        self._history.append({
            "user": user_text,
            "intent": intent,
            "topic": topic,
            "response": response_text,
        })
        if topic:
            self._last_topic = topic

    def resolve_reference(self, text):
        """If text uses a referential word ("それ", "あれ"), return last topic."""
        referentials = ("それ", "あれ", "これ", "その", "あの", "この")
        if any(r in text for r in referentials) and self._last_topic:
            return self._last_topic
        return None

    def last_topic(self):
        return self._last_topic

    def history(self):
        return list(self._history)

    def clear(self):
        self._history.clear()
        self._last_topic = None
