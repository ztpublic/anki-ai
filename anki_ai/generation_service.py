"""Claude Code-backed flashcard generation service."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import re
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypedDict


class MaterialInput(TypedDict):
    name: str
    contentBase64: str


class GeneratedCard(TypedDict):
    id: str
    front: str
    back: str


class GenerationRunInfo(TypedDict, total=False):
    workspacePath: str
    sessionId: str
    stopReason: str


class GenerationResult(TypedDict):
    cards: list[GeneratedCard]
    run: GenerationRunInfo


class ClaudeRunMetadata(TypedDict, total=False):
    sessionId: str
    stopReason: str


class GenerationServiceError(Exception):
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


ClaudeRunner = Callable[[str, Path], ClaudeRunMetadata]
WorkspaceFactory = Callable[[], Path]
RATE_LIMIT_ERROR_CODE = "claude_generation_rate_limited"


def _default_workspace_factory() -> Path:
    return Path(tempfile.mkdtemp(prefix="anki-ai-generation-"))


class ClaudeCardGenerationService:
    """Prepare generation materials and collect Claude Code output."""

    DEFAULT_CARD_COUNT = 5
    MAX_CARD_COUNT = 50

    def __init__(
        self,
        *,
        runner: ClaudeRunner | None = None,
        workspace_factory: WorkspaceFactory = _default_workspace_factory,
    ) -> None:
        self._runner = _run_claude_generation if runner is None else runner
        self._workspace_factory = workspace_factory

    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: Sequence[MaterialInput] = (),
        card_count: int = DEFAULT_CARD_COUNT,
    ) -> GenerationResult:
        has_source_text = source_text is not None and bool(source_text.strip())
        if not has_source_text and not materials:
            raise GenerationServiceError(
                "missing_generation_input",
                "Provide source text or at least one material file to generate cards.",
            )

        normalized_card_count = max(1, min(card_count, self.MAX_CARD_COUNT))
        workspace_path = self._workspace_factory()
        workspace_path.mkdir(parents=True, exist_ok=True)
        materials_dir = workspace_path / "materials"
        materials_dir.mkdir(exist_ok=True)

        material_names: list[str] = []
        used_names: set[str] = set()
        if has_source_text and source_text is not None:
            source_path = materials_dir / self._unique_material_name(
                "source.txt",
                used_names=used_names,
            )
            source_path.write_text(source_text, encoding="utf-8")
            material_names.append(source_path.name)

        for index, material in enumerate(materials):
            material_path = materials_dir / self._material_filename(
                material,
                index=index,
                used_names=used_names,
            )
            try:
                content = base64.b64decode(material["contentBase64"], validate=True)
            except (ValueError, TypeError) as error:
                raise GenerationServiceError(
                    "invalid_material_payload",
                    f"Material {index + 1} did not contain valid base64 content.",
                    {"materialName": material.get("name", "")},
                ) from error

            material_path.write_bytes(content)
            material_names.append(material_path.name)

        prompt = self._build_prompt(
            material_names=material_names,
            card_count=normalized_card_count,
        )

        run_info: GenerationRunInfo = {"workspacePath": str(workspace_path)}
        try:
            run_metadata = self._runner(prompt, workspace_path)
        except GenerationServiceError as error:
            error.details = self._merge_details(
                error.details,
                {"workspacePath": str(workspace_path)},
            )
            raise
        except Exception as error:
            if self._matches_error_name(error, "CLINotFoundError"):
                raise GenerationServiceError(
                    "claude_cli_not_found",
                    "Claude Code CLI is not available in the current environment.",
                    {"workspacePath": str(workspace_path)},
                ) from error
            if self._matches_error_name(
                error,
                "CLIConnectionError",
                "ProcessError",
                "ClaudeSDKError",
            ):
                raise GenerationServiceError(
                    "claude_generation_failed",
                    "Claude Code generation failed.",
                    {"workspacePath": str(workspace_path), "error": str(error)},
                ) from error
            raise GenerationServiceError(
                "claude_generation_failed",
                "Claude Code generation failed.",
                {"workspacePath": str(workspace_path), "error": str(error)},
            ) from error

        if "sessionId" in run_metadata:
            run_info["sessionId"] = run_metadata["sessionId"]
        if "stopReason" in run_metadata:
            run_info["stopReason"] = run_metadata["stopReason"]

        cards_path = workspace_path / "cards.json"
        if not cards_path.is_file():
            raise GenerationServiceError(
                "missing_cards_output",
                "Claude Code did not create cards.json in the workspace root.",
                {"workspacePath": str(workspace_path)},
            )

        try:
            raw_cards = cards_path.read_text(encoding="utf-8")
        except OSError as error:
            raise GenerationServiceError(
                "cards_output_unreadable",
                "cards.json could not be read.",
                {"workspacePath": str(workspace_path)},
            ) from error

        try:
            parsed_cards = json.loads(raw_cards)
        except json.JSONDecodeError as error:
            raise GenerationServiceError(
                "invalid_cards_output",
                "cards.json was not valid JSON.",
                {"workspacePath": str(workspace_path)},
            ) from error

        return {
            "cards": self._normalize_cards(parsed_cards),
            "run": run_info,
        }

    def _build_prompt(
        self,
        *,
        material_names: Sequence[str],
        card_count: int,
    ) -> str:
        files_list = "\n".join(f"- {name}" for name in material_names)
        return (
            "Study the materials available in the ./materials directory and create "
            f"approximately {card_count} useful Anki flashcards.\n\n"
            "Requirements:\n"
            "- Read only the materials in ./materials.\n"
            "- Write exactly one output file named cards.json in the current working directory.\n"
            '- cards.json must contain a JSON array of objects.\n'
            '- Every object must have string fields named "Front" and "Back".\n'
            "- Make each card concise, accurate, and useful for studying.\n"
            "- Do not wrap the JSON in markdown fences.\n"
            "- Do not create any other output files.\n\n"
            "Prepared material files:\n"
            f"{files_list}\n"
        )

    def _normalize_cards(self, value: Any) -> list[GeneratedCard]:
        if not isinstance(value, list) or not value:
            raise GenerationServiceError(
                "invalid_cards_output",
                "cards.json must contain a non-empty JSON array.",
            )

        cards: list[GeneratedCard] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise GenerationServiceError(
                    "invalid_cards_output",
                    "Each cards.json entry must be an object.",
                    {"cardIndex": index},
                )

            front = item.get("Front")
            back = item.get("Back")
            if not isinstance(front, str) or not front.strip():
                raise GenerationServiceError(
                    "invalid_cards_output",
                    'Each card must have a non-empty string field "Front".',
                    {"cardIndex": index},
                )
            if not isinstance(back, str) or not back.strip():
                raise GenerationServiceError(
                    "invalid_cards_output",
                    'Each card must have a non-empty string field "Back".',
                    {"cardIndex": index},
                )

            cards.append(
                {
                    "id": f"generated-{index + 1}",
                    "front": front,
                    "back": back,
                }
            )

        return cards

    def _material_filename(
        self,
        material: MaterialInput,
        *,
        index: int,
        used_names: set[str],
    ) -> str:
        raw_name = material.get("name", "").strip()
        filename = Path(raw_name).name
        if not filename:
            filename = f"material-{index + 1}.bin"

        sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        sanitized = sanitized.lstrip(".")
        if not sanitized:
            sanitized = f"material-{index + 1}.bin"

        return self._unique_material_name(sanitized, used_names=used_names)

    @staticmethod
    def _unique_material_name(name: str, *, used_names: set[str]) -> str:
        candidate = name
        stem = Path(name).stem
        suffix = Path(name).suffix
        counter = 2
        while candidate in used_names:
            candidate = f"{stem}-{counter}{suffix}"
            counter += 1
        used_names.add(candidate)
        return candidate

    @staticmethod
    def _merge_details(
        existing: Any | None,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        if isinstance(existing, dict):
            merged.update(existing)
        elif existing is not None:
            merged["detail"] = existing
        merged.update(extra)
        return merged

    @staticmethod
    def _matches_error_name(error: Exception, *names: str) -> bool:
        return any(base.__name__ in names for base in type(error).__mro__)


def _run_claude_generation(prompt: str, workspace_path: Path) -> ClaudeRunMetadata:
    return asyncio.run(_run_claude_generation_async(prompt, workspace_path))


async def _run_claude_generation_async(
    prompt: str,
    workspace_path: Path,
) -> ClaudeRunMetadata:
    sdk = importlib.import_module("claude_agent_sdk")

    stderr_lines: list[str] = []
    result_message: Any | None = None

    options = sdk.ClaudeAgentOptions(
        cwd=workspace_path,
        permission_mode="bypassPermissions",
        max_turns=12,
        stderr=stderr_lines.append,
        extra_args={"debug-to-stderr": None},
    )

    try:
        async for message in sdk.query(prompt=prompt, options=options):
            if type(message).__name__ == "ResultMessage":
                result_message = message
    except Exception as error:
        details = _claude_failure_details(
            error=error,
            stderr_lines=stderr_lines,
        )
        raise _claude_failure_error(
            details=details,
            rate_limited=_looks_rate_limited(error, stderr_lines),
            default_message="Claude Code generation failed.",
        ) from error

    if result_message is None:
        return {}

    if result_message.is_error:
        details = _claude_failure_details(
            errors=result_message.errors,
            result=getattr(result_message, "result", None),
            stderr_lines=stderr_lines,
        )
        raise _claude_failure_error(
            details=details,
            rate_limited=_looks_rate_limited(
                result_message.errors,
                getattr(result_message, "result", None),
                stderr_lines,
            ),
            default_message="Claude Code reported an error while generating cards.",
        )

    metadata: ClaudeRunMetadata = {}
    if result_message.session_id:
        metadata["sessionId"] = result_message.session_id
    if result_message.stop_reason:
        metadata["stopReason"] = result_message.stop_reason
    return metadata


def _claude_failure_details(
    *,
    stderr_lines: Sequence[str],
    error: Exception | None = None,
    errors: Any | None = None,
    result: Any | None = None,
) -> dict[str, Any] | None:
    details: dict[str, Any] = {}
    if error is not None:
        details["error"] = str(error)
    if errors:
        details["errors"] = errors
    if result not in (None, ""):
        details["result"] = result
    if stderr_lines:
        details["stderr"] = list(stderr_lines[-40:])
    return details or None


def _claude_failure_error(
    *,
    details: dict[str, Any] | None,
    rate_limited: bool,
    default_message: str,
) -> GenerationServiceError:
    if rate_limited:
        return GenerationServiceError(
            RATE_LIMIT_ERROR_CODE,
            "Claude Code generation was rate limited by the configured API provider.",
            details,
        )
    return GenerationServiceError(
        "claude_generation_failed",
        default_message,
        details,
    )


def _looks_rate_limited(*values: Any) -> bool:
    for value in values:
        if value is None:
            continue
        serialized = _serialize_detail_value(value)
        lowered = serialized.lower()
        if (
            "429" in serialized
            or "rate_limit" in lowered
            or "rate limit" in lowered
            or "速率限制" in serialized
        ):
            return True
    return False


def _serialize_detail_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)
