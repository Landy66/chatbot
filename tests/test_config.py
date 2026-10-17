"""Tests für das Konfigurationsmodul (AC-01, AC-02, AC-11)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from ai_assistant.config import Settings, load_settings


def test_default_settings() -> None:
    """Prüft, ob Standardwerte aus PRD korrekt gesetzt werden."""
    settings = Settings(_env_file=None)
    assert settings.openai_model == "gpt-5-mini"
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 7860
    assert settings.max_input_chars == 8000
    assert settings.max_context_turns == 20
    assert settings.max_context_chars == 80000
    assert settings.max_ui_turns == 100
    assert settings.max_output_tokens == 4096
    assert settings.run_timeout_seconds == 120.0
    assert settings.max_retries == 2
    assert settings.max_concurrent_runs == 4
    assert settings.max_queue_size == 16


def test_secret_redaction_in_repr() -> None:
    """Stellt sicher, dass das API-Secret nicht im repr() von Settings erscheint."""
    secret = "sk-super-secret-api-key-test"
    settings = Settings(_env_file=None, openai_api_key=SecretStr(secret))
    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert "**********" in repr(settings)


def test_load_settings_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prüft, ob load_settings bei fehlendem Key eine verständliche Exception wirft."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY ist nicht gesetzt oder leer"):
        load_settings(require_api_key=True, env_file=None)


def test_invalid_log_level() -> None:
    """Prüft, ob ungültige Log-Levels abgelehnt werden."""
    with pytest.raises(ValueError, match="Ungültiges Log-Level"):
        Settings(log_level="INVALID")


def test_gemini_settings_and_autodetect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prüft, ob Gemini-Provider-Konfiguration und automatische Erkennung funktionieren."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestGeminiKey123")
    settings = load_settings(require_api_key=True, env_file=None)
    assert settings.llm_provider == "google"
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_api_key.get_secret_value() == "AIzaSyTestGeminiKey123"


def test_gemini_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prüft, ob fehlender GEMINI_API_KEY bei explizitem Google-Provider gemeldet wird."""
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY ist nicht gesetzt oder leer"):
        load_settings(require_api_key=True, env_file=None)


def test_groq_settings_and_autodetect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prüft, ob Groq-Provider-Konfiguration und automatische Erkennung funktionieren."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test1234567890abcdef")
    settings = load_settings(require_api_key=True, env_file=None)
    assert settings.llm_provider == "groq"
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.groq_api_key.get_secret_value() == "gsk_test1234567890abcdef"


def test_groq_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prüft, ob fehlender GROQ_API_KEY bei explizitem Groq-Provider gemeldet wird."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY ist nicht gesetzt oder leer"):
        load_settings(require_api_key=True, env_file=None)
