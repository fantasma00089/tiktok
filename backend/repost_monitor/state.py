"""Persistência do estado do monitor em JSON (escrita atômica)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import Repost

log = logging.getLogger(__name__)

MAX_DETECTIONS = 50


@dataclass
class MonitorState:
    target: str = ""               # @ ou user_id monitorado quando o estado foi criado
    initialized: bool = False      # já fizemos a leitura de base (baseline)?
    last_item_id: str | None = None  # ID do repost mais recente conhecido (RF-04)
    seen_ids: list[str] = field(default_factory=list)  # mais recente primeiro
    detections: list[dict[str, Any]] = field(default_factory=list)  # mais recente primeiro
    last_check_at: str | None = None
    last_success_at: str | None = None
    next_check_at: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    total_checks: int = 0

    @property
    def latest_detection(self) -> Repost | None:
        return Repost.from_dict(self.detections[0]) if self.detections else None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MonitorState":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class StateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self, target: str) -> MonitorState:
        if self.path.exists():
            try:
                state = MonitorState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError) as exc:
                backup = self.path.with_suffix(".corrompido.json")
                log.error("Estado corrompido (%s); movido para %s e recriado.", exc, backup)
                self.path.replace(backup)
            else:
                if state.target == target:
                    return state
                log.warning("Alvo mudou de %s para %s: estado reiniciado.", state.target, target)
        return MonitorState(target=target)

    def save(self, state: MonitorState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state.to_dict(), fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
