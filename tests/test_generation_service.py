from __future__ import annotations

import base64
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from anki_ai.file_conversion_service import FileConversionServiceError
from anki_ai import generation_service as generation_module
from anki_ai.generation_service import (
    RATE_LIMIT_ERROR_CODE,
    ClaudeCardGenerationService,
    GenerationLogEvent,
    GenerationServiceError,
    _generation_environment,
    _run_claude_generation_async,
)


def material_payload(name: str, content: bytes) -> dict[str, str]:
    return {
        "name": name,
        "contentBase64": base64.b64encode(content).decode("ascii"),
    }


def log_messages(logs: list[GenerationLogEvent]) -> list[str]:
    return [log["message"] for log in logs]


class ClaudeCardGenerationServiceTest(unittest.TestCase):
    def test_generate_cards_prepares_materials_and_returns_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertEqual(workspace, workspace_path)
                self.assertIn("Target card count: 3", prompt)
                self.assertIn("Every card must test one clear knowledge point.", prompt)
                self.assertIn("Each \"Front\" must be context-free", prompt)
                self.assertIn("normally 3-18 words", prompt)
                self.assertIn("Never refer to item numbers", prompt)
                self.assertIn(
                    "Expand abbreviations, acronyms, and initialisms in card text",
                    prompt,
                )
                self.assertIn(
                    "retrieval-augmented generation (RAG)",
                    prompt,
                )
                self.assertIn(
                    "Are abbreviations expanded or clearly defined on the card itself?",
                    prompt,
                )
                self.assertIn("Delete or rewrite any card that fails the audit.", prompt)
                self.assertIn('Each flashcard must be a JSON object with exactly these fields:', prompt)
                self.assertIn('- "Front": string', prompt)
                self.assertIn('- "Back": string', prompt)
                self.assertNotIn('- "Explanation": string', prompt)
                self.assertNotIn("answer_with_explanation", prompt)
                self.assertIn("- user_input.txt", prompt)
                self.assertIn("- notes.md", prompt)
                self.assertEqual(
                    (workspace / "materials" / "user_input.txt").read_text(
                        encoding="utf-8"
                    ),
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
                {
                    "id": "generated-1",
                    "cardType": "basic",
                    "front": "Question 1",
                    "back": "Answer 1",
                },
                {
                    "id": "generated-2",
                    "cardType": "basic",
                    "front": "Question 2",
                    "back": "Answer 2",
                },
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

    def test_generate_cards_injects_instructions_without_materializing_them(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertIn("- notes.md", prompt)
                self.assertIn("Additional user instructions:", prompt)
                self.assertIn("Only generate yes/no questions.", prompt)
                self.assertIn("not as learning material", prompt)
                self.assertNotIn("- user_input.txt", prompt)
                self.assertFalse(
                    (workspace / "materials" / "user_input.txt").exists()
                )
                self.assertEqual(
                    (workspace / "materials" / "notes.md").read_bytes(),
                    b"# Notes\n",
                )
                (workspace / "cards.json").write_text(
                    json.dumps([{"Front": "Question", "Back": "Answer"}]),
                    encoding="utf-8",
                )
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            result = service.generate_cards(
                materials=[material_payload("notes.md", b"# Notes\n")],
                instructions="Only generate yes/no questions.",
            )

        self.assertEqual(
            result["cards"],
            [
                {
                    "id": "generated-1",
                    "cardType": "basic",
                    "front": "Question",
                    "back": "Answer",
                }
            ],
        )

    def test_generate_cards_converts_non_markdown_material_to_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            class FakeMaterialConverter:
                def __init__(self) -> None:
                    self.calls: list[dict[str, str]] = []

                def convert_file(self, *, file: dict[str, str]) -> dict[str, object]:
                    self.calls.append(file)
                    return {
                        "document": {
                            "name": "lecture.pdf",
                            "markdown": "# Lecture\n\nConverted notes.\n",
                            "sourceExtension": ".pdf",
                        }
                    }

            converter = FakeMaterialConverter()

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertIn("- lecture.md", prompt)
                self.assertNotIn("- lecture.pdf", prompt)
                self.assertEqual(
                    (workspace / "materials" / "lecture.md").read_text(
                        encoding="utf-8"
                    ),
                    "# Lecture\n\nConverted notes.\n",
                )
                self.assertFalse((workspace / "materials" / "lecture.pdf").exists())
                (workspace / "cards.json").write_text(
                    json.dumps([{"Front": "Question", "Back": "Answer"}]),
                    encoding="utf-8",
                )
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
                material_converter=converter,
            )
            logs: list[GenerationLogEvent] = []

            result = service.generate_cards(
                materials=[material_payload("lecture.pdf", b"%PDF-1.4\n")],
                log_sink=logs.append,
            )

        self.assertEqual(
            result["cards"],
            [
                {
                    "id": "generated-1",
                    "cardType": "basic",
                    "front": "Question",
                    "back": "Answer",
                }
            ],
        )
        self.assertEqual(len(converter.calls), 1)
        self.assertEqual(converter.calls[0]["name"], "lecture.pdf")
        self.assertEqual(
            base64.b64decode(converter.calls[0]["contentBase64"]),
            b"%PDF-1.4\n",
        )
        self.assertEqual(
            log_messages(logs),
            [
                "Converting lecture.pdf to markdown for card generation.",
                "Converted lecture.pdf to lecture.md (28 characters).",
            ],
        )

    def test_generate_cards_copies_markdown_material_without_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            class FailingMaterialConverter:
                def convert_file(self, *, file: dict[str, str]) -> dict[str, object]:
                    _ = file
                    raise AssertionError("markdown material should not be converted")

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertIn("- notes.markdown", prompt)
                self.assertEqual(
                    (workspace / "materials" / "notes.markdown").read_bytes(),
                    b"# Notes\n",
                )
                (workspace / "cards.json").write_text(
                    json.dumps([{"Front": "Question", "Back": "Answer"}]),
                    encoding="utf-8",
                )
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
                material_converter=FailingMaterialConverter(),
            )
            logs: list[GenerationLogEvent] = []

            result = service.generate_cards(
                materials=[material_payload("notes.markdown", b"# Notes\n")],
                log_sink=logs.append,
            )

        self.assertEqual(
            result["cards"],
            [
                {
                    "id": "generated-1",
                    "cardType": "basic",
                    "front": "Question",
                    "back": "Answer",
                }
            ],
        )
        self.assertEqual(logs, [])

    def test_generate_cards_surfaces_material_conversion_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            class FailingMaterialConverter:
                def convert_file(self, *, file: dict[str, str]) -> dict[str, object]:
                    _ = file
                    raise FileConversionServiceError(
                        "unsupported_file_type",
                        "This file type is not currently supported for conversion.",
                        {"sourceExtension": ".exe"},
                    )

            service = ClaudeCardGenerationService(
                runner=lambda prompt, workspace: {},
                workspace_factory=lambda: workspace_path,
                material_converter=FailingMaterialConverter(),
            )
            logs: list[GenerationLogEvent] = []

            with self.assertRaises(GenerationServiceError) as error:
                service.generate_cards(
                    materials=[material_payload("notes.exe", b"binary")],
                    log_sink=logs.append,
                )

        self.assertEqual(error.exception.code, "material_conversion_failed")
        assert isinstance(error.exception.details, dict)
        self.assertEqual(
            error.exception.details["conversionCode"],
            "unsupported_file_type",
        )
        self.assertEqual(error.exception.details["materialName"], "notes.exe")
        self.assertEqual(error.exception.details["workspacePath"], str(workspace_path))
        self.assertEqual(
            log_messages(logs),
            [
                "Converting notes.exe to markdown for card generation.",
                (
                    "Failed to convert notes.exe to markdown: This file type is not "
                    "currently supported for conversion."
                ),
            ],
        )

    def test_bootstrap_generation_runtime_adds_bundled_paths(self) -> None:
        original_sys_path = list(sys.path)
        original_path = os.environ.get("PATH", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vendor_dir = root / "vendor"
            python_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"
            site_packages_dir = root / ".venv" / "lib" / python_dir / "site-packages"
            cli_dir = root / "bin"
            vendor_dir.mkdir()
            site_packages_dir.mkdir(parents=True)
            cli_dir.mkdir()

            try:
                with (
                    patch.object(generation_module, "ADDON_VENDOR_DIR", vendor_dir),
                    patch.object(generation_module, "PROJECT_ROOT", root),
                    patch.object(
                        generation_module,
                        "_cli_path_candidates",
                        return_value=[cli_dir],
                    ),
                ):
                    generation_module._bootstrap_generation_runtime()

                self.assertEqual(sys.path[0], str(vendor_dir))
                self.assertIn(str(site_packages_dir), sys.path)
                self.assertTrue(
                    os.environ.get("PATH", "").startswith(
                        f"{cli_dir}{os.pathsep}"
                    )
                )
            finally:
                sys.path[:] = original_sys_path
                os.environ["PATH"] = original_path

    def test_generation_environment_uses_runtime_env_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "generation": {
                            "anthropicAuthToken": "configured-token",
                            "anthropicBaseUrl": "https://example.test",
                            "anthropicModel": "configured-model",
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ANKI_AI_CONFIG_PATH": str(config_path),
                    "ANTHROPIC_API_KEY": "env-api-key",
                    "ANTHROPIC_AUTH_TOKEN": "",
                },
                clear=False,
            ):
                env = _generation_environment()

        self.assertEqual(env["ANTHROPIC_API_KEY"], "env-api-key")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "configured-token")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://example.test")
        self.assertEqual(env["ANTHROPIC_MODEL"], "configured-model")

    def test_generation_environment_loads_shell_startup_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zshrc_path = Path(temp_dir) / ".zshrc"
            missing_path = Path(temp_dir) / ".zprofile"
            zshrc_path.write_text(
                "\n".join(
                    [
                        "export ANTHROPIC_AUTH_TOKEN='shell-token'",
                        'ANTHROPIC_BASE_URL="https://shell.example" # provider',
                        "ANTHROPIC_MODEL=shell-model",
                        "UNRELATED_SECRET=ignored",
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch.object(
                    generation_module,
                    "_shell_env_file_candidates",
                    return_value=[missing_path, zshrc_path],
                ),
                patch.object(generation_module, "ADDON_CONFIG_PATH", missing_path),
                patch.object(
                    generation_module,
                    "ADDON_LOCAL_CONFIG_PATH",
                    missing_path,
                ),
                patch.dict(os.environ, {}, clear=True),
            ):
                env = _generation_environment()

        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "shell-token")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://shell.example")
        self.assertEqual(env["ANTHROPIC_MODEL"], "shell-model")
        self.assertNotIn("UNRELATED_SECRET", env)

    def test_generation_environment_uses_local_config_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config_path = Path(temp_dir) / "config.json"
            local_config_path = Path(temp_dir) / "config.local.json"
            base_config_path.write_text(
                json.dumps(
                    {
                        "generation": {
                            "anthropicBaseUrl": "https://base.example",
                            "anthropicModel": "base-model",
                        }
                    }
                ),
                encoding="utf-8",
            )
            local_config_path.write_text(
                json.dumps(
                    {
                        "generation": {
                            "anthropicAuthToken": "local-token",
                            "anthropicModel": "local-model",
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(
                    generation_module,
                    "ADDON_CONFIG_PATH",
                    base_config_path,
                ),
                patch.object(
                    generation_module,
                    "ADDON_LOCAL_CONFIG_PATH",
                    local_config_path,
                ),
                patch.dict(os.environ, {"ANKI_AI_CONFIG_PATH": ""}, clear=False),
            ):
                env = _generation_environment()

        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "local-token")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://base.example")
        self.assertEqual(env["ANTHROPIC_MODEL"], "local-model")

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

    def test_generate_cards_accepts_lowercase_card_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                _ = prompt
                (workspace / "cards.json").write_text(
                    json.dumps([{"front": "Question", "back": "Answer"}]),
                    encoding="utf-8",
                )
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            result = service.generate_cards(source_text="Important facts")

        self.assertEqual(
            result["cards"],
            [
                {
                    "id": "generated-1",
                    "cardType": "basic",
                    "front": "Question",
                    "back": "Answer",
                }
            ],
        )

    def test_generate_cards_rejects_removed_answer_with_explanation_card_type(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                _ = prompt
                _ = workspace
                self.fail("runner should not be called for a removed card type")
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            with self.assertRaises(GenerationServiceError) as error:
                service.generate_cards(
                    source_text="Important facts",
                    card_type="answer_with_explanation",
                )

        self.assertEqual(error.exception.code, "invalid_card_type")

    def test_regenerate_answer_writes_input_and_returns_replacement_answer(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertEqual(workspace, workspace_path)
                self.assertIn("regenerated_card.json", prompt)
                self.assertIn('"OriginalAnswer"', prompt)
                self.assertIn('- "Back": string', prompt)
                self.assertIn("Output only the improved answer", prompt)
                self.assertNotIn('- "Explanation": string', prompt)
                self.assertEqual(
                    json.loads((workspace / "card.json").read_text(encoding="utf-8")),
                    {
                        "Question": "What does retrieval practice strengthen?",
                        "OriginalAnswer": "Memory",
                        "OriginalExplanation": "Practice strengthens recall routes.",
                    },
                )
                (workspace / "regenerated_card.json").write_text(
                    json.dumps({"Back": "Long-term recall"}),
                    encoding="utf-8",
                )
                return {"sessionId": "session-1", "stopReason": "end_turn"}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            result = service.regenerate_answer(
                question="What does retrieval practice strengthen?",
                answer="Memory",
                explanation="Practice strengthens recall routes.",
            )

        self.assertEqual(
            result,
            {
                "fields": {"answer": "Long-term recall"},
                "run": {
                    "workspacePath": str(workspace_path),
                    "sessionId": "session-1",
                    "stopReason": "end_turn",
                },
            },
        )

    def test_regenerate_answer_uses_user_instructions_instead_of_default_goals(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertEqual(workspace, workspace_path)
                self.assertIn("User regeneration instructions:", prompt)
                self.assertIn("Add more explanation to the answer.", prompt)
                self.assertIn("Use them instead of the default improvement goals", prompt)
                self.assertNotIn("Improve the card by fixing issues such as", prompt)
                self.assertIn("Non-negotiable constraints:", prompt)
                (workspace / "regenerated_card.json").write_text(
                    json.dumps({"Back": "Memory, with stronger recall paths"}),
                    encoding="utf-8",
                )
                return {}

            service = ClaudeCardGenerationService(
                runner=runner,
                workspace_factory=lambda: workspace_path,
            )

            result = service.regenerate_answer(
                question="What does retrieval practice strengthen?",
                answer="Memory",
                explanation="Practice strengthens recall routes.",
                instructions="Add more explanation to the answer.",
            )

        self.assertEqual(
            result["fields"],
            {"answer": "Memory, with stronger recall paths"},
        )

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

    def test_run_claude_generation_surfaces_auth_missing(self) -> None:
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
                    "API error: Could not resolve authentication method. "
                    "Expected either apiKey or authToken to be set."
                )
            if False:
                yield None

            class ProcessError(Exception):
                pass

            raise ProcessError("Command failed with exit code 1")

        fake_sdk = SimpleNamespace(
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )

        with (
            patch(
                "anki_ai.generation_service.importlib.import_module",
                return_value=fake_sdk,
            ),
            patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": ""}, clear=False),
        ):
            with self.assertRaises(GenerationServiceError) as error:
                asyncio.run(
                    _run_claude_generation_async("Prompt", Path("/tmp/fake-workspace"))
                )

        self.assertEqual(error.exception.code, "claude_auth_missing")
        self.assertIn("authentication is not configured", error.exception.message)

    def test_run_claude_generation_passes_generation_env_and_cli_path(self) -> None:
        captured_options: object | None = None

        class FakeClaudeAgentOptions:
            def __init__(self, **kwargs: object) -> None:
                nonlocal captured_options
                captured_options = self
                for key, value in kwargs.items():
                    setattr(self, key, value)

        class ResultMessage:
            def __init__(self) -> None:
                self.is_error = False
                self.errors = []
                self.result = ""
                self.session_id = "session-1"
                self.stop_reason = "end_turn"

        async def fake_query(*, prompt: str, options: object) -> object:
            _ = prompt
            _ = options
            yield ResultMessage()

        fake_sdk = SimpleNamespace(
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )

        with (
            patch.object(
                generation_module,
                "_configured_claude_cli_path",
                return_value="/fake/bin/claude",
            ),
            patch(
                "anki_ai.generation_service.importlib.import_module",
                return_value=fake_sdk,
            ),
            patch.dict(
                os.environ,
                {
                    "ANTHROPIC_AUTH_TOKEN": "env-auth-token",
                    "ANTHROPIC_BASE_URL": "https://example.test",
                },
                clear=False,
            ),
        ):
            metadata = asyncio.run(
                _run_claude_generation_async("Prompt", Path("/tmp/fake-workspace"))
            )

        self.assertEqual(metadata["sessionId"], "session-1")
        self.assertIsNotNone(captured_options)
        assert captured_options is not None
        self.assertEqual(getattr(captured_options, "cli_path", None), "/fake/bin/claude")
        option_env = getattr(captured_options, "env", {})
        self.assertEqual(option_env["ANTHROPIC_AUTH_TOKEN"], "env-auth-token")
        self.assertEqual(option_env["ANTHROPIC_BASE_URL"], "https://example.test")

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

    def test_run_claude_generation_filters_stderr_below_error(self) -> None:
        class FakeClaudeAgentOptions:
            def __init__(self, **kwargs: object) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)

        class ResultMessage:
            def __init__(self) -> None:
                self.is_error = False
                self.errors = []
                self.result = ""
                self.session_id = "session-1"
                self.stop_reason = "end_turn"

        async def fake_query(*, prompt: str, options: object) -> object:
            _ = prompt
            stderr = getattr(options, "stderr", None)
            if callable(stderr):
                stderr("[DEBUG] Claude debug line")
                stderr("[ERROR] Claude error line")
            yield ResultMessage()

        fake_sdk = SimpleNamespace(
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )
        logs: list[GenerationLogEvent] = []

        with patch(
            "anki_ai.generation_service.importlib.import_module",
            return_value=fake_sdk,
        ):
            metadata = asyncio.run(
                _run_claude_generation_async(
                    "Prompt",
                    Path("/tmp/fake-workspace"),
                    log_sink=logs.append,
                )
            )

        self.assertEqual(metadata["sessionId"], "session-1")
        self.assertEqual(log_messages(logs), ["[ERROR] Claude error line"])
        self.assertEqual(logs[0]["source"], "claude")
        self.assertEqual(logs[0]["level"], "error")

    def test_run_claude_generation_streams_llm_messages_to_log_sink(self) -> None:
        class FakeClaudeAgentOptions:
            def __init__(self, **kwargs: object) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)

        class TextBlock:
            def __init__(self, text: str) -> None:
                self.text = text

        class ThinkingBlock:
            def __init__(self, thinking: str) -> None:
                self.thinking = thinking
                self.signature = "thinking-signature"

        class ToolUseBlock:
            def __init__(self) -> None:
                self.id = "tool-1"
                self.name = "Write"
                self.input = {"file_path": "cards.json"}

        class UserMessage:
            def __init__(self) -> None:
                self.content = "Material summary"

        class AssistantMessage:
            def __init__(self) -> None:
                self.content = [
                    TextBlock("I will write cards."),
                    ThinkingBlock("I should create concise cards."),
                    ToolUseBlock(),
                ]
                self.error = None

        class ResultMessage:
            def __init__(self) -> None:
                self.is_error = False
                self.errors = []
                self.result = ""
                self.session_id = "session-1"
                self.stop_reason = "end_turn"

        captured_options: object | None = None

        async def fake_query(*, prompt: str, options: object) -> object:
            nonlocal captured_options
            _ = prompt
            captured_options = options
            yield UserMessage()
            yield AssistantMessage()
            yield ResultMessage()

        fake_sdk = SimpleNamespace(
            ClaudeAgentOptions=FakeClaudeAgentOptions,
            query=fake_query,
        )
        logs: list[GenerationLogEvent] = []

        with patch(
            "anki_ai.generation_service.importlib.import_module",
            return_value=fake_sdk,
        ):
            metadata = asyncio.run(
                _run_claude_generation_async(
                    "Prompt",
                    Path("/tmp/fake-workspace"),
                    log_sink=logs.append,
                )
            )

        self.assertEqual(metadata["sessionId"], "session-1")
        self.assertEqual(
            log_messages(logs),
            [
                "Claude Code -> LLM: Material summary",
                "LLM -> Claude Code: I will write cards.",
                "LLM -> Claude Code thinking: I should create concise cards.",
                'LLM -> Claude Code tool request: Write {"file_path": "cards.json"}',
            ],
        )
        self.assertTrue(all(log["source"] == "llm" for log in logs))
        self.assertEqual(
            logs[0]["part"],
            {"type": "text", "text": "Material summary"},
        )
        self.assertEqual(
            logs[2]["part"],
            {
                "type": "reasoning",
                "text": "I should create concise cards.",
                "signature": "thinking-signature",
            },
        )
        self.assertEqual(
            logs[3]["part"],
            {
                "type": "tool-call",
                "toolCallId": "tool-1",
                "toolName": "Write",
                "argsText": '{"file_path": "cards.json"}',
            },
        )
        self.assertEqual(
            getattr(captured_options, "thinking", None),
            {"type": "adaptive", "display": "summarized"},
        )


if __name__ == "__main__":
    unittest.main()
