"""Configuração do monitor, lida de variáveis de ambiente e de um arquivo `.env`.

Não dependemos de python-dotenv: o parser abaixo cobre o formato KEY=VALUE
usado no `.env.example`. Variáveis já definidas no ambiente têm prioridade.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

MIN_POLL_INTERVAL = 30  # segundos; abaixo disso o risco de bloqueio/rate-limit é alto


def load_dotenv(path: Path) -> dict[str, str]:
    """Lê um arquivo .env simples (KEY=VALUE, comentários com #)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif value.startswith("#"):
            value = ""  # só comentário após o "="
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _json(value: str | None, default: Any) -> Any:
    if value is None or value.strip() == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido na configuração: {value!r} ({exc})") from exc


def _path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    p = Path(value).expanduser()
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


@dataclass
class Settings:
    # Alvo
    username: str = ""
    user_id: str = ""

    # Provedor de dados
    provider: str = "mock"
    provider_options: dict[str, Any] = field(default_factory=dict)

    # Polling e resiliência
    poll_interval: int = 180
    poll_jitter: int = 15
    max_backoff: int = 1800
    http_timeout: int = 30
    retry_attempts: int = 3
    retry_base_delay: float = 2.0

    # Detecção / exibição
    alert_window_minutes: int = 60
    baseline_on_first_run: bool = True
    max_seen_ids: int = 500

    # Servidor local
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    admin_token: str = ""

    # Notificações locais
    desktop_notifications: bool = True
    open_browser_on_repost: bool = False

    # Publicação (webhook reverso)
    netlify_auth_token: str = ""
    netlify_site_id: str = ""
    netlify_site_dir: Path = PROJECT_DIR / "site"
    netlify_min_interval: int = 60
    netlify_heartbeat_minutes: int = 0
    webhook_url: str = ""
    webhook_secret: str = ""

    # Arquivos
    data_dir: Path = BACKEND_DIR / "data"
    log_dir: Path = BACKEND_DIR / "logs"
    log_level: str = "INFO"

    @property
    def state_file(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def detections_log(self) -> Path:
        return self.log_dir / "reposts.jsonl"

    @property
    def target_label(self) -> str:
        if self.username:
            return f"@{self.username}"
        return f"user_id {self.user_id}" if self.user_id else "(não configurado)"

    def validate(self) -> list[str]:
        problems = []
        if not self.username and not self.user_id:
            problems.append("Defina TIKTOK_USERNAME ou TIKTOK_USER_ID.")
        if self.provider not in {"mock", "http", "apify", "tiktok_research"}:
            problems.append(f"PROVIDER desconhecido: {self.provider!r}")
        if bool(self.netlify_auth_token) != bool(self.netlify_site_id):
            problems.append("NETLIFY_AUTH_TOKEN e NETLIFY_SITE_ID devem ser definidos juntos.")
        return problems

    @classmethod
    def load(cls, env_file: Path | None = None, overrides: dict[str, str] | None = None) -> "Settings":
        env: dict[str, str] = {}
        env.update(load_dotenv(env_file or BACKEND_DIR / ".env"))
        env.update(os.environ)
        env.update(overrides or {})
        g = env.get

        provider = (g("PROVIDER") or "mock").strip().lower()
        s = cls(
            username=(g("TIKTOK_USERNAME") or "").strip().lstrip("@"),
            user_id=(g("TIKTOK_USER_ID") or "").strip(),
            provider=provider,
            poll_interval=max(MIN_POLL_INTERVAL, _int(g("POLL_INTERVAL_SECONDS"), 180)),
            poll_jitter=max(0, _int(g("POLL_JITTER_SECONDS"), 15)),
            max_backoff=_int(g("MAX_BACKOFF_SECONDS"), 1800),
            http_timeout=_int(g("HTTP_TIMEOUT_SECONDS"), 30),
            retry_attempts=max(1, _int(g("RETRY_ATTEMPTS"), 3)),
            retry_base_delay=float(g("RETRY_BASE_DELAY_SECONDS") or 2.0),
            alert_window_minutes=_int(g("ALERT_WINDOW_MINUTES"), 60),
            baseline_on_first_run=_bool(g("BASELINE_ON_FIRST_RUN"), True),
            max_seen_ids=_int(g("MAX_SEEN_IDS"), 500),
            host=g("HOST") or "127.0.0.1",
            port=_int(g("PORT"), 8000),
            cors_origins=[o.strip() for o in (g("CORS_ORIGINS") or "*").split(",") if o.strip()],
            admin_token=g("ADMIN_TOKEN") or "",
            desktop_notifications=_bool(g("DESKTOP_NOTIFICATIONS"), True),
            open_browser_on_repost=_bool(g("OPEN_BROWSER_ON_REPOST"), False),
            netlify_auth_token=g("NETLIFY_AUTH_TOKEN") or "",
            netlify_site_id=g("NETLIFY_SITE_ID") or "",
            netlify_site_dir=_path(g("NETLIFY_SITE_DIR"), PROJECT_DIR / "site"),
            netlify_min_interval=_int(g("NETLIFY_MIN_INTERVAL_SECONDS"), 60),
            netlify_heartbeat_minutes=_int(g("NETLIFY_HEARTBEAT_MINUTES"), 0),
            webhook_url=g("WEBHOOK_URL") or "",
            webhook_secret=g("WEBHOOK_SECRET") or "",
            data_dir=_path(g("DATA_DIR"), BACKEND_DIR / "data"),
            log_dir=_path(g("LOG_DIR"), BACKEND_DIR / "logs"),
            log_level=(g("LOG_LEVEL") or "INFO").upper(),
        )
        s.provider_options = _provider_options(provider, g)
        return s


def _provider_options(provider: str, g) -> dict[str, Any]:
    if provider == "http":
        return {
            "url": g("HTTP_API_URL") or "",
            "method": (g("HTTP_API_METHOD") or "GET").upper(),
            "headers": _json(g("HTTP_API_HEADERS"), {}),
            "body": _json(g("HTTP_API_BODY"), None),
            "items_path": g("HTTP_API_ITEMS_PATH") or "",
            "id_field": g("HTTP_API_ID_FIELD") or "",
            "url_field": g("HTTP_API_URL_FIELD") or "",
            "author_field": g("HTTP_API_AUTHOR_FIELD") or "",
            "description_field": g("HTTP_API_DESCRIPTION_FIELD") or "",
            "cover_field": g("HTTP_API_COVER_FIELD") or "",
        }
    if provider == "apify":
        return {
            "token": g("APIFY_TOKEN") or "",
            "actor": g("APIFY_ACTOR") or "",
            "input": _json(g("APIFY_INPUT"), None),
            "items_path": g("APIFY_ITEMS_FILTER_PATH") or "",
        }
    if provider == "tiktok_research":
        return {
            "client_key": g("TIKTOK_CLIENT_KEY") or "",
            "client_secret": g("TIKTOK_CLIENT_SECRET") or "",
            "fields": g("TIKTOK_RESEARCH_FIELDS") or "id,create_time",
            "max_count": _int(g("TIKTOK_RESEARCH_MAX_COUNT"), 20),
        }
    if provider == "mock":
        return {"file": _path(g("MOCK_FILE"), BACKEND_DIR / "data" / "mock_reposts.json")}
    return {}
