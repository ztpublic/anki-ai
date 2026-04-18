"""MarkItDown-backed file conversion service."""

from __future__ import annotations

import base64
import importlib
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypedDict


class FileConversionInput(TypedDict):
    name: str
    contentBase64: str


class ConvertedDocument(TypedDict):
    name: str
    markdown: str
    sourceExtension: str


class FileConversionResult(TypedDict):
    document: ConvertedDocument


class FileConversionServiceError(Exception):
    """A domain error that can be safely surfaced to bridge callers."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class MarkItDownResult(Protocol):
    text_content: str


class MarkItDownConverter(Protocol):
    def convert(self, source: str) -> MarkItDownResult:
        ...


ConverterFactory = Callable[[], MarkItDownConverter]
WorkspaceFactory = Callable[[], Path]


def _default_workspace_factory() -> Path:
    return Path(tempfile.mkdtemp(prefix="anki-ai-file-conversion-"))


def _default_converter_factory() -> MarkItDownConverter:
    module = importlib.import_module("markitdown")
    return module.MarkItDown()


class MarkItDownFileConversionService:
    """Convert attached files into markdown using MarkItDown."""

    # These mirror the default built-in converters registered by MarkItDown().
    SUPPORTED_EXTENSIONS = frozenset(
        {
            ".atom",
            ".csv",
            ".docx",
            ".epub",
            ".htm",
            ".html",
            ".ipynb",
            ".jpeg",
            ".jpg",
            ".json",
            ".jsonl",
            ".m4a",
            ".md",
            ".markdown",
            ".mp3",
            ".mp4",
            ".msg",
            ".pdf",
            ".png",
            ".pptx",
            ".rss",
            ".text",
            ".txt",
            ".wav",
            ".xls",
            ".xlsx",
            ".xml",
            ".zip",
        }
    )

    def __init__(
        self,
        *,
        converter_factory: ConverterFactory = _default_converter_factory,
        workspace_factory: WorkspaceFactory = _default_workspace_factory,
    ) -> None:
        self._converter_factory = converter_factory
        self._workspace_factory = workspace_factory

    def convert_file(
        self,
        *,
        file: FileConversionInput,
    ) -> FileConversionResult:
        filename = self._sanitize_filename(file)
        extension = Path(filename).suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise FileConversionServiceError(
                "unsupported_file_type",
                "This file type is not currently supported for conversion.",
                {
                    "fileName": filename,
                    "sourceExtension": extension,
                    "supportedExtensions": sorted(self.SUPPORTED_EXTENSIONS),
                },
            )

        try:
            content = base64.b64decode(file["contentBase64"], validate=True)
        except (ValueError, TypeError) as error:
            raise FileConversionServiceError(
                "invalid_file_payload",
                "The attached file did not contain valid base64 content.",
                {"fileName": filename},
            ) from error

        workspace_path = self._workspace_factory()
        workspace_path.mkdir(parents=True, exist_ok=True)
        source_path = workspace_path / filename
        source_path.write_bytes(content)

        try:
            converter = self._converter_factory()
        except ModuleNotFoundError as error:
            if error.name not in (None, "markitdown") and "markitdown" not in str(error):
                raise
            raise FileConversionServiceError(
                "markitdown_not_available",
                "MarkItDown is not available in the current environment.",
            ) from error

        try:
            result = converter.convert(str(source_path))
        except Exception as error:
            raise FileConversionServiceError(
                "file_conversion_failed",
                f"Could not convert {filename} to markdown.",
                {
                    "fileName": filename,
                    "sourceExtension": extension,
                    "workspacePath": str(workspace_path),
                    "error": str(error),
                },
            ) from error

        markdown = getattr(result, "text_content", None)
        if not isinstance(markdown, str) or not markdown.strip():
            raise FileConversionServiceError(
                "empty_conversion_output",
                f"{filename} did not produce any markdown output.",
                {
                    "fileName": filename,
                    "sourceExtension": extension,
                    "workspacePath": str(workspace_path),
                },
            )

        return {
            "document": {
                "name": filename,
                "markdown": markdown,
                "sourceExtension": extension,
            }
        }

    @staticmethod
    def _sanitize_filename(file: FileConversionInput) -> str:
        raw_name = file.get("name", "").strip()
        filename = Path(raw_name).name
        if not filename:
            filename = "attachment.bin"

        sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        sanitized = sanitized.lstrip(".")
        if not sanitized:
            sanitized = "attachment.bin"
        return sanitized
