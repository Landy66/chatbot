"""Memory-Management und Trimming-Logik für den KI-Assistenten."""

from __future__ import annotations

import copy
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)


def count_message_characters(messages: list[ModelMessage]) -> int:
    """Zählt die Summe aller Zeichen in den Textinhalten der Nachrichten."""
    total_chars = 0
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, (UserPromptPart, SystemPromptPart)) and isinstance(
                    part.content, str
                ):
                    total_chars += len(part.content)
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, TextPart):
                    total_chars += len(part.content)
    return total_chars


def group_into_turns(
    messages: list[ModelMessage],
) -> tuple[list[SystemPromptPart], list[tuple[ModelRequest, ModelResponse]]]:
    """Trennt System-Instruktionen und gruppiert die Nachrichten in (Request, Response)-Runden.

    Behält System-Instruktionen bei, damit sie beim Entfernen ganzer Runden
    nicht verloren gehen.
    """
    system_parts: list[SystemPromptPart] = []
    turns: list[tuple[ModelRequest, ModelResponse]] = []

    pending_request: ModelRequest | None = None

    for msg in messages:
        if isinstance(msg, ModelRequest):
            # System-Prompts erfassen
            non_system_parts: list[Any] = []
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    system_parts.append(part)
                else:
                    non_system_parts.append(part)

            # Neuer Request mit verbleibenden Teilen (z. B. UserPromptPart)
            req_copy = copy.deepcopy(msg)
            req_copy.parts = non_system_parts
            pending_request = req_copy

        elif isinstance(msg, ModelResponse):
            if pending_request is not None:
                turns.append((pending_request, copy.deepcopy(msg)))
                pending_request = None

    return system_parts, turns


def reconstruct_messages(
    system_parts: list[SystemPromptPart],
    turns: list[tuple[ModelRequest, ModelResponse]],
) -> list[ModelMessage]:
    """Baut eine geordnete Liste von ModelMessages aus System-Prompts und Runden zusammen."""
    if not turns:
        if system_parts:
            return [ModelRequest(parts=list(system_parts))]
        return []

    result: list[ModelMessage] = []
    for i, (req, resp) in enumerate(turns):
        req_copy = copy.deepcopy(req)
        if i == 0 and system_parts:
            # System-Prompts im ersten Request an den Anfang setzen
            existing_sys = [p for p in req_copy.parts if isinstance(p, SystemPromptPart)]
            if not existing_sys:
                req_copy.parts = list(system_parts) + req_copy.parts
        result.append(req_copy)
        result.append(copy.deepcopy(resp))

    return result


def trim_context_turns(
    messages: list[ModelMessage],
    max_turns: int,
    max_chars: int,
) -> tuple[list[ModelMessage], bool]:
    """Entfernt älteste vollständige Gesprächsrunden bei Überschreitung der Grenzwerte.

    - Entfernt ausschließlich ganze abgeschlossene Runden (User-Frage + Modell-Antwort).
    - Behält System-Instruktionen stets bei.
    - Gibt die bereinigte Liste und ein Flag zurück, ob gekürzt wurde.
    """
    if not messages:
        return [], False

    system_parts, turns = group_into_turns(messages)
    original_turns_count = len(turns)

    # 1. Kürzen nach Runden-Limit
    trimmed = False
    if len(turns) > max_turns:
        turns = turns[-max_turns:]
        trimmed = True

    # 2. Prüfen und Kürzen nach Zeichen-Limit
    current_messages = reconstruct_messages(system_parts, turns)
    while turns and count_message_characters(current_messages) > max_chars:
        turns.pop(0)
        trimmed = True
        current_messages = reconstruct_messages(system_parts, turns)

    if not trimmed and len(turns) == original_turns_count:
        return messages, False

    return current_messages, True


def trim_ui_turns(
    ui_messages: list[dict[str, Any]],
    max_ui_turns: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Entfernt älteste Nachrichten aus der UI-Anzeige bei Überschreitung von max_ui_turns.

    Eine Runde entspricht typischerweise 2 UI-Nachrichten (Nutzer + Assistent).
    """
    max_messages = max_ui_turns * 2
    if len(ui_messages) > max_messages:
        return ui_messages[-max_messages:], True
    return ui_messages, False
