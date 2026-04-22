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

from anki_ai import generation_service as generation_module
from anki_ai.generation_service import (
    RATE_LIMIT_ERROR_CODE,
    ClaudeCardGenerationService,
    GenerationServiceError,
    _generation_environment,
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
                self.assertIn("Target card count: 3", prompt)
                self.assertIn("Every card must test one clear knowledge point.", prompt)
                self.assertIn("Each \"Front\" must be context-free", prompt)
                self.assertIn("normally 3-18 words", prompt)
                self.assertIn("Never refer to item numbers", prompt)
                self.assertIn("Delete or rewrite any card that fails the audit.", prompt)
                self.assertIn('Each flashcard must be a JSON object with exactly these fields:', prompt)
                self.assertIn('- "Front": string', prompt)
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

    def test_generate_cards_accepts_materials_without_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"

            def runner(prompt: str, workspace: Path) -> dict[str, str]:
                self.assertIn("- notes.md", prompt)
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
            )

        self.assertEqual(
            result["cards"],
            [{"id": "generated-1", "front": "Question", "back": "Answer"}],
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
            [{"id": "generated-1", "front": "Question", "back": "Answer"}],
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


if __name__ == "__main__":
    unittest.main()
