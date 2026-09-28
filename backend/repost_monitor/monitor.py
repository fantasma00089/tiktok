"""Orquestra um ciclo de polling: consulta → detecção → notificação → publicação."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import httpx

from .config import Settings
from .detector import detect_new_reposts
from .events import EventBus
from .http import ProviderError, RateLimitError
from .logging_setup import log_detection
from .models import Repost, iso, utcnow
from .notifiers import notify_local
from .providers import RepostProvider, build_provider
from .publishers import NetlifyPublisher, send_webhook
from .state import MonitorState, StateStore
from .status import build_status

log = logging.getLogger(__name__)


@dataclass
class CycleResult:
    ok: bool
    new_reposts: list[Repost] = field(default_factory=list)
    fetched: int = 0
    error: str | None = None
    retry_after: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "novos_reposts": [r.to_dict() for r in self.new_reposts],
            "itens_consultados": self.fetched,
            "erro": self.error,
        }


class Monitor:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None,
                 provider: RepostProvider | None = None, bus: EventBus | None = None,
                 notify: bool = True):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            headers={"User-Agent": "tiktok-repost-monitor/1.0"}, follow_redirects=True
        )
        self.provider = provider or build_provider(settings, self.client)
        self.bus = bus or EventBus()
        self.notify = notify
        self.store = StateStore(settings.state_file)
        self.state: MonitorState = self.store.load(settings.state_key)
        self.running = False
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self.netlify: NetlifyPublisher | None = None
        if settings.netlify_auth_token and settings.netlify_site_id:
            self.netlify = NetlifyPublisher(settings, self.client, self.status)

    def status(self) -> dict[str, Any]:
        return build_status(self.settings, self.state, running=self.running)

    async def run_cycle(self) -> CycleResult:
        async with self._lock:
            result = await self._cycle()
            self.bus.publish("status", self.status())
            return result

    async def _cycle(self) -> CycleResult:
        state = self.state
        state.last_check_at = iso(utcnow())
        state.total_checks += 1
        try:
            fetched = await self.provider.fetch_reposts()
        except (ProviderError, httpx.HTTPError, ValueError) as exc:
            state.consecutive_failures += 1
            state.last_error = str(exc)
            self.store.save(state)
            log.error("Falha ao consultar reposts (%d seguida(s)): %s", state.consecutive_failures, exc)
            return CycleResult(ok=False, error=str(exc), retry_after=getattr(exc, "retry_after", None))

        first_run = not state.initialized
        new = detect_new_reposts(
            state, fetched,
            baseline_on_first_run=self.settings.baseline_on_first_run,
            max_seen_ids=self.settings.max_seen_ids,
        )
        state.consecutive_failures = 0
        state.last_error = None
        state.last_success_at = state.last_check_at
        self.store.save(state)

        if first_run and fetched:
            log.info("Leitura de base: %d repost(s) existentes de %s registrados (sem alerta).",
                     len(fetched), self.settings.target_label)
        if new:
            await self._on_new_reposts(new)
        else:
            log.info("Nenhum repost novo de %s (%d itens consultados).", self.settings.target_label, len(fetched))
        return CycleResult(ok=True, new_reposts=new, fetched=len(fetched))

    async def _on_new_reposts(self, new: list[Repost]) -> None:
        for repost in new:
            log.info("REPOST DETECTADO: %s repostou %s", self.settings.target_label, repost.url)
            log_detection(self.settings.detections_log, self.settings.target_label, repost)
        self.bus.publish("repost", {"reposts": [r.to_dict() for r in new]})
        if self.netlify:
            self.netlify.request_publish()
        tasks = []
        if self.notify:
            tasks.append(notify_local(self.settings, new))
        if self.settings.webhook_url:
            tasks.append(send_webhook(self.settings, self.client, self.status()))
        for outcome in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(outcome, Exception):
                log.error("Falha em ação pós-detecção: %s", outcome)

    def next_delay(self, result: CycleResult) -> float:
        """Intervalo até o próximo ciclo, com jitter e backoff exponencial em falhas."""
        base = float(self.settings.poll_interval)
        if not result.ok:
            base = min(self.settings.max_backoff, base * 2 ** min(self.state.consecutive_failures - 1, 6))
            if result.retry_after:
                base = max(base, result.retry_after)
        return max(5.0, base + random.uniform(-self.settings.poll_jitter, self.settings.poll_jitter))

    def check_now(self) -> None:
        """Acorda o loop para verificar imediatamente."""
        self._wake.set()

    async def run_forever(self) -> None:
        self.running = True
        log.info("Monitorando reposts de %s via provedor '%s' a cada ~%ss.",
                 self.settings.target_label, self.provider.name, self.settings.poll_interval)
        if self.settings.is_simulation:
            log.warning("MODO SIMULAÇÃO (PROVIDER=mock): o TikTok NÃO está sendo consultado; "
                        "reposts reais não aparecem. Configure PROVIDER=apify e APIFY_TOKEN no backend/.env.")
        netlify_task = asyncio.create_task(self.netlify.run()) if self.netlify else None
        if self.netlify:
            self.netlify.request_publish()  # publica o estado inicial
        try:
            while True:
                self._wake.clear()
                result = await self.run_cycle()
                delay = self.next_delay(result)
                self.state.next_check_at = iso(utcnow() + timedelta(seconds=delay))
                self.store.save(self.state)
                self.bus.publish("status", self.status())
                self._maybe_heartbeat()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    log.info("Verificação imediata solicitada.")
                except asyncio.TimeoutError:
                    pass
        finally:
            self.running = False
            if netlify_task:
                netlify_task.cancel()

    def _maybe_heartbeat(self) -> None:
        minutes = self.settings.netlify_heartbeat_minutes
        if self.netlify and minutes > 0 and time.monotonic() - self.netlify.last_publish_monotonic >= minutes * 60:
            self.netlify.request_publish()

    async def aclose(self) -> None:
        await self.client.aclose()
