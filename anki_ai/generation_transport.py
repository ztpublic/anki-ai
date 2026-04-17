"""Transport handlers for Claude Code-backed card generation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from .generation_service import (
    ClaudeCardGenerationService,
    GenerationServiceError,
    MaterialInput,
)
from .transport import JsonObject, TransportError, TransportRouter


def register_generation_transport_handlers(
    router: TransportRouter,
    service: ClaudeCardGenerationService | None = None,
) -> None:
    """Register generation bridge methods on a transport router."""
    handlers = GenerationTransportHandlers(service)
    router.register("anki.generation.generateCards", handlers.generate_cards)


class GenerationTransportHandlers:
    """Bridge-facing wrappers around ClaudeCardGenerationService."""

    def __init__(
        self,
        service: ClaudeCardGenerationService | None = None,
    ) -> None:
        self._service = ClaudeCardGenerationService() if service is None else service

    def generate_cards(self, params: JsonObject) -> JsonObject:
        source_text = _optional_string(params, "sourceText")
        card_count = _optional_int(
            params,
            "cardCount",
            ClaudeCardGenerationService.DEFAULT_CARD_COUNT,
            minimum=1,
            maximum=ClaudeCardGenerationService.MAX_CARD_COUNT,
        )
        materials = _optional_material_inputs(params, "materials")

        if source_text is None and not materials:
            raise TransportError(
                "invalid_params",
                "Provide sourceText or at least one item in materials.",
            )

        return self._run(
            lambda service: service.generate_cards(
                source_text=source_text,
                materials=materials,
                card_count=card_count,
            )
        )

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
