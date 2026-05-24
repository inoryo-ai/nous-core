"""nous-core: LLM-free cognitive engine.

Public API re-exports. These conditional imports populate the namespace
as the library's optional modules become available.
"""

__version__ = "0.1.0"

from nous.knowledge import KnowledgeStore

__all__ = ["KnowledgeStore"]

try:
    from nous.language import LanguageEngine  # noqa: F401
    __all__.append("LanguageEngine")
except ImportError:
    pass

try:
    from nous.bookshelf import Book, BookShelf  # noqa: F401
    __all__.extend(["Book", "BookShelf"])
except ImportError:
    pass

try:
    from nous.brain import Brain, Response  # noqa: F401
    __all__.extend(["Brain", "Response"])
except ImportError:
    pass
