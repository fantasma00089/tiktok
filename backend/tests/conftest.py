import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repost_monitor.config import Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.load(
        env_file=tmp_path / "inexistente.env",
        overrides={
            "TIKTOK_USERNAME": "alvo_teste",
            "PROVIDER": "mock",
            "MOCK_FILE": str(tmp_path / "mock.json"),
            "DATA_DIR": str(tmp_path / "data"),
            "LOG_DIR": str(tmp_path / "logs"),
            "DESKTOP_NOTIFICATIONS": "false",
            "RETRY_BASE_DELAY_SECONDS": "0",
            "NETLIFY_SITE_DIR": str(tmp_path / "site"),
        },
    )
