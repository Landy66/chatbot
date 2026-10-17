"""Gradio Blocks Benutzeroberfläche für den KI-Assistenten."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import gradio as gr

from ai_assistant.chat_service import ChatService
from ai_assistant.config import Settings
from ai_assistant.memory import trim_ui_turns
from ai_assistant.models import (
    CancelledEvent,
    ChunkEvent,
    CompletedEvent,
    ErrorEvent,
    SessionState,
)
from ai_assistant.prompts import (
    MEMORY_TRIMMED_NOTICE,
    UI_DISCLAIMER,
    UI_TRIMMED_NOTICE,
)

logger = logging.getLogger(__name__)


def create_ui(chat_service: ChatService, settings: Settings) -> gr.Blocks:
    """Erstellt die Gradio-Blocks-Oberfläche mit Event-Verdrahtung."""
    with gr.Blocks(
        title="KI-Assistent",
    ) as demo:
        state = gr.State()

        gr.Markdown("## Allgemeiner KI-Assistent")
        gr.Markdown(f"*{UI_DISCLAIMER}*")

        chatbot = gr.Chatbot(
            label="Gesprächsverlauf",
            elem_id="chatbot",
        )

        with gr.Row():
            txt_input = gr.Textbox(
                placeholder="Nachricht eingeben (Enter zum Senden, Shift+Enter für neue Zeile)...",
                lines=2,
                max_lines=8,
                show_label=False,
                scale=8,
                elem_id="user_input",
            )

        with gr.Row():
            btn_send = gr.Button("Senden", variant="primary", scale=2)
            btn_stop = gr.Button("Stoppen", variant="stop", scale=1)
            btn_new = gr.Button("Neuer Chat", variant="secondary", scale=1)

        status_display = gr.Markdown("", elem_id="status_display")

        async def user_send(
            prompt: str,
            ui_history: list[dict[str, Any]] | None,
            current_state: SessionState | None,
        ) -> AsyncIterator[tuple[list[dict[str, Any]], str, str, SessionState]]:
            """Verarbeitet das Senden einer Nachricht und streamt die Antwort."""
            if current_state is None:
                current_state = SessionState()

            history: list[dict[str, Any]] = list(ui_history) if ui_history is not None else []
            clean_prompt = prompt.strip() if prompt else ""

            if not clean_prompt:
                current_state.is_busy = False
                yield history, "", "Bitte gib eine Nachricht ein.", current_state
                return

            if len(prompt) > settings.max_input_chars:
                current_state.is_busy = False
                yield (
                    history,
                    prompt,
                    f"Eingabe zu lang: Maximal {settings.max_input_chars} Zeichen erlaubt.",
                    current_state,
                )
                return

            # Nachricht zur UI hinzufügen und Eingabefeld leeren
            history.append({"role": "user", "content": prompt})
            history.append({"role": "assistant", "content": ""})
            yield history, "", "Antwort wird generiert...", current_state

            # Stream vom ChatService abrufen
            try:
                async for event in chat_service.stream_chat(current_state, prompt):
                    if isinstance(event, ChunkEvent):
                        history[-1]["content"] = event.content
                        yield history, "", "Antwort wird generiert...", current_state

                    elif isinstance(event, CompletedEvent):
                        history[-1]["content"] = event.full_text

                        # UI Trimming anwenden
                        trimmed_history, ui_was_trimmed = trim_ui_turns(
                            history,
                            max_ui_turns=settings.max_ui_turns,
                        )
                        history = trimmed_history

                        status_parts = [event.usage.format_status()]
                        if event.memory_trimmed:
                            status_parts.append(MEMORY_TRIMMED_NOTICE)
                        if ui_was_trimmed:
                            status_parts.append(UI_TRIMMED_NOTICE)

                        current_state.is_busy = False
                        current_state.active_run_id = None
                        yield history, "", " | ".join(status_parts), current_state

                    elif isinstance(event, CancelledEvent):
                        current_state.is_busy = False
                        current_state.active_run_id = None
                        if event.partial_text:
                            history[-1]["content"] = (
                                f"{event.partial_text}\n\n*[Antwort abgebrochen]*"
                            )
                        else:
                            history[-1]["content"] = "*[Antwort abgebrochen]*"

                        yield history, "", "Generierung abgebrochen.", current_state

                    elif isinstance(event, ErrorEvent):
                        current_state.is_busy = False
                        current_state.active_run_id = None
                        err_msg = event.error_message
                        if event.partial_text:
                            history[-1]["content"] = (
                                f"{event.partial_text}\n\n⚠️ **Fehler**: {err_msg}"
                            )
                        else:
                            history[-1]["content"] = f"⚠️ **Fehler**: {err_msg}"

                        yield history, "", f"Fehler: {err_msg}", current_state
            finally:
                current_state.is_busy = False
                current_state.active_run_id = None

        def handle_stop(
            current_state: SessionState | None,
        ) -> tuple[str, SessionState]:
            """Stoppt die aktuelle Antwortgenerierung sofort."""
            if current_state is not None:
                chat_service.stop_session(current_state)
            else:
                current_state = SessionState()
            current_state.is_busy = False
            current_state.active_run_id = None
            return "Generierung gestoppt.", current_state

        def handle_new_chat(
            current_state: SessionState | None,
        ) -> tuple[list[dict[str, Any]], str, str, SessionState]:
            """Setzt die Sitzung und Ansicht vollständig zurück."""
            if current_state is not None:
                chat_service.reset_session(current_state)
            current_state = SessionState()
            return (
                [],
                "",
                "Neuer Chat gestartet. Gesprächsverlauf wurde gelöscht.",
                current_state,
            )

        # Event-Verknüpfungen mit Gradio-Cancellation
        send_ev1 = btn_send.click(
            fn=user_send,
            inputs=[txt_input, chatbot, state],
            outputs=[chatbot, txt_input, status_display, state],
        )

        send_ev2 = txt_input.submit(
            fn=user_send,
            inputs=[txt_input, chatbot, state],
            outputs=[chatbot, txt_input, status_display, state],
        )

        btn_stop.click(
            fn=handle_stop,
            inputs=[state],
            outputs=[status_display, state],
            cancels=[send_ev1, send_ev2],
        )

        btn_new.click(
            fn=handle_new_chat,
            inputs=[state],
            outputs=[chatbot, txt_input, status_display, state],
            cancels=[send_ev1, send_ev2],
        )

    return demo
