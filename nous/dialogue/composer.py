"""ResponseComposer — turns retrieved knowledge into natural language.

Templates by intent. No LLM. Deterministic, auditable.
"""


class ResponseComposer:
    """Compose Japanese responses from retrieved Curator results."""

    NO_MATCH_TEMPLATE = "申し訳ございません、その内容は登録された知識にありませんでした。"

    def compose(self, query, intent, match):
        """Build a response string from a match dict.

        Args:
            query: original user text
            intent: parsed intent (ask / solve / learn / create / ...)
            match: dict from Curator.best_match() or None

        Returns:
            str — response text
        """
        if not match:
            return self.NO_MATCH_TEMPLATE

        entry = match["entry"]
        key = match["key"]

        if intent in ("ask", "learn", "general"):
            return self._compose_information(key, entry)
        if intent == "solve":
            return self._compose_solution(key, entry)
        if intent == "create":
            return self._compose_creation(key, entry)
        return self._compose_information(key, entry)

    def _compose_information(self, key, entry):
        if isinstance(entry, dict):
            parts = [f"【{key}】"]
            for k, v in entry.items():
                if k.startswith("_"):
                    continue
                parts.append(f"・{k}：{self._stringify(v)}")
            return "\n".join(parts)
        return f"【{key}】{self._stringify(entry)}"

    def _compose_solution(self, key, entry):
        if isinstance(entry, dict):
            head = f"「{key}」について、以下の情報が該当します。"
            body = "、".join(f"{k}={self._stringify(v)}" for k, v in entry.items()
                            if not k.startswith("_"))
            return f"{head}\n{body}"
        return f"{key}：{self._stringify(entry)}"

    def _compose_creation(self, key, entry):
        if isinstance(entry, dict):
            parts = [f"「{key}」のテンプレート案："]
            for k, v in entry.items():
                if k.startswith("_"):
                    continue
                parts.append(f"{k}: {self._stringify(v)}")
            return "\n".join(parts)
        return f"{key}: {self._stringify(entry)}"

    @staticmethod
    def _stringify(v):
        if isinstance(v, (list, tuple)):
            return "、".join(str(x) for x in v)
        return str(v)
