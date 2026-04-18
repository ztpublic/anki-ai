"""Transport handlers for MarkItDown-backed file conversion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from .file_conversion_service import (
    FileConversionInput,
    FileConversionServiceError,
    MarkItDownFileConversionService,
)
from .transport import JsonObject, TransportError, TransportRouter


def register_file_conversion_transport_handlers(
    router: TransportRouter,
    service: MarkItDownFileConversionService | None = None,
) -> None:
    """Register file conversion bridge methods on a transport router."""
    handlers = FileConversionTransportHandlers(service)
    router.register("anki.files.convertToMarkdown", handlers.convert_to_markdown)


class FileConversionTransportHandlers:
    """Bridge-facing wrappers around MarkItDownFileConversionService."""

    def __init__(
        self,
        service: MarkItDownFileConversionService | None = None,
    ) -> None:
        self._service = (
            MarkItDownFileConversionService() if service is None else service
        )

    def convert_to_markdown(self, params: JsonObject) -> JsonObject:
        file = _required_file_input(params, "file")
        return self._run(lambda service: service.convert_file(file=file))

    def _run(
        self,
        callback: Callable[[MarkItDownFileConversionService], Any],
    ) -> JsonObject:
        try:
            result = callback(self._service)
        except FileConversionServiceError as error:
            raise TransportError(error.code, error.message, error.details) from error

        if not isinstance(result, dict):
            raise TransportError(
                "invalid_service_result",
                "File conversion service returned a non-object payload.",
            )
        return cast(JsonObject, result)


def _required_file_input(params: JsonObject, key: str) -> FileConversionInput:
    value = params.get(key)
    if not isinstance(value, dict):
        raise TransportError(
            "invalid_params",
            f"{key} must be an object.",
        )

    name = value.get("name")
    content_base64 = value.get("contentBase64")
    if not isinstance(name, str) or not name.strip():
        raise TransportError(
            "invalid_params",
            f"{key}.name must be a non-empty string.",
        )
    if not isinstance(content_base64, str):
        raise TransportError(
            "invalid_params",
            f"{key}.contentBase64 must be a string.",
        )

    return {"name": name, "contentBase64": content_base64}
