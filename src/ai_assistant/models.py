"""Datenmodelle für SessionState, Service-Events und Usage-Metadaten."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ModelMessage


@dataclass
class UsageInfo:
    """Metadaten zum Tokenverbrauch eines Modelllaufs."""

    request_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None

    def format_status(self) -> str:
        """Gibt eine dezente Formatierung des Verbrauchs auf Deutsch zurück."""
        if (
            self.total_tokens is None
            and self.request_tokens is None
            and self.response_tokens is None
        ):
            return "Tokenverbrauch: Unbekannt"

        parts: list[str] = []
        if self.request_tokens is not None:
            parts.append(f"{self.request_tokens} Prompt")
        if self.response_tokens is not None:
            parts.append(f"{self.response_tokens} Antwort")
        if self.total_tokens is not None:
            parts.append(f"{self.total_tokens} Gesamt")

        return f"Tokenverbrauch: {', '.join(parts)}" if parts else "Tokenverbrauch: Unbekannt"


@dataclass
class ServiceEvent:
    """Basis-Klasse für asynchrone Service-Ereignisse."""

    run_id: str
    generation_id: int


@dataclass
class ChunkEvent(ServiceEvent):
    """Ereignis für ein gestreamtes Text-Update."""

    content: str
    is_cumulative: bool = True


@dataclass
class CompletedEvent(ServiceEvent):
    """Ereignis für den erfolgreichen Abschluss einer Antwortgenerierung."""

    full_text: str
    usage: UsageInfo
    memory_trimmed: bool = False
    ui_trimmed: bool = False


@dataclass
class ErrorEvent(ServiceEvent):
    """Ereignis für einen aufgetretenen Fehler."""

    error_message: str
    error_type: str
    partial_text: str = ""


@dataclass
class CancelledEvent(ServiceEvent):
    """Ereignis für einen durch den Benutzer abgebrochenen Lauf."""

    partial_text: str = ""


@dataclass
class SessionState:
    """Serialisierbarer Sitzungszustand für eine Browser-Session.

    Hält die autoritative Pydantic-AI-History und die UI-Nachrichten getrennt.
    Enthält bewusst keine Tasks, Queues oder Locks, um deepcopy-kompatibel
    mit Gradio State zu bleiben.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generation_id: int = 0
    active_run_id: str | None = None
    messages: list[ModelMessage] = field(default_factory=list)
    ui_messages: list[dict[str, Any]] = field(default_factory=list)
    is_busy: bool = False
    status_text: str = ""

    def reset_for_new_chat(self) -> None:
        """Löscht den Chatverlauf logisch vollständig und invalidiert laufende Generierungen."""
        self.generation_id += 1
        self.active_run_id = None
        self.messages.clear()
        self.ui_messages.clear()
        self.is_busy = False
        self.status_text = ""

    def copy(self) -> SessionState:
        """Erstellt eine tiefe Kopie des Zustands."""
        return copy.deepcopy(self)
