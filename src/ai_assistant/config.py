"""Konfigurationsmodul für den KI-Assistenten mit Pydantic Settings."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Zentrale Konfiguration der Anwendung.

    Liest Werte aus Umgebungsvariablen und optional einer .env-Datei.
    Führt keine Netzwerk- oder API-Aufrufe beim Import durch.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API Key (Secret)",
    )
    openai_model: str = Field(
        default="gpt-5-mini",
        description="Name des zu verwendenden OpenAI-Modells",
    )
    llm_provider: str = Field(
        default="openai",
        description="Modellanbieter: 'openai', 'google' oder 'groq'",
    )
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Google Gemini API Key (Secret)",
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash",
        description="Name des zu verwendenden Gemini-Modells",
    )
    groq_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Groq API Key (Secret)",
    )
    groq_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Name des zu verwendenden Groq-Modells",
    )
    app_host: str = Field(
        default="127.0.0.1",
        description="Lokaler Host für die Web-Oberfläche",
    )
    app_port: int = Field(
        default=7860,
        description="Lokaler Port für die Web-Oberfläche",
    )
    log_level: str = Field(
        default="INFO",
        description="Log-Level (DEBUG, INFO, WARNING, ERROR)",
    )
    max_input_chars: int = Field(
        default=8000,
        description="Maximale Zeichenlänge der Nutzereingabe",
        gt=0,
    )
    max_context_turns: int = Field(
        default=20,
        description="Maximale Anzahl vollständiger Frage-Antwort-Runden im Modellkontext",
        gt=0,
    )
    max_context_chars: int = Field(
        default=80000,
        description="Maximale Zeichenanzahl für gespeicherte Textinhalte im Modellkontext",
        gt=0,
    )
    max_ui_turns: int = Field(
        default=100,
        description="Maximale Anzahl Runden in der UI-Anzeige",
        gt=0,
    )
    max_output_tokens: int = Field(
        default=4096,
        description="Maximales Tokenbudget für Antworten",
        gt=0,
    )
    run_timeout_seconds: float = Field(
        default=120.0,
        description="Gesamttimeout für einen Modelllauf in Sekunden",
        gt=0,
    )
    max_retries: int = Field(
        default=2,
        description="Maximale Retries vor erstem sichtbaren Chunk",
        ge=0,
    )
    max_concurrent_runs: int = Field(
        default=4,
        description="Prozessweite Begrenzung gleichzeitiger Läufe",
        gt=0,
    )
    max_queue_size: int = Field(
        default=16,
        description="Maximale Queue-Größe für wartende Anfragen",
        gt=0,
    )

    VALID_LOG_LEVELS: ClassVar[set[str]] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in cls.VALID_LOG_LEVELS:
            raise ValueError(f"Ungültiges Log-Level: {value}. Erlaubt: {cls.VALID_LOG_LEVELS}")
        return upper


def load_settings(
    require_api_key: bool = True,
    env_file: str | None = ".env",
) -> Settings:
    """Lädt und validiert die Einstellungen.

    Wenn require_api_key=True ist, wird geprüft, ob ein gültiger API-Schlüssel
    für den konfigurierten Provider (OpenAI, Google Gemini oder Groq) gesetzt und nicht leer ist.
    Gibt bei Fehlern eine redigierte Fehlermeldung ohne sensible Daten aus.
    """
    settings = Settings(_env_file=env_file)

    # Automatische Provider-Erkennung:
    gemini_key = settings.gemini_api_key.get_secret_value().strip()
    openai_key = settings.openai_api_key.get_secret_value().strip()
    groq_key = settings.groq_api_key.get_secret_value().strip()

    if groq_key and not openai_key and not gemini_key and settings.llm_provider == "openai":
        settings.llm_provider = "groq"
    elif gemini_key and not openai_key and settings.llm_provider == "openai":
        settings.llm_provider = "google"

    if require_api_key:
        if settings.llm_provider == "groq":
            if not groq_key:
                raise ValueError(
                    "Fehlende Konfiguration: GROQ_API_KEY ist nicht gesetzt oder leer. "
                    "Bitte setze die Umgebungsvariable oder trage sie in .env ein."
                )
        elif settings.llm_provider == "google":
            if not gemini_key:
                raise ValueError(
                    "Fehlende Konfiguration: GEMINI_API_KEY ist nicht gesetzt oder leer. "
                    "Bitte setze die Umgebungsvariable oder trage sie in .env ein."
                )
        else:
            if not openai_key:
                raise ValueError(
                    "Fehlende Konfiguration: OPENAI_API_KEY ist nicht gesetzt oder leer. "
                    "Bitte setze die Umgebungsvariable oder trage sie in .env ein. "
                    "(Alternativ: GROQ_API_KEY mit LLM_PROVIDER=groq oder GEMINI_API_KEY)."
                )
    return settings
