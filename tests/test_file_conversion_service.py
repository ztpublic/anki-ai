from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from anki_ai.file_conversion_service import (
    FileConversionServiceError,
    MarkItDownFileConversionService,
)


def file_payload(name: str, content: bytes) -> dict[str, str]:
    return {
        "name": name,
        "contentBase64": base64.b64encode(content).decode("ascii"),
    }


class MarkItDownFileConversionServiceTest(unittest.TestCase):
    def test_supported_extensions_match_markitdown_builtin_file_types(self) -> None:
        self.assertEqual(
            MarkItDownFileConversionService.SUPPORTED_EXTENSIONS,
            frozenset(
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
            ),
        )

    def test_convert_file_supports_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            class FakeMarkItDown:
                def convert(self, source: str) -> object:
                    source_path = Path(source)
                    source_bytes = source_path.read_bytes()
                    assert source_path.name == "lecture.pdf"
                    assert source_bytes == b"%PDF-1.4\n"
                    return SimpleNamespace(text_content="# Lecture\n")

            service = MarkItDownFileConversionService(
                converter_factory=FakeMarkItDown,
                workspace_factory=lambda: workspace_path,
            )

            result = service.convert_file(file=file_payload("lecture.pdf", b"%PDF-1.4\n"))

        self.assertEqual(
            result,
            {
                "document": {
                    "name": "lecture.pdf",
                    "markdown": "# Lecture\n",
                    "sourceExtension": ".pdf",
                }
            },
        )

    def test_convert_file_supports_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            class FakeMarkItDown:
                def convert(self, source: str) -> object:
                    source_path = Path(source)
                    assert source_path.suffix == ".html"
                    assert "<h1>Title</h1>" in source_path.read_text(encoding="utf-8")
                    return SimpleNamespace(text_content="# Title\n")

            service = MarkItDownFileConversionService(
                converter_factory=FakeMarkItDown,
                workspace_factory=lambda: workspace_path,
            )

            result = service.convert_file(
                file=file_payload("page.html", b"<html><h1>Title</h1></html>")
            )

        self.assertEqual(result["document"]["sourceExtension"], ".html")
        self.assertEqual(result["document"]["markdown"], "# Title\n")

    def test_convert_url_passes_url_directly_to_markitdown(self) -> None:
        class FakeMarkItDown:
            def convert(self, source: str) -> object:
                assert source == "https://example.com/article"
                return SimpleNamespace(text_content="# Article\n")

        service = MarkItDownFileConversionService(converter_factory=FakeMarkItDown)

        result = service.convert_url(url="https://example.com/article")

        self.assertEqual(
            result,
            {
                "document": {
                    "name": "article.html",
                    "markdown": "# Article\n",
                    "sourceExtension": ".html",
                }
            },
        )

    def test_convert_url_rejects_non_http_url(self) -> None:
        service = MarkItDownFileConversionService(converter_factory=lambda: object())

        with self.assertRaises(FileConversionServiceError) as error:
            service.convert_url(url="/tmp/page.html")

        self.assertEqual(error.exception.code, "invalid_url")

    def test_convert_url_preserves_supported_url_extension(self) -> None:
        class FakeMarkItDown:
            def convert(self, source: str) -> object:
                assert source == "https://example.com/lecture.pdf"
                return SimpleNamespace(text_content="# Lecture\n")

        service = MarkItDownFileConversionService(converter_factory=FakeMarkItDown)

        result = service.convert_url(url="https://example.com/lecture.pdf")

        self.assertEqual(result["document"]["name"], "lecture.pdf")
        self.assertEqual(result["document"]["sourceExtension"], ".pdf")

    def test_convert_file_supports_docx(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            class FakeMarkItDown:
                def convert(self, source: str) -> object:
                    source_path = Path(source)
                    assert source_path.suffix == ".docx"
                    assert source_path.read_bytes() == b"docx-bytes"
                    return SimpleNamespace(text_content="# Notes\n")

            service = MarkItDownFileConversionService(
                converter_factory=FakeMarkItDown,
                workspace_factory=lambda: workspace_path,
            )

            result = service.convert_file(file=file_payload("notes.docx", b"docx-bytes"))

        self.assertEqual(result["document"]["sourceExtension"], ".docx")
        self.assertEqual(result["document"]["markdown"], "# Notes\n")

    def test_convert_file_rejects_unsupported_extension(self) -> None:
        service = MarkItDownFileConversionService(converter_factory=lambda: object())

        with self.assertRaises(FileConversionServiceError) as error:
            service.convert_file(file=file_payload("notes.exe", b"data"))

        self.assertEqual(error.exception.code, "unsupported_file_type")

    def test_convert_file_rejects_invalid_base64_payload(self) -> None:
        service = MarkItDownFileConversionService(converter_factory=lambda: object())

        with self.assertRaises(FileConversionServiceError) as error:
            service.convert_file(
                file={"name": "page.html", "contentBase64": "%%%"},
            )

        self.assertEqual(error.exception.code, "invalid_file_payload")

    def test_convert_file_surfaces_missing_markitdown_dependency(self) -> None:
        service = MarkItDownFileConversionService()

        with patch(
            "anki_ai.file_conversion_service.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'markitdown'"),
        ):
            with self.assertRaises(FileConversionServiceError) as error:
                service.convert_file(file=file_payload("page.html", b"<html></html>"))

        self.assertEqual(error.exception.code, "markitdown_not_available")

    def test_convert_file_rejects_empty_output(self) -> None:
        service = MarkItDownFileConversionService(
            converter_factory=lambda: SimpleNamespace(
                convert=lambda source: SimpleNamespace(text_content="  ")
            )
        )

        with self.assertRaises(FileConversionServiceError) as error:
            service.convert_file(file=file_payload("page.html", b"<html></html>"))

        self.assertEqual(error.exception.code, "empty_conversion_output")


if __name__ == "__main__":
    unittest.main()
