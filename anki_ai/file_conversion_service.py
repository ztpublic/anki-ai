"""MarkItDown-backed file conversion service."""

from __future__ import annotations

import base64
import importlib
import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast
from urllib.parse import unquote, urlparse


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
ADDON_DIR = Path(__file__).resolve().parent
ADDON_VENDOR_DIR = ADDON_DIR / "vendor"
PROJECT_ROOT = ADDON_DIR.parent


def _default_workspace_factory() -> Path:
    return Path(tempfile.mkdtemp(prefix="anki-ai-file-conversion-"))


def _default_converter_factory() -> MarkItDownConverter:
    _bootstrap_conversion_runtime()
    module = importlib.import_module("markitdown")
    return cast(MarkItDownConverter, module.MarkItDown())


def _bootstrap_conversion_runtime() -> None:
    """Make bundled/local conversion dependencies visible inside Anki."""
    _prepend_sys_path(_dependency_path_candidates())


def _dependency_path_candidates() -> list[Path]:
    candidates: list[Path] = []

    local_venv = PROJECT_ROOT / ".venv"
    expected_python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for pattern in (
        "lib/python*/site-packages",
        "lib/python*/dist-packages",
    ):
        candidates.extend(
            candidate
            for candidate in sorted(local_venv.glob(pattern))
            if candidate.parent.name == expected_python_dir
        )

    if ADDON_VENDOR_DIR.is_dir():
        candidates.append(ADDON_VENDOR_DIR)

    return candidates


def _prepend_sys_path(paths: list[Path]) -> None:
    for path in reversed([candidate for candidate in paths if candidate.is_dir()]):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


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

        markdown = self._convert_source(
            source=str(source_path),
            failure_code="file_conversion_failed",
            failure_message=f"Could not convert {filename} to markdown.",
            empty_message=f"{filename} did not produce any markdown output.",
            details={
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

    def convert_url(self, *, url: str) -> FileConversionResult:
        normalized_url = url.strip()
        parsed_url = urlparse(normalized_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise FileConversionServiceError(
                "invalid_url",
                "URL must be an absolute http or https URL.",
                {"url": url},
            )

        filename = self._filename_from_url(normalized_url)
        extension = Path(filename).suffix.lower()
        markdown = self._convert_source(
            source=normalized_url,
            failure_code="url_conversion_failed",
            failure_message=f"Could not convert {normalized_url} to markdown.",
            empty_message=f"{normalized_url} did not produce any markdown output.",
            details={
                "url": normalized_url,
                "fileName": filename,
                "sourceExtension": extension,
            },
        )

        return {
            "document": {
                "name": filename,
                "markdown": markdown,
                "sourceExtension": extension,
            }
        }

    def _convert_source(
        self,
        *,
        source: str,
        failure_code: str,
        failure_message: str,
        empty_message: str,
        details: dict[str, Any],
    ) -> str:
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
            result = converter.convert(source)
        except Exception as error:
            raise FileConversionServiceError(
                failure_code,
                failure_message,
                {**details, "error": str(error)},
            ) from error

        markdown = getattr(result, "text_content", None)
        if not isinstance(markdown, str) or not markdown.strip():
            raise FileConversionServiceError(
                "empty_conversion_output",
                empty_message,
                details,
            )
        return markdown

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

    @staticmethod
    def _filename_from_url(url: str) -> str:
        parsed_url = urlparse(url)
        path_name = Path(unquote(parsed_url.path)).name
        filename = path_name or "page.html"
        suffix = Path(filename).suffix.lower()
        if suffix not in MarkItDownFileConversionService.SUPPORTED_EXTENSIONS:
            filename = f"{filename}.html"
        return MarkItDownFileConversionService._sanitize_filename(
            {"name": filename, "contentBase64": ""}
        )
