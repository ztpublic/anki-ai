from __future__ import annotations

import base64
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from anki_ai.convert_pdf_to_markdown_cli import main
from anki_ai.file_conversion_service import FileConversionServiceError


class FakeFileConverter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.response = {
            "document": {
                "name": "notes.pdf",
                "markdown": "# Notes\n\nConverted.\n",
                "sourceExtension": ".pdf",
            }
        }

    def convert_file(self, *, file: dict[str, str]) -> dict[str, object]:
        self.calls.append({"file": dict(file)})
        return self.response


class ErrorFileConverter:
    def convert_file(self, *, file: dict[str, str]) -> dict[str, object]:
        _ = file
        raise FileConversionServiceError(
            "file_conversion_failed",
            "Could not convert notes.pdf to markdown.",
            {"workspacePath": "/tmp/failure-run"},
        )


class ConvertPdfToMarkdownCliTest(unittest.TestCase):
    def test_main_writes_derived_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            material_path = Path(temp_dir) / "notes.pdf"
            material_path.write_bytes(b"%PDF-1.4\n")
            output_path = Path(temp_dir) / "notes.pdf.md"

            service = FakeFileConverter()
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                [str(material_path)],
                service=service,
                stdout=stdout,
                stderr=stderr,
            )
            written = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(stdout.getvalue().strip(), str(output_path))
        self.assertEqual(written, "# Notes\n\nConverted.\n")
        self.assertEqual(len(service.calls), 1)
        call = service.calls[0]
        file_payload = call["file"]
        self.assertIsInstance(file_payload, dict)
        assert isinstance(file_payload, dict)
        self.assertEqual(file_payload["name"], "notes.pdf")
        self.assertEqual(
            base64.b64decode(file_payload["contentBase64"]),
            b"%PDF-1.4\n",
        )

    def test_main_can_write_markdown_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            material_path = Path(temp_dir) / "notes.pdf"
            material_path.write_bytes(b"%PDF-1.4\n")

            stdout = StringIO()
            stderr = StringIO()
            exit_code = main(
                [str(material_path), "--stdout"],
                service=FakeFileConverter(),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(stdout.getvalue(), "# Notes\n\nConverted.\n")

    def test_main_reports_conversion_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            material_path = Path(temp_dir) / "notes.pdf"
            material_path.write_bytes(b"%PDF-1.4\n")

            stdout = StringIO()
            stderr = StringIO()
            exit_code = main(
                [str(material_path)],
                service=ErrorFileConverter(),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "File conversion failed: Could not convert notes.pdf to markdown.",
            stderr.getvalue(),
        )
        self.assertIn("/tmp/failure-run", stderr.getvalue())

    def test_main_rejects_missing_material_file(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        exit_code = main(
            ["/tmp/does-not-exist.pdf"],
            service=FakeFileConverter(),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Material file not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
