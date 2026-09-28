"""Provedor de simulação: lê os reposts de um arquivo JSON local.

Útil para testar o fluxo completo sem API. Use `python -m repost_monitor simulate`
para acrescentar um repost falso ao arquivo e ver a notificação chegar.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from ..http import ProviderError
from ..models import Repost, iso, utcnow, video_url
from .base import RepostProvider, normalize_items


class MockProvider(RepostProvider):
    name = "mock"

    async def fetch_reposts(self) -> list[Repost]:
        path: Path = self.options["file"]
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Arquivo de simulação inválido ({path}): {exc}") from exc
        return normalize_items(data)


def add_fake_repost(path: Path, author: str = "criador_exemplo") -> dict:
    """Insere um repost falso no topo do arquivo de simulação e o retorna."""
    items = []
    if path.exists():
        items = json.loads(path.read_text(encoding="utf-8") or "[]")
    item_id = str(7_400_000_000_000_000_000 + random.randint(0, 10**17))
    item = {
        "id": item_id,
        "author": author,
        "desc": f"Vídeo de teste #{len(items) + 1}",
        "url": video_url(item_id, author),
        "create_time": iso(utcnow()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item] + items, ensure_ascii=False, indent=2), encoding="utf-8")
    return item
