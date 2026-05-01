"""Transport handlers for Claude Code-backed card generation."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any, Union, cast

from .card_types import DEFAULT_CARD_TYPE_ID, card_type_ids
from .generation_service import (
    ClaudeCardGenerationService,
    GenerationLogEvent,
    GenerationResult,
    GenerationServiceError,
    MaterialInput,
)
from .transport import JsonObject, TransportError, TransportRouter

GenerationJobOutcome = Union[GenerationResult, BaseException]
GenerationJobOperation = Callable[[], GenerationResult]
GenerationJobCallback = Callable[[GenerationJobOutcome], None]
GenerationBackgroundRunner = Callable[
    [GenerationJobOperation, GenerationJobCallback],
    None,
]
GenerationEventEmitter = Callable[[str, JsonObject], None]


def register_generation_transport_handlers(
    router: TransportRouter,
    service: ClaudeCardGenerationService | None = None,
    *,
    background_runner: GenerationBackgroundRunner | None = None,
    event_emitter: GenerationEventEmitter | None = None,
) -> None:
    """Register generation bridge methods on a transport router."""
    handlers = GenerationTransportHandlers(
        service,
        background_runner=background_runner,
        event_emitter=event_emitter,
    )
    router.register("anki.generation.generateCards", handlers.generate_cards)
    router.register("anki.generation.regenerateAnswer", handlers.regenerate_answer)
    router.register(
        "anki.generation.regenerateAnswerAndExplanation",
        handlers.regenerate_answer_and_explanation,
    )
    router.register("anki.generation.startGenerateCards", handlers.start_generate_cards)
    router.register("anki.generation.stopGenerateCards", handlers.stop_generate_cards)


class GenerationTransportHandlers:
    """Bridge-facing wrappers around ClaudeCardGenerationService."""

    def __init__(
        self,
        service: ClaudeCardGenerationService | None = None,
        *,
        background_runner: GenerationBackgroundRunner | None = None,
        event_emitter: GenerationEventEmitter | None = None,
    ) -> None:
        self._service = ClaudeCardGenerationService() if service is None else service
        self._background_runner = (
            _default_background_runner
            if background_runner is None
            else background_runner
        )
        self._event_emitter = event_emitter
        self._jobs_lock = threading.Lock()
        self._active_jobs: set[str] = set()
        self._cancelled_jobs: set[str] = set()

    def generate_cards(self, params: JsonObject) -> JsonObject:
        source_text, materials, card_count, card_type = self._generation_inputs(params)

        return self._run(
            lambda service: service.generate_cards(
                source_text=source_text,
                materials=materials,
                card_count=card_count,
                card_type=card_type,
            )
        )

    def regenerate_answer(self, params: JsonObject) -> JsonObject:
        question, answer, explanation = self._card_regeneration_inputs(params)

        return self._run(
            lambda service: service.regenerate_answer(
                question=question,
                answer=answer,
                explanation=explanation,
            )
        )

    def regenerate_answer_and_explanation(self, params: JsonObject) -> JsonObject:
        question, answer, explanation = self._card_regeneration_inputs(params)

        return self._run(
            lambda service: service.regenerate_answer_and_explanation(
                question=question,
                answer=answer,
                explanation=explanation,
            )
        )

    def start_generate_cards(self, params: JsonObject) -> JsonObject:
        event_emitter = self._event_emitter
        if event_emitter is None:
            raise TransportError(
                "generation_events_unavailable",
                "Generation events are not available in this bridge context.",
            )

        source_text, materials, card_count, card_type = self._generation_inputs(params)
        job_id = str(uuid.uuid4())

        with self._jobs_lock:
            self._active_jobs.add(job_id)

        def emit_job(payload: JsonObject) -> None:
            event_emitter(
                "anki.generation.job",
                {
                    "jobId": job_id,
                    **payload,
                },
            )

        def is_cancelled() -> bool:
            with self._jobs_lock:
                return job_id in self._cancelled_jobs

        def log_sink(event: GenerationLogEvent) -> None:
            if is_cancelled():
                return

            payload: JsonObject = {
                "status": "log",
                "level": event.get("level", "info"),
                "message": event.get("message", ""),
            }
            source = event.get("source")
            role = event.get("role")
            part = event.get("part")
            if source is not None:
                payload["source"] = source
            if role is not None:
                payload["role"] = role
            if part is not None:
                payload["part"] = part
            emit_job(payload)

        def operation() -> GenerationResult:
            if is_cancelled():
                raise GenerationServiceError(
                    "generation_cancelled",
                    "Generation was stopped.",
                )
            emit_job(
                {
                    "status": "started",
                    "message": "Started Claude Code card generation.",
                }
            )
            result = self._service.generate_cards(
                source_text=source_text,
                materials=materials,
                card_count=card_count,
                card_type=card_type,
                log_sink=log_sink,
            )
            if is_cancelled():
                raise GenerationServiceError(
                    "generation_cancelled",
                    "Generation was stopped.",
                )
            return result

        def on_done(outcome: GenerationJobOutcome) -> None:
            with self._jobs_lock:
                was_cancelled = job_id in self._cancelled_jobs
                self._active_jobs.discard(job_id)
                self._cancelled_jobs.discard(job_id)

            if was_cancelled:
                return

            if isinstance(outcome, BaseException):
                emit_job(
                    {
                        "status": "failed",
                        "error": _error_payload(outcome),
                    }
                )
                return

            emit_job(
                {
                    "status": "succeeded",
                    "result": outcome,
                }
            )

        self._background_runner(operation, on_done)
        return {"jobId": job_id}

    def stop_generate_cards(self, params: JsonObject) -> JsonObject:
        event_emitter = self._event_emitter
        if event_emitter is None:
            raise TransportError(
                "generation_events_unavailable",
                "Generation events are not available in this bridge context.",
            )

        job_id = _required_string(params, "jobId")
        with self._jobs_lock:
            was_active = job_id in self._active_jobs
            if was_active:
                self._cancelled_jobs.add(job_id)

        if was_active:
            event_emitter(
                "anki.generation.job",
                {
                    "jobId": job_id,
                    "status": "cancelled",
                    "message": "Generation stopped.",
                },
            )

        return {"jobId": job_id, "stopped": was_active}

    def _generation_inputs(
        self,
        params: JsonObject,
    ) -> tuple[str | None, list[MaterialInput], int, str]:
        source_text = _optional_string(params, "sourceText")
        card_count = _optional_int(
            params,
            "cardCount",
            ClaudeCardGenerationService.DEFAULT_CARD_COUNT,
            minimum=1,
            maximum=ClaudeCardGenerationService.MAX_CARD_COUNT,
        )
        card_type = _optional_card_type(params, "cardType")
        materials = _optional_material_inputs(params, "materials")

        if source_text is None and not materials:
            raise TransportError(
                "invalid_params",
                "Provide sourceText or at least one item in materials.",
            )

        return source_text, materials, card_count, card_type

    def _card_regeneration_inputs(
        self,
        params: JsonObject,
    ) -> tuple[str, str, str | None]:
        question = _required_string(params, "question")
        answer = _required_string(params, "answer")
        explanation = _optional_text(params, "explanation")

        return question, answer, explanation

    def _run(
        self,
        callback: Callable[[ClaudeCardGenerationService], Any],
    ) -> JsonObject:
        try:
            result = callback(self._service)
        except GenerationServiceError as error:
            raise TransportError(error.code, error.message, error.details) from error

        if not isinstance(result, dict):
            raise TransportError(
                "invalid_service_result",
                "Generation service returned a non-object payload.",
            )
        return cast(JsonObject, result)


def _default_background_runner(
    operation: GenerationJobOperation,
    on_done: GenerationJobCallback,
) -> None:
    def run() -> None:
        try:
            outcome: GenerationJobOutcome = operation()
        except BaseException as error:
            outcome = error
        on_done(outcome)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


def _error_payload(error: BaseException) -> JsonObject:
    if isinstance(error, TransportError):
        return error.to_payload()
    if isinstance(error, GenerationServiceError):
        return TransportError(error.code, error.message, error.details).to_payload()
    return TransportError(
        "claude_generation_failed",
        "Claude Code generation failed.",
        {
            "errorType": type(error).__name__,
            "error": str(error),
        },
    ).to_payload()


def _optional_string(params: JsonObject, key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty string when provided.",
        )
    return value


def _optional_text(params: JsonObject, key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TransportError(
            "invalid_params",
            f"{key} must be a string when provided.",
        )
    return value


def _required_string(params: JsonObject, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty string.",
        )
    return value


def _optional_card_type(params: JsonObject, key: str) -> str:
    value = params.get(key, DEFAULT_CARD_TYPE_ID)
    if not isinstance(value, str) or not value.strip():
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty string.",
        )
    if value not in card_type_ids():
        raise TransportError(
            "invalid_params",
            f"{key} is not a supported card type.",
            {"cardType": value, "supportedCardTypes": list(card_type_ids())},
        )
    return value


def _optional_int(
    params: JsonObject,
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TransportError(
            "invalid_params",
            f"{key} must be an integer.",
        )
    if value < minimum or value > maximum:
        raise TransportError(
            "invalid_params",
            f"{key} must be between {minimum} and {maximum}.",
        )
    return cast(int, value)


def _optional_material_inputs(params: JsonObject, key: str) -> list[MaterialInput]:
    value = params.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise TransportError(
            "invalid_params",
            f"{key} must be a list of material payloads when provided.",
        )

    materials: list[MaterialInput] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise TransportError(
                "invalid_params",
                f"{key}[{index}] must be an object.",
            )

        name = item.get("name")
        content_base64 = item.get("contentBase64")
        if not isinstance(name, str) or not name.strip():
            raise TransportError(
                "invalid_params",
                f"{key}[{index}].name must be a non-empty string.",
            )
        if not isinstance(content_base64, str):
            raise TransportError(
                "invalid_params",
                f"{key}[{index}].contentBase64 must be a string.",
            )

        materials.append({"name": name, "contentBase64": content_base64})

    return materials
