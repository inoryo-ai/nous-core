"""NOUS Runtime — multi-agent platform layer.

Hosts heterogeneous agents (LLM-based, knowledge-based, hybrid) on a shared
runtime with episodic memory and inter-agent messaging.

Core abstractions:
  - Agent: generic agent with execute(task, context) -> AgentResult
  - NousRuntime: registers agents and orchestrates execution
  - Hippocampus: shared episodic memory (Hopfield-based)
  - MessageBus: pub/sub for agent coordination
"""
from .agent import Agent, AgentResult
from .coordinator import NousRuntime
from .hippocampus import Hippocampus
from .messaging import MessageBus, Message

__all__ = [
    'Agent', 'AgentResult',
    'NousRuntime',
    'Hippocampus',
    'MessageBus', 'Message',
]
