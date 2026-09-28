"""Barramento simples de eventos para o Server-Sent Events do painel local."""

from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._queues.discard(queue)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        for queue in list(self._queues):
            if queue.full():  # cliente lento: descarta o evento mais antigo
                queue.get_nowait()
            queue.put_nowait((event, data))
