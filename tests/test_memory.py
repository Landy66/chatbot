"""Tests für das Memory-Management und Trimming ganzer Runden (AC-04, AC-09)."""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from ai_assistant.memory import (
    count_message_characters,
    group_into_turns,
    trim_context_turns,
    trim_ui_turns,
)


def make_turn(
    user_text: str, assistant_text: str, sys_text: str | None = None
) -> list[ModelMessage]:
    """Hilfsfunktion zum Erzeugen einer vollständigen Gesprächsrunde."""
    parts = []
    if sys_text:
        parts.append(SystemPromptPart(content=sys_text))
    parts.append(UserPromptPart(content=user_text))
    req = ModelRequest(parts=parts)
    resp = ModelResponse(parts=[TextPart(content=assistant_text)])
    return [req, resp]


def test_turn_grouping_and_char_counting() -> None:
    """Prüft das Gruppieren in Runden und Zählen von Zeichen."""
    msgs = make_turn("Hallo", "Hi", sys_text="Du bist ein Assistent.")
    sys_parts, turns = group_into_turns(msgs)
    assert len(sys_parts) == 1
    assert sys_parts[0].content == "Du bist ein Assistent."
    assert len(turns) == 1
    assert count_message_characters(msgs) == len("Du bist ein Assistent.") + len("Hallo") + len(
        "Hi"
    )


def test_trim_context_turns_preserves_system_prompt() -> None:
    """Stellt sicher, dass das Trimming nur ältere Runden entfernt und System-Prompts behält."""
    msgs: list[ModelMessage] = []
    msgs.extend(make_turn("Frage 1", "Antwort 1", sys_text="System-Instruktion"))
    msgs.extend(make_turn("Frage 2", "Antwort 2"))
    msgs.extend(make_turn("Frage 3", "Antwort 3"))

    # Limit auf max 2 Runden
    trimmed_msgs, was_trimmed = trim_context_turns(msgs, max_turns=2, max_chars=10000)
    assert was_trimmed is True
    assert len(trimmed_msgs) == 4  # 2 Runden (2 Requests + 2 Responses)

    # Erste Nachricht muss SystemPromptPart beibehalten
    first_req = trimmed_msgs[0]
    assert isinstance(first_req, ModelRequest)
    assert any(isinstance(p, SystemPromptPart) for p in first_req.parts)
    # Und Frage 1 wurde entfernt, Frage 2 ist jetzt die älteste
    user_part = [p for p in first_req.parts if isinstance(p, UserPromptPart)][0]
    assert user_part.content == "Frage 2"


def test_trim_context_chars_limit() -> None:
    """Stellt sicher, dass bei Überschreitung des Zeichenlimits ältere Runden entfernt werden."""
    msgs: list[ModelMessage] = []
    msgs.extend(make_turn("Frage 1", "A" * 100))
    msgs.extend(make_turn("Frage 2", "B" * 100))
    msgs.extend(make_turn("Frage 3", "C" * 100))

    # Zeichenlimit 150 -> Frage 1 & 2 müssen weichen, nur Frage 3 passt
    trimmed_msgs, was_trimmed = trim_context_turns(msgs, max_turns=10, max_chars=150)
    assert was_trimmed is True
    assert len(trimmed_msgs) == 2
    assert trimmed_msgs[0].parts[0].content == "Frage 3"


def test_trim_ui_turns() -> None:
    """Prüft das Entfernen ältester UI-Nachrichten."""
    ui_messages = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "1"},
        {"role": "user", "content": "2"},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": "3"},
    ]
    trimmed, was_trimmed = trim_ui_turns(ui_messages, max_ui_turns=2)
    assert was_trimmed is True
    assert len(trimmed) == 4
    assert trimmed[0]["content"] == "2"
