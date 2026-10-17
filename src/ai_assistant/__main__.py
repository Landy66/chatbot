"""Haupteinstiegspunkt für den KI-Assistenten."""

from __future__ import annotations

import sys

from ai_assistant.agent import create_agent
from ai_assistant.chat_service import ChatService
from ai_assistant.config import load_settings
from ai_assistant.logging_config import setup_logging
from ai_assistant.ui import create_ui


def main() -> None:
    """Startet die KI-Assistent-Anwendung."""
    # 1. Konfiguration laden und validieren
    try:
        settings = load_settings(require_api_key=True)
    except Exception as exc:
        # Sichere Fehlerausgabe ohne sensiblen Traceback
        sys.stderr.write(f"Konfigurationsfehler: {exc}\n")
        sys.exit(1)

    # 2. Logging konfigurieren
    secrets_to_redact = [
        s
        for s in (
            settings.openai_api_key.get_secret_value(),
            settings.gemini_api_key.get_secret_value(),
            settings.groq_api_key.get_secret_value(),
        )
        if s
    ]
    setup_logging(
        log_level=settings.log_level,
        secret_to_redact=secrets_to_redact,
    )

    # 3. Komponenten instanziieren
    try:
        agent = create_agent(settings)
        chat_service = ChatService(agent, settings)
        demo = create_ui(chat_service, settings)
    except Exception as exc:
        sys.stderr.write(f"Fehler bei der Initialisierung: {exc}\n")
        sys.exit(1)

    # 4. Anwendung lokal starten
    print(f"Starte KI-Assistent auf http://{settings.app_host}:{settings.app_port} ...")
    demo.launch(
        server_name=settings.app_host,
        server_port=settings.app_port,
        share=False,
    )


if __name__ == "__main__":
    main()
