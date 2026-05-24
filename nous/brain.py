"""Brain — top-level integrated entry point for nous-core.

Provides the public API that clients use:
    brain = Brain()
    brain.load_book("manual", "path/to/manual.json")
    response = brain.ask("有給は何日？")

Plugins may be registered to hook into the ask() pipeline. A plugin may
implement any subset of these callbacks (duck-typed, no base class needed):

    before_parse(text)               -> text
    after_parse(parsed)              -> parsed
    before_search(query)             -> query
    after_search(match)              -> match | None
    before_compose(intent, match)    -> (intent, match)
    after_compose(response)          -> response

Plugins run in registration order. Missing callbacks are skipped.
"""

from dataclasses import dataclass, field

from nous.knowledge import KnowledgeStore
from nous.language import LanguageEngine
from nous.bookshelf import BookShelf
from nous.curator import Curator
from nous.dialogue import DialogueManager, ResponseComposer


@dataclass
class Response:
    """One answer from the Brain. Fully traceable."""
    text: str
    intent: str
    source_book: str = ""
    source_key: str = ""
    confidence: float = 0.0
    keywords: list = field(default_factory=list)
    used_fallback: bool = False

    def trace(self):
        """Return auditing trace: where this answer came from."""
        return {
            "intent": self.intent,
            "source_book": self.source_book,
            "source_key": self.source_key,
            "confidence": self.confidence,
            "keywords": list(self.keywords),
            "used_fallback": self.used_fallback,
        }


class Brain:
    """Integrated cognitive engine: knowledge + language + books + dialogue."""

    def __init__(self, wiki_patterns=None, jmdict_vocab=None):
        self.ks = KnowledgeStore()
        self.shelf = BookShelf()
        self.language = LanguageEngine(
            self.ks, wiki_patterns=wiki_patterns, jmdict_vocab=jmdict_vocab
        )
        self.curator = Curator(self.shelf, self.ks)
        self.dialogue = DialogueManager()
        self.composer = ResponseComposer()
        self._plugins = []

    # --- Plugin system ---

    def register(self, plugin):
        """Attach a plugin. Plugins run in registration order.

        Accepts any object; callbacks are invoked only if defined.
        Returns the plugin for chaining.
        """
        self._plugins.append(plugin)
        return plugin

    def unregister(self, plugin):
        """Remove a previously registered plugin. Silent if not found."""
        try:
            self._plugins.remove(plugin)
        except ValueError:
            pass

    def plugins(self):
        """Return the current plugin list (copy)."""
        return list(self._plugins)

    def _run_hook(self, hook_name, value):
        """Pipe `value` through every plugin's `hook_name` that exists."""
        for p in self._plugins:
            fn = getattr(p, hook_name, None)
            if callable(fn):
                value = fn(value)
        return value

    # --- Knowledge management ---

    def load_book(self, name, path, schema=None, writable=False):
        """Register a JSON knowledge book. Returns the Book instance."""
        return self.shelf.load_book(name, path, schema=schema, writable=writable)

    def books(self):
        """List registered book names."""
        return self.shelf.names()

    def teach(self, concept, prop, value, conf=1.0):
        """Directly add a fact to knowledge store."""
        return self.ks.store_fact(concept, prop, value, conf=conf)

    def learn_pattern(self, text, intent, target=None):
        """Teach the language engine that this text maps to this intent."""
        return self.language.learn_pattern(text, intent, target=target)

    # --- Conversation ---

    def ask(self, text, books=None):
        """Main entry: answer a natural-language question.

        Pipeline:
            text
              → before_parse
              → language.parse
              → after_parse
              → dialogue reference resolution
              → before_search
              → curator.best_match
              → after_search
              → before_compose
              → composer.compose
              → Response construction
              → after_compose
        """
        text = self._run_hook("before_parse", text)

        parsed = self.language.parse(text)
        parsed = self._run_hook("after_parse", parsed)

        reference = self.dialogue.resolve_reference(text)
        search_query = f"{reference} {text}" if reference else text
        search_query = self._run_hook("before_search", search_query)

        match = self.curator.best_match(search_query, books=books)
        match = self._run_hook("after_search", match)

        intent = parsed["intent"]
        for p in self._plugins:
            fn = getattr(p, "before_compose", None)
            if callable(fn):
                intent, match = fn(intent, match)

        response_text = self.composer.compose(text, intent, match)

        topic = match["key"] if match else parsed.get("target", "")
        self.dialogue.record(text, intent, topic, response_text)

        response = Response(
            text=response_text,
            intent=intent,
            source_book=match["book"] if match else "",
            source_key=match["key"] if match else "",
            confidence=match["score"] if match else 0.0,
            keywords=parsed["keywords"],
            used_fallback=match is None,
        )

        return self._run_hook("after_compose", response)

    def chat(self, text, books=None):
        """Alias for ask() with dialogue context. Returns Response."""
        return self.ask(text, books=books)

    def clear_conversation(self):
        """Clear dialogue history."""
        self.dialogue.clear()

    # --- Introspection ---

    def summary(self):
        return {
            "books": self.shelf.names(),
            "book_count": len(self.shelf),
            "fact_count": self.ks.fact_count(),
            "pattern_count": self.language.pattern_count(),
            "dialogue_turns": len(self.dialogue.history()),
            "plugin_count": len(self._plugins),
        }
