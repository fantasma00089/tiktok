"""Configuração de logs: console + arquivo rotativo, e log de detecções em JSONL."""

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .models import Repost

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_dir: Path, level: str = "INFO", console_stream=None) -> None:
    """`console_stream` padrão é stderr; em pythonw.exe (sem console) ele é None e é ignorado."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stream = console_stream or sys.stderr
    if stream is not None:
        console = logging.StreamHandler(stream)
        console.setFormatter(logging.Formatter(FORMAT, "%H:%M:%S"))
        root.addHandler(console)
    file_handler = RotatingFileHandler(log_dir / "monitor.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(file_handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_detection(path: Path, target: str, repost: Repost) -> None:
    """RF-05: registra timestamp, @ monitorado e URL do vídeo, uma linha JSON por repost."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": repost.detected_at,
        "monitorado": target,
        "item_id": repost.item_id,
        "url": repost.url,
        "autor_video": repost.author,
        "descricao": repost.description,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
