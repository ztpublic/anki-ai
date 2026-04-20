from __future__ import annotations

import json
import unittest

from anki_ai.file_conversion_service import FileConversionServiceError
from anki_ai.file_conversion_transport import (
    register_file_conversion_transport_handlers,
)
from anki_ai.transport import PROTOCOL, JsonObject, TransportRouter


def request_message(
    method: str,
    params: JsonObject | None = None,
    request_id: str = "req-1",
) -> str:
    return json.dumps(
        {
            "protocol": PROTOCOL,
            "kind": "request",
            "id": request_id,
            "method": method,
            "params": {} if params is None else params,
        }
    )


class FakeFileConversionService:
    def __init__(self) -> None:
        self.file_calls: list[dict[str, str]] = []
        self.url_calls: list[str] = []

    def convert_file(
        self,
        *,
        file: dict[str, str],
    ) -> JsonObject:
        self.file_calls.append(file)
        return {
            "document": {
                "name": file["name"],
                "markdown": "# Converted\n",
                "sourceExtension": ".pdf",
            }
        }

    def convert_url(
        self,
        *,
        url: str,
    ) -> JsonObject:
        self.url_calls.append(url)
        return {
            "document": {
                "name": "article.html",
                "markdown": "# Converted URL\n",
                "sourceExtension": ".html",
            }
        }


class ErrorFileConversionService:
    def convert_file(
        self,
        *,
        file: dict[str, str],
    ) -> JsonObject:
        _ = file
        raise FileConversionServiceError(
            "unsupported_file_type",
            "This file type is not currently supported for conversion.",
            {
                "supportedExtensions": [
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
                ]
            },
        )

    def convert_url(
        self,
        *,
        url: str,
    ) -> JsonObject:
        _ = url
        raise FileConversionServiceError(
            "url_conversion_failed",
            "Could not convert https://example.com to markdown.",
        )


class FileConversionTransportHandlersTest(unittest.TestCase):
    def test_convert_to_markdown_accepts_file_payload(self) -> None:
        service = FakeFileConversionService()
        router = TransportRouter()
        register_file_conversion_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message(
                "anki.files.convertToMarkdown",
                {"file": {"name": "lecture.pdf", "contentBase64": "aGVsbG8="}},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(
            service.file_calls,
            [{"name": "lecture.pdf", "contentBase64": "aGVsbG8="}],
        )
        self.assertEqual(response["result"]["document"]["name"], "lecture.pdf")

    def test_convert_to_markdown_accepts_url_payload(self) -> None:
        service = FakeFileConversionService()
        router = TransportRouter()
        register_file_conversion_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message(
                "anki.files.convertToMarkdown",
                {"url": "https://example.com/article"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(service.url_calls, ["https://example.com/article"])
        self.assertEqual(response["result"]["document"]["name"], "article.html")

    def test_convert_to_markdown_requires_file_object(self) -> None:
        service = FakeFileConversionService()
        router = TransportRouter()
        register_file_conversion_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message("anki.files.convertToMarkdown", {})
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")

    def test_convert_to_markdown_rejects_file_and_url_together(self) -> None:
        service = FakeFileConversionService()
        router = TransportRouter()
        register_file_conversion_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message(
                "anki.files.convertToMarkdown",
                {
                    "file": {"name": "lecture.pdf", "contentBase64": "aGVsbG8="},
                    "url": "https://example.com/article",
                },
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")

    def test_convert_to_markdown_preserves_service_error_code(self) -> None:
        router = TransportRouter()
        register_file_conversion_transport_handlers(router, ErrorFileConversionService())

        response = router.handle_raw_message(
            request_message(
                "anki.files.convertToMarkdown",
                {"file": {"name": "notes.exe", "contentBase64": "aGVsbG8="}},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "unsupported_file_type")


if __name__ == "__main__":
    unittest.main()
