"""Sichere Logging-Konfiguration ohne Secrets und ohne Nachrichteninhalte."""

from __future__ import annotations

import logging
import sys
from typing import ClassVar


class RedactingFormatter(logging.Formatter):
    """Logging-Formatter, der sicherstellt, dass Secrets nicht ausgegeben werden."""

    _redacted_patterns: ClassVar[set[str]] = set()

    @classmethod
    def register_secret(cls, secret: str | None) -> None:
        """Registriert ein Secret für die Maskierung, falls vorhanden."""
        if secret and len(secret.strip()) > 3:
            cls._redacted_patterns.add(secret.strip())

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        for secret in self._redacted_patterns:
            if secret in original:
                original = original.replace(secret, "[REDACTED_SECRET]")
        return original


def setup_logging(
    log_level: str = "INFO",
    secret_to_redact: str | list[str] | tuple[str, ...] | None = None,
) -> None:
    """Richtet das Anwendungs-Logging ein.

    Begrenzt Drittanbieter-Logger (httpx, openai, google etc.) auf WARNING und
    verhindert die Ausgabe von Nachrichteninhalten oder Secrets.
    """
    if isinstance(secret_to_redact, (list, tuple, set)):
        for sec in secret_to_redact:
            if sec:
                RedactingFormatter.register_secret(sec)
    elif secret_to_redact:
        RedactingFormatter.register_secret(secret_to_redact)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Bestehende Handler bereinigen
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    formatter = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Drittanbieter-Logger auf WARNING drosseln, um Body- und Auth-Logs zu verhindern
    for noisy in (
        "httpx",
        "httpcore",
        "openai",
        "google",
        "google_genai",
        "groq",
        "gradio",
        "urllib3",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
