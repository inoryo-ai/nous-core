"""NOUS agents — concrete agent implementations on the runtime.

Modules:
  - llm: LLMAgent base + LLM wrapper (requires openai)
  - knowledge: KnowledgeAgent (uses BookShelf for retrieval)
  - marketing: 9-agent marketing team (Commander + 8 specialists)
"""
from .llm import LLMAgent

__all__ = ['LLMAgent']

# Marketing team is optional (depends on prompts module)
try:
    from . import marketing  # noqa: F401
    __all__.append('marketing')
except ImportError:
    pass

# KnowledgeAgent depends on bookshelf
try:
    from .knowledge import KnowledgeAgent  # noqa: F401
    __all__.append('KnowledgeAgent')
except ImportError:
    pass

# StudentAssistantAgent (BookShelf + LLM hybrid)
try:
    from .student_assistant import StudentAssistantAgent  # noqa: F401
    __all__.append('StudentAssistantAgent')
except ImportError:
    pass
