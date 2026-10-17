"""ChatService zur asynchronen Koordination von Pydantic-AI-Läufen und Streaming."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from ai_assistant.config import Settings
from ai_assistant.errors import (
    AuthenticationError,
    InputValidationError,
    ModelAccessError,
    QueueFullError,
    RateLimitError,
    RunCancelledError,
    classify_error,
)
from ai_assistant.memory import trim_context_turns
from ai_assistant.models import (
    CancelledEvent,
    ChunkEvent,
    CompletedEvent,
    ErrorEvent,
    ServiceEvent,
    SessionState,
    UsageInfo,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Koordiniert Modellläufe, Streaming, Sitzungsisolation und Limits."""

    def __init__(self, agent: Agent[None, str], settings: Settings) -> None:
        self.agent = agent
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_runs)
        self._queued_and_running_count = 0
        self._count_lock = asyncio.Lock()
        self._session_tasks: dict[str, asyncio.Task[Any]] = {}
        self._session_run_ids: dict[str, str] = {}
        self._session_reservation_locks: dict[str, asyncio.Lock] = {}
        self._secrets_to_redact = [
            s
            for s in (
                settings.openai_api_key.get_secret_value(),
                settings.gemini_api_key.get_secret_value(),
                settings.groq_api_key.get_secret_value(),
            )
            if s
        ]

    def _get_reservation_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._session_reservation_locks:
            self._session_reservation_locks[session_id] = asyncio.Lock()
        return self._session_reservation_locks[session_id]

    def _release_session(self, session_state: SessionState, run_id: str | None = None) -> None:
        """Gibt die Sitzungsregistrierung und den Busy-Status frei."""
        session_id = session_state.session_id
        if run_id is None or self._session_run_ids.get(session_id) == run_id:
            self._session_run_ids.pop(session_id, None)
            self._session_tasks.pop(session_id, None)
            session_state.is_busy = False
            session_state.active_run_id = None

    def is_session_running(self, session_id: str) -> bool:
        """Prüft, ob für die angegebene Sitzung bereits ein Lauf aktiv ist."""
        task = self._session_tasks.get(session_id)
        if task is not None and not task.done():
            return True
        return session_id in self._session_run_ids

    def stop_session(self, session_state: SessionState) -> None:
        """Bricht den aktuellen Lauf der Sitzung sofort ab und gibt Ressourcen frei."""
        session_id = session_state.session_id
        task = self._session_tasks.get(session_id)
        if task is not None and not task.done():
            task.cancel()

        self._release_session(session_state)

    def reset_session(self, session_state: SessionState) -> None:
        """Stoppt die Sitzung und setzt den Verlauf vollständig zurück."""
        self.stop_session(session_state)
        session_state.reset_for_new_chat()

    async def stream_chat(
        self,
        session_state: SessionState,
        prompt: str,
    ) -> AsyncIterator[ServiceEvent]:
        """Startet einen Modelllauf und liefert typisierte Service-Ereignisse."""
        # 1. Eingabevalidierung
        stripped_prompt = prompt.strip() if prompt else ""
        if not stripped_prompt:
            yield ErrorEvent(
                run_id="",
                generation_id=session_state.generation_id,
                error_message="Bitte gib eine Nachricht ein.",
                error_type="InputValidationError",
            )
            return

        if len(prompt) > self.settings.max_input_chars:
            yield ErrorEvent(
                run_id="",
                generation_id=session_state.generation_id,
                error_message=(
                    f"Die Eingabe überschreitet das Limit von "
                    f"{self.settings.max_input_chars} Zeichen."
                ),
                error_type="InputValidationError",
            )
            return

        # 2. Atomare Sitzungsreservierung (Verhinderung von Doppelklick/Doppelsenden)
        reservation_lock = self._get_reservation_lock(session_state.session_id)
        async with reservation_lock:
            if session_state.is_busy or self.is_session_running(session_state.session_id):
                yield ErrorEvent(
                    run_id="",
                    generation_id=session_state.generation_id,
                    error_message="Es läuft bereits eine Anfrage in dieser Sitzung.",
                    error_type="ConcurrentRunError",
                )
                return

            run_id = str(uuid.uuid4())
            current_generation = session_state.generation_id
            session_state.is_busy = True
            session_state.active_run_id = run_id
            self._session_run_ids[session_state.session_id] = run_id

        # Task in Registry registrieren
        current_task = asyncio.current_task()
        if current_task is not None:
            self._session_tasks[session_state.session_id] = current_task

        # 3. Queue-Größe und Semaphore prüfen
        async with self._count_lock:
            max_allowed = self.settings.max_concurrent_runs + self.settings.max_queue_size
            if self._queued_and_running_count >= max_allowed:
                self.stop_session(session_state)
                yield ErrorEvent(
                    run_id=run_id,
                    generation_id=current_generation,
                    error_message=(
                        "Die Warteschlange ist voll. "
                        "Bitte versuche es in wenigen Augenblicken erneut."
                    ),
                    error_type="QueueFullError",
                )
                return
            self._queued_and_running_count += 1

        semaphore_acquired = False
        first_chunk_yielded = False
        cumulative_text = ""
        retry_count = 0

        try:
            # Warten auf freien Concurrency-Slot
            await self._semaphore.acquire()
            semaphore_acquired = True

            # Kontext-Trimming auf History-Kopie anwenden
            context_messages, memory_trimmed = trim_context_turns(
                session_state.messages,
                max_turns=self.settings.max_context_turns,
                max_chars=self.settings.max_context_chars,
            )

            # Gesamtlauf mit Timeout und optionalen Retries
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                while True:
                    try:
                        was_cancelled = False
                        usage_info = UsageInfo()
                        final_messages: list[ModelMessage] = []

                        async with self.agent.run_stream(
                            prompt,
                            message_history=context_messages,
                        ) as result:
                            async for chunk in result.stream_text(debounce_by=None):
                                # Bei Reset oder Stop abbrechen
                                if (
                                    session_state.generation_id != current_generation
                                    or session_state.active_run_id != run_id
                                ):
                                    was_cancelled = True
                                    break

                                first_chunk_yielded = True
                                cumulative_text = chunk
                                yield ChunkEvent(
                                    run_id=run_id,
                                    generation_id=current_generation,
                                    content=cumulative_text,
                                    is_cumulative=True,
                                )

                            # Finale Prüfung nach dem Stream
                            if (
                                was_cancelled
                                or session_state.generation_id != current_generation
                                or session_state.active_run_id != run_id
                            ):
                                was_cancelled = True
                            else:
                                # Verbrauchsdaten auslesen
                                raw_usage = getattr(result, "usage", None)
                                req_tokens = (
                                    getattr(raw_usage, "input_tokens", None) if raw_usage else None
                                )
                                resp_tokens = (
                                    getattr(raw_usage, "output_tokens", None) if raw_usage else None
                                )
                                tot_tokens = (
                                    getattr(raw_usage, "total_tokens", None) if raw_usage else None
                                )

                                usage_info = UsageInfo(
                                    request_tokens=req_tokens,
                                    response_tokens=resp_tokens,
                                    total_tokens=tot_tokens,
                                )
                                final_messages = result.all_messages()

                        # Der async context manager ist nun vollständig und sauber geschlossen.
                        if was_cancelled:
                            self._release_session(session_state, run_id)
                            yield CancelledEvent(
                                run_id=run_id,
                                generation_id=current_generation,
                                partial_text=cumulative_text,
                            )
                            return

                        # Atomarer Commit der finalen History und Freigabe des Busy-Status
                        session_state.messages = final_messages
                        self._release_session(session_state, run_id)

                        yield CompletedEvent(
                            run_id=run_id,
                            generation_id=current_generation,
                            full_text=cumulative_text,
                            usage=usage_info,
                            memory_trimmed=memory_trimmed,
                        )
                        return

                    except GeneratorExit:
                        self._release_session(session_state, run_id)
                        return

                    except asyncio.CancelledError:
                        self._release_session(session_state, run_id)
                        yield CancelledEvent(
                            run_id=run_id,
                            generation_id=current_generation,
                            partial_text=cumulative_text,
                        )
                        raise

                    except Exception as stream_exc:
                        classified = classify_error(stream_exc, self._secrets_to_redact)
                        logger.error(
                            "Modellanfrage fehlgeschlagen in Lauf %s: %s (Klassifiziert als %s)",
                            run_id,
                            classified.internal_details or stream_exc,
                            type(classified).__name__,
                        )

                        # Nicht wiederholbar, wenn Guthaben fehlt
                        is_unrecoverable_rate_limit = isinstance(
                            classified, RateLimitError
                        ) and any(
                            kw in (classified.internal_details or "").lower()
                            for kw in ("credit", "billing", "quota")
                        )

                        # Retry-Bedingungen: nur vor erstem sichtbaren Chunk
                        # und nur bei transienten Fehlern
                        if (
                            not first_chunk_yielded
                            and retry_count < self.settings.max_retries
                            and not is_unrecoverable_rate_limit
                            and not isinstance(
                                classified,
                                (
                                    AuthenticationError,
                                    ModelAccessError,
                                    InputValidationError,
                                    RunCancelledError,
                                    QueueFullError,
                                ),
                            )
                        ):
                            retry_count += 1
                            logger.warning(
                                "Transienter Fehler in Lauf %s, Wiederholungsversuch %d/%d: %s",
                                run_id,
                                retry_count,
                                self.settings.max_retries,
                                type(classified).__name__,
                            )
                            await asyncio.sleep(0.3 * (2 ** (retry_count - 1)))
                            continue

                        self._release_session(session_state, run_id)
                        yield ErrorEvent(
                            run_id=run_id,
                            generation_id=current_generation,
                            error_message=classified.user_message,
                            error_type=type(classified).__name__,
                            partial_text=cumulative_text,
                        )
                        return

        except GeneratorExit:
            self._release_session(session_state, run_id)
            return

        except asyncio.CancelledError:
            self._release_session(session_state, run_id)
            yield CancelledEvent(
                run_id=run_id,
                generation_id=current_generation,
                partial_text=cumulative_text,
            )
            raise

        except TimeoutError:
            self._release_session(session_state, run_id)
            yield ErrorEvent(
                run_id=run_id,
                generation_id=current_generation,
                error_message="Zeitüberschreitung: Die Anfrage hat das Zeitlimit überschritten.",
                error_type="TimeoutError",
                partial_text=cumulative_text,
            )

        except Exception as exc:
            classified = classify_error(exc, self._secrets_to_redact)
            logger.error(
                "Fehler in stream_chat Lauf %s: %s (Klassifiziert als %s)",
                run_id,
                classified.internal_details or exc,
                type(classified).__name__,
            )
            self._release_session(session_state, run_id)
            yield ErrorEvent(
                run_id=run_id,
                generation_id=current_generation,
                error_message=classified.user_message,
                error_type=type(classified).__name__,
                partial_text=cumulative_text,
            )

        finally:
            if semaphore_acquired:
                self._semaphore.release()

            async with self._count_lock:
                self._queued_and_running_count = max(0, self._queued_and_running_count - 1)

            self._release_session(session_state, run_id)
