from __future__ import annotations

import base64
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from anki_ai.generation_service import (
    RATE_LIMIT_ERROR_CODE,
    ClaudeCardGenerationService,
    GenerationServiceError,
    _run_claude_generation_async,
)


def material_payload(name: str, content: bytes) -> dict[str, str]:
    return {
        "name": name,
        "contentBase64": base64.b64encode(content).decode("ascii"),
    }


class ClaudeCardGenerationServiceTest(unittest.TestCase):
    def test_generate_cards_prepares_materials_and_returns_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertEqual(workspace, workspace_path)
                self.assertIn("approximately 3 useful Anki flashcards", prompt)
                self.assertEqual(
                    (workspace / "materials" / "source.txt").read_text(encoding="utf-8"),
                    "Important facts",
                )
                self.assertEqual(
                    (workspace / "materials" / "notes.md").read_bytes(),
                    b"# Notes\n",
                )
                (workspace / "cards.json").write_text(
                    json.dumps(
                        [
                            {"Front": "Question 1", "Back": "Answer 1"},
                            {"Front": "Question 2", "Back": "Answer 2"},
                        ]
                    ),
                    encoding="utf-8",
                )
                return {"sessionId": "session-1", "stopReason": "end_turn"}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            result = service.generate_cards(
                source_text="Important facts",
                materials=[material_payload("notes.md", b"# Notes\n")],
                card_count=3,
            )

        self.assertEqual(
            result["cards"],
            [
                {"id": "generated-1", "front": "Question 1", "back": "Answer 1"},
                {"id": "generated-2", "front": "Question 2", "back": "Answer 2"},
            ],
        )
        self.assertEqual(
            result["run"],
            {
                "workspacePath": str(workspace_path),
                "sessionId": "session-1",
                "stopReason": "end_turn",
            },
        )

    def test_generate_cards_requires_cards_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                _ = prompt
                _ = workspace
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            with self.assertRaises(GenerationServiceError) as error:
                service.generate_cards(source_text="Important facts")

        self.assertEqual(error.exception.code, "missing_cards_output")

    def test_generate_cards_rejects_invalid_card_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                _ = prompt
                (workspace / "cards.json").write_text(
                    json.dumps([{"Front": "Question only"}]),
                    encoding="utf-8",
                )
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            with self.assertRaises(GenerationServiceError) as error:
                service.generate_cards(source_text="Important facts")

        self.assertEqual(error.exception.code, "invalid_cards_output")

    def test_generate_cards_rejects_invalid_material_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            service = ClaudeCardGenerationService(
                runner=lambda prompt, workspace: {},
                workspace_factory=lambda: workspace_path,
            )

            with self.assertRaises(GenerationServiceError) as error:
                service.generate_cards(
                    materials=[{"name": "bad.bin", "contentBase64": "%%%"}],
                )

        self.assertEqual(error.exception.code, "invalid_material_payload")

    def test_run_claude_generation_surfaces_rate_limit_details(self) -> None:
        class FakeClaudeAgentOptions:
            def __init__(self, **kwargs: object) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)

        async def fake_query(*, prompt: str, options: object) -> object:
            _ = prompt
            self.assertEqual(getattr(options, "permission_mode", None), "bypassPermissions")
            stderr = getattr(options, "stderr", None)
            if callable(stderr):
                stderr(
                    'API error (attempt 1/11): 429 429 {"error":{"code":"1302","message":"您的账户已达到速率限制，请您控制请求频率"}}'
                )
            if False:
                yield None

            class ProcessError(Exception):
                pass

            raise ProcessError(
                "Command failed with exit code 1 (exit code: 1)\n"
                "Error output: Check stderr output for details"
            )

        fake_sdk = SimpleNamespace(
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )

        with patch(
            "anki_ai.generation_service.importlib.import_module",
            return_value=fake_sdk,
        ):
            with self.assertRaises(GenerationServiceError) as error:
                asyncio.run(
                    _run_claude_generation_async("Prompt", Path("/tmp/fake-workspace"))
                )

        self.assertEqual(error.exception.code, RATE_LIMIT_ERROR_CODE)
        assert isinstance(error.exception.details, dict)
        self.assertIn("Command failed with exit code 1", error.exception.details["error"])
        self.assertTrue(error.exception.details["stderr"])
        self.assertIn("429 429", error.exception.details["stderr"][0])

    def test_run_claude_generation_includes_stderr_on_result_error(self) -> None:
        class FakeClaudeAgentOptions:
            def __init__(self, **kwargs: object) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)

        class ResultMessage:
            def __init__(self) -> None:
                self.is_error = True
                self.errors = [{"message": "bad response"}]
                self.result = "Model returned invalid output"
                self.session_id = None
                self.stop_reason = None

        async def fake_query(*, prompt: str, options: object) -> object:
            _ = prompt
            self.assertEqual(getattr(options, "permission_mode", None), "bypassPermissions")
            stderr = getattr(options, "stderr", None)
            if callable(stderr):
                stderr("Non-rate-limit stderr detail")
            yield ResultMessage()

        fake_sdk = SimpleNamespace(
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )

        with patch(
            "anki_ai.generation_service.importlib.import_module",
            return_value=fake_sdk,
        ):
            with self.assertRaises(GenerationServiceError) as error:
                asyncio.run(
                    _run_claude_generation_async("Prompt", Path("/tmp/fake-workspace"))
                )

        self.assertEqual(error.exception.code, "claude_generation_failed")
        assert isinstance(error.exception.details, dict)
        self.assertEqual(error.exception.details["result"], "Model returned invalid output")
        self.assertEqual(error.exception.details["stderr"], ["Non-rate-limit stderr detail"])


if __name__ == "__main__":
    unittest.main()
