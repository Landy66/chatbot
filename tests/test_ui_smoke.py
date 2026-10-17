"""Smoke-Test für die Gradio UI und Event-Initialisierung (AC-02, AC-11)."""

from __future__ import annotations

import gradio as gr

from ai_assistant.chat_service import ChatService
from ai_assistant.config import Settings
from ai_assistant.ui import create_ui


def test_ui_creation_and_blocks(fake_chat_service: ChatService, test_settings: Settings) -> None:
    """AC-02 & AC-11: App ohne echte API-Verbindung erzeugen und Komponenten prüfen."""
    demo = create_ui(fake_chat_service, test_settings)
    assert isinstance(demo, gr.Blocks)
    assert demo.title == "KI-Assistent"

    # Komponenten prüfen
    block_types = [type(b).__name__ for b in demo.blocks.values()]
    assert "Chatbot" in block_types
    assert "Textbox" in block_types
    assert "Button" in block_types
    assert "State" in block_types
