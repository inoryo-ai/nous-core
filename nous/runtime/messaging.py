"""MessageBus — pub/sub for inter-agent coordination."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    channel: str
    payload: Any
    sender: str | None = None
    timestamp: float = field(default_factory=time.time)


class MessageBus:
    """Lightweight pub/sub. Single-threaded MVP."""

    def __init__(self) -> None:
        self._queues: dict[str, deque[Message]] = defaultdict(deque)
        self._subs: dict[str, set[str]] = defaultdict(set)

    def subscribe(self, subscriber: str, channel: str) -> None:
        self._subs[subscriber].add(channel)

    def unsubscribe(self, subscriber: str, channel: str) -> None:
        self._subs[subscriber].discard(channel)

    def publish(self, channel: str, payload: Any,
                sender: str | None = None) -> None:
        self._queues[channel].append(
            Message(channel=channel, payload=payload, sender=sender))

    def drain(self, channel: str) -> list[Message]:
        msgs = list(self._queues[channel])
        self._queues[channel].clear()
        return msgs

    def drain_for(self, subscriber: str) -> list[Message]:
        out: list[Message] = []
        for ch in list(self._subs.get(subscriber, ())):
            out.extend(self.drain(ch))
        return out

    def peek_for(self, subscriber: str) -> list[Message]:
        out: list[Message] = []
        for ch in list(self._subs.get(subscriber, ())):
            out.extend(self._queues[ch])
        return out

    def clear(self) -> None:
        self._queues.clear()

    def channel_size(self, channel: str) -> int:
        return len(self._queues.get(channel, ()))
