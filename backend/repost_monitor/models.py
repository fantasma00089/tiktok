"""Estruturas de dados compartilhadas entre os módulos."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if dt else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def video_url(item_id: str, author: str | None = None) -> str:
    # Sem o @ do autor o TikTok ainda resolve o vídeo pelo ID em /@/video/<id>.
    return f"https://www.tiktok.com/@{author or ''}/video/{item_id}"


@dataclass
class Repost:
    """Um vídeo que aparece na aba de reposts do perfil monitorado."""

    item_id: str
    url: str
    author: str | None = None
    description: str | None = None
    cover_url: str | None = None
    created_at: str | None = None  # data de publicação do vídeo original, se a API informar
    detected_at: str | None = None  # preenchido quando o monitor detecta o repost

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Repost":
        known = {k: data.get(k) for k in cls.__dataclass_fields__}
        known["item_id"] = str(known["item_id"])
        return cls(**known)
