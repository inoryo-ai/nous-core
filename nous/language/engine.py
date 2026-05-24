"""LanguageEngine — natural language → structured intent.

Bilingual (Japanese + English). No neural networks. No external NLP libs.
Learns from user feedback via KnowledgeStore for pattern matching.

Pipeline:
    text -> tokenize -> match_pattern -> intent/target extraction
"""

import re


_STOP_EN = {
    "the", "a", "an", "is", "are", "was", "were", "to", "for", "of", "in", "on",
    "it", "that", "this", "with", "from", "can", "do", "be", "has", "have", "not",
    "but", "and", "or", "all", "every", "some", "any", "how", "what", "why",
    "when", "where", "who", "does", "did", "will", "would", "could", "should",
    "than", "then", "them", "they", "there", "these", "those", "very", "just",
    "about", "also", "each", "much", "many", "only", "into", "over", "after",
    "before", "between", "through", "during",
}

_STOP_JP = {
    "する", "して", "した", "です", "ます", "ない", "ある", "いる", "から", "まで",
    "ため", "こと", "もの", "それ", "これ", "あの", "その", "どの", "ところ",
    "ほう", "よう", "ように",
}

_INTENT_SIGNALS = {
    "prove":    {"prove", "proof", "demonstrate", "show", "why",
                 "証明", "示せ", "なぜ", "理由"},
    "solve":    {"solve", "compute", "calculate", "answer", "result",
                 "解く", "計算", "求め", "答え"},
    "discover": {"find", "discover", "pattern", "analyze", "explore", "search",
                 "見つけ", "発見", "パターン", "分析", "探す", "調べ"},
    "learn":    {"learn", "understand", "study", "teach", "explain",
                 "学ぶ", "理解", "勉強", "教え", "説明"},
    "create":   {"create", "build", "generate", "make", "design", "write",
                 "作る", "作成", "作って", "生成", "設計", "構築", "書く"},
    "ask":      {"what", "which", "how", "tell",
                 "何", "どう", "どれ", "教えて", "ですか", "知りたい"},
}


class LanguageEngine:
    """Parse natural-language input into {intent, target, keywords, confidence}."""

    def __init__(self, ks, wiki_patterns=None, jmdict_vocab=None):
        self.ks = ks
        self._pattern_count = self._count_existing_patterns()

        self._jp_nouns = set()
        self._jp_verbs = set()
        self._jp_vocab = set()
        self._jp_meanings = {}

        if wiki_patterns:
            self._load_wiki_patterns(wiki_patterns)
        if jmdict_vocab:
            self._load_jmdict(jmdict_vocab)

    # -------- loaders --------

    def _count_existing_patterns(self):
        n = 0
        for (c, _) in self.ks.facts:
            if c.startswith("lang_pattern_"):
                i = int(c.split("_")[-1])
                if i >= n:
                    n = i + 1
        return n

    def _load_wiki_patterns(self, patterns):
        def words(data):
            if isinstance(data, dict):
                return data.keys()
            if isinstance(data, list):
                return data
            return []

        for w in words(patterns.get("freq_noun", {})):
            if isinstance(w, str) and len(w) >= 2:
                self._jp_nouns.add(w)
                self._jp_vocab.add(w)
        for w in words(patterns.get("freq_verb", {})):
            if isinstance(w, str) and len(w) >= 2:
                self._jp_verbs.add(w)
                self._jp_vocab.add(w)
        for w in words(patterns.get("freq_adj", {})):
            if isinstance(w, str) and len(w) >= 2:
                self._jp_vocab.add(w)
        for key_set in ("noun_verb", "noun_noun"):
            for w in words(patterns.get(key_set, {})):
                clean = w.split("-")[0] if isinstance(w, str) else ""
                if len(clean) >= 2:
                    self._jp_nouns.add(clean)
                    self._jp_vocab.add(clean)
        for w in words(patterns.get("verb_object", {})):
            if isinstance(w, str) and len(w) >= 2:
                self._jp_verbs.add(w)
                self._jp_vocab.add(w)

    def _load_jmdict(self, vocab):
        for word, info in vocab.items():
            if len(word) < 2:
                continue
            self._jp_vocab.add(word)
            if info.get("meaning"):
                self._jp_meanings[word] = info["meaning"]
            pos = info.get("pos", [])
            if any(p == "n" or p.startswith("n-") for p in pos):
                self._jp_nouns.add(word)
            if any(p.startswith("v") for p in pos):
                self._jp_verbs.add(word)

    # -------- parsing --------

    def parse(self, text):
        """text -> {intent, target, keywords, confidence, matched_pattern}."""
        keywords = self.tokenize(text)
        best = self._match_known_pattern(keywords)

        if best and best["score"] > 0.5:
            return {
                "intent": best["intent"],
                "target": best["target"],
                "keywords": keywords,
                "confidence": best["score"],
                "matched_pattern": best["pattern_id"],
            }

        inferred = self._infer_intent(keywords, text)
        return {
            "intent": inferred["intent"],
            "target": inferred["target"],
            "keywords": keywords,
            "confidence": inferred["confidence"],
            "matched_pattern": None,
        }

    def learn_pattern(self, text, intent, target=None):
        """Learn: this text means this intent. Future parse() will match similar inputs."""
        keywords = self.tokenize(text)
        pid = f"lang_pattern_{self._pattern_count}"
        self._pattern_count += 1

        self.ks.store_fact(pid, "text", text)
        self.ks.store_fact(pid, "intent", intent)
        self.ks.store_fact(pid, "keywords", ",".join(keywords))
        if target:
            self.ks.store_fact(pid, "target", target)
        return pid

    # -------- tokenizer --------

    def tokenize(self, text):
        en_words = re.findall(r"[A-Za-z]{3,}", text)
        jp_words = self._tokenize_japanese(text)

        out = []
        seen = set()
        for w in en_words:
            lw = w.lower()
            if lw not in _STOP_EN and lw not in seen:
                out.append(lw)
                seen.add(lw)
        for w in jp_words:
            if w not in _STOP_JP and w not in seen:
                out.append(w)
                seen.add(w)
        return out

    def _tokenize_japanese(self, text):
        """Longest-match segmentation using loaded vocabulary."""
        spans = re.findall(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u30fc]+", text)
        if not self._jp_vocab:
            return [s for s in spans if len(s) >= 2]

        words = []
        for span in spans:
            i = 0
            while i < len(span):
                best = None
                for length in range(min(6, len(span) - i), 1, -1):
                    cand = span[i:i + length]
                    if cand in self._jp_vocab:
                        best = cand
                        break
                if best:
                    words.append(best)
                    i += len(best)
                else:
                    if i + 1 < len(span) and "\u4e00" <= span[i] <= "\u9fff":
                        words.append(span[i:i + 2])
                        i += 2
                    else:
                        i += 1
        return words

    # -------- pattern matching & intent inference --------

    def _match_known_pattern(self, keywords):
        patterns = {}
        for (c, p), v in self.ks.facts.items():
            if c.startswith("lang_pattern_") and p == "intent":
                patterns[c] = {"intent": v}
        if not patterns:
            return None

        for pid in patterns:
            kws = (self.ks.access(pid, "keywords") or "").split(",")
            patterns[pid]["keywords"] = kws
            patterns[pid]["target"] = self.ks.access(pid, "target")

        best_pid = None
        best_score = 0.0
        kw_set = set(keywords)
        for pid, info in patterns.items():
            pkws = set(info["keywords"])
            if not pkws:
                continue
            inter = kw_set & pkws
            union = kw_set | pkws
            score = len(inter) / len(union) if union else 0.0
            if score > best_score:
                best_score = score
                best_pid = pid

        if best_pid and best_score > 0:
            return {
                "pattern_id": best_pid,
                "intent": patterns[best_pid]["intent"],
                "target": patterns[best_pid].get("target", ""),
                "score": round(best_score, 4),
            }
        return None

    def _infer_intent(self, keywords, text):
        text_lower = text.lower()
        kw_set = set(keywords)

        best_intent = "general"
        best_score = 0
        for intent, signals in _INTENT_SIGNALS.items():
            score = len(kw_set & signals)
            for sig in signals:
                if sig in text_lower:
                    score += 1
            if score > best_score:
                best_score = score
                best_intent = intent

        all_signals = set()
        for signals in _INTENT_SIGNALS.values():
            all_signals |= signals
        target_candidates = [kw for kw in keywords if kw not in all_signals]
        target = target_candidates[0] if target_candidates else ""

        confidence = min(0.3 + best_score * 0.15, 0.8) if best_score > 0 else 0.1
        return {"intent": best_intent, "target": target, "confidence": confidence}

    # -------- stats --------

    def pattern_count(self):
        pids = set(c for (c, _) in self.ks.facts if c.startswith("lang_pattern_"))
        return len(pids)

    def vocab_count(self):
        return len(self._jp_vocab)

    def summary(self):
        return (f"LanguageEngine: {self.pattern_count()} patterns, "
                f"{self.vocab_count()} JP words")
