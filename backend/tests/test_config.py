from repost_monitor.config import MIN_POLL_INTERVAL, Settings, load_dotenv


def test_dotenv_parsing(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comentário\n"
        "TIKTOK_USERNAME=@fulano   # com arroba\n"
        "ADMIN_TOKEN=                # vazio com comentário\n"
        'HTTP_API_HEADERS={"X-Key": "a#b"}\n'
        "QUOTED='valor # não é comentário'\n"
        "export PORT=9000\n",
        encoding="utf-8",
    )
    values = load_dotenv(env)
    assert values["TIKTOK_USERNAME"] == "@fulano"
    assert values["ADMIN_TOKEN"] == ""
    assert values["HTTP_API_HEADERS"] == '{"X-Key": "a#b"}'
    assert values["QUOTED"] == "valor # não é comentário"
    assert values["PORT"] == "9000"


def test_settings_normalization(tmp_path):
    s = Settings.load(tmp_path / "x.env", {"TIKTOK_USERNAME": "@fulano", "POLL_INTERVAL_SECONDS": "5",
                                           "CORS_ORIGINS": "https://a.netlify.app, https://b.app"})
    assert s.username == "fulano"
    assert s.target_label == "@fulano"
    assert s.poll_interval == MIN_POLL_INTERVAL
    assert s.cors_origins == ["https://a.netlify.app", "https://b.app"]
    assert s.validate() == []


def test_validation_errors(tmp_path):
    s = Settings.load(tmp_path / "x.env", {"TIKTOK_USERNAME": "", "PROVIDER": "xyz", "NETLIFY_SITE_ID": "abc"})
    assert len(s.validate()) == 3


def test_example_env_file_loads_cleanly():
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / ".env.example"
    s = Settings.load(example, {})
    assert s.admin_token == "" and s.webhook_url == "" and s.netlify_auth_token == ""
    assert s.poll_interval == 180 and s.host == "127.0.0.1" and s.validate() == []
