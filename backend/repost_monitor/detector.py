"""Detecção de novos reposts comparando a lista atual com os IDs já vistos."""

from __future__ import annotations

from .models import Repost, iso, utcnow
from .state import MAX_DETECTIONS, MonitorState


def detect_new_reposts(
    state: MonitorState,
    fetched: list[Repost],
    *,
    baseline_on_first_run: bool = True,
    max_seen_ids: int = 500,
) -> list[Repost]:
    """Atualiza `state` e devolve os reposts novos (mais recente primeiro).

    - Na primeira leitura (sem estado), os reposts existentes viram a "base" e
      não geram alerta, a menos que baseline_on_first_run=False.
    - Um item é novo se o ID nunca foi visto. Guardamos um conjunto de IDs (e
      não só o último) porque a ordem da lista pode variar entre chamadas e
      um repost desfeito não deve fazer o anterior "reaparecer" como novo.
    - Lista vazia não altera nada (pode ser falha momentânea da API).
    """
    if not fetched:
        return []

    seen = set(state.seen_ids)
    new = [r for r in fetched if r.item_id not in seen]

    if not state.initialized:
        state.initialized = True
        if baseline_on_first_run:
            new = []

    now = iso(utcnow())
    for repost in new:
        repost.detected_at = now

    fetched_ids = [r.item_id for r in fetched]
    merged = fetched_ids + [i for i in state.seen_ids if i not in set(fetched_ids)]
    state.seen_ids = merged[:max_seen_ids]
    state.last_item_id = fetched[0].item_id

    if new:
        state.detections = [r.to_dict() for r in new] + state.detections
        del state.detections[MAX_DETECTIONS:]
    return new
