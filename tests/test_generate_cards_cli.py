from __future__ import annotations

import base64
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from anki_ai.generate_cards_cli import main
from anki_ai.generation_service import GenerationServiceError


class FakeCardGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.response = {
            "cards": [
                {
                    "id": "generated-1",
                    "cardType": "basic",
                    "front": "Front 1",
                    "back": "Back 1",
                },
                {
                    "id": "generated-2",
                    "cardType": "basic",
                    "front": "Front 2",
                    "back": "Back 2",
                },
            ],
            "run": {"workspacePath": "/tmp/fake-run"},
        }

    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: list[dict[str, str]] | tuple[()] = (),
        card_count: int = 5,
        card_type: str = "basic",
    ) -> dict[str, object]:
        self.calls.append(
            {
                "source_text": source_text,
                "materials": list(materials),
                "card_count": card_count,
                "card_type": card_type,
            }
        )
        return self.response


class ErrorCardGenerator:
    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: list[dict[str, str]] | tuple[()] = (),
        card_count: int = 5,
        card_type: str = "basic",
    ) -> dict[str, object]:
        _ = source_text
        _ = materials
        _ = card_count
        _ = card_type
        raise GenerationServiceError(
            "claude_generation_failed",
            "Claude Code generation failed.",
            {"workspacePath": "/tmp/failure-run"},
        )


class GenerateCardsCliTest(unittest.TestCase):
    def test_main_reads_file_material_and_writes_derived_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            material_path = Path(temp_dir) / "notes.md"
            material_path.write_text("# Notes\n", encoding="utf-8")
            output_path = Path(temp_dir) / "notes.md.json"

            service = FakeCardGenerator()
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                [str(material_path), "--card-count", "7"],
                service=service,
                stdout=stdout,
                stderr=stderr,
            )
            written = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(stdout.getvalue().strip(), str(output_path))
        self.assertEqual(
            json.loads(written),
            [
                {"Front": "Front 1", "Back": "Back 1"},
                {"Front": "Front 2", "Back": "Back 2"},
            ],
        )
        self.assertEqual(len(service.calls), 1)
        call = service.calls[0]
        self.assertEqual(call["card_count"], 7)
        self.assertEqual(call["card_type"], "basic")
        materials = call["materials"]
        self.assertIsInstance(materials, list)
        assert isinstance(materials, list)
        self.assertEqual(materials[0]["name"], "notes.md")
        self.assertEqual(
            base64.b64decode(materials[0]["contentBase64"]),
            b"# Notes\n",
        )

    def test_main_writes_explanation_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            material_path = Path(temp_dir) / "notes.md"
            material_path.write_text("# Notes\n", encoding="utf-8")
            output_path = Path(temp_dir) / "notes.md.json"

            service = FakeCardGenerator()
            service.response = {
                "cards": [
                    {
                        "id": "generated-1",
                        "cardType": "answer_with_explanation",
                        "front": "Front",
                        "back": "Back",
                        "explanation": "Because the source says so.",
                    }
                ],
                "run": {"workspacePath": "/tmp/fake-run"},
            }
            stdout = StringIO()
            stderr = StringIO()

            exit_code = main(
                [
                    str(material_path),
                    "--card-type",
                    "answer_with_explanation",
                ],
                service=service,
                stdout=stdout,
                stderr=stderr,
            )
            written = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(stdout.getvalue().strip(), str(output_path))
        self.assertEqual(
            json.loads(written),
            [
                {
                    "Front": "Front",
                    "Back": "Back",
                    "Explanation": "Because the source says so.",
                }
            ],
        )
        self.assertEqual(service.calls[0]["card_type"], "answer_with_explanation")

    def test_main_reports_generation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            material_path = Path(temp_dir) / "input.pdf"
            material_path.write_bytes(b"%PDF-1.4\n")

            stdout = StringIO()
            stderr = StringIO()
            exit_code = main(
                [str(material_path)],
                service=ErrorCardGenerator(),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "Card generation failed: Claude Code generation failed.",
            stderr.getvalue(),
        )
        self.assertIn("/tmp/failure-run", stderr.getvalue())

    def test_main_rejects_missing_material_file(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        exit_code = main(
            ["/tmp/does-not-exist.txt"],
            service=FakeCardGenerator(),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Material file not found", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
