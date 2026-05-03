"""Claude Code-backed flashcard generation service."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from .card_generation_workflows import (
    CardGenerationWorkflowError,
    GeneratedCard,
    get_generation_workflow,
)
from .card_regeneration_workflows import (
    CARD_REGENERATION_INPUT_FILENAME,
    REGENERATE_ANSWER_WORKFLOW_ID,
    CardRegenerationWorkflowError,
    RegeneratedCardFields,
    get_regeneration_workflow,
)
from .card_types import (
    CardTypeError,
    DEFAULT_CARD_TYPE_ID,
    normalize_card_type_id,
)
from .file_conversion_service import (
    FileConversionInput,
    FileConversionResult,
    FileConversionServiceError,
    MarkItDownFileConversionService,
)


class MaterialInput(TypedDict):
    name: str
    contentBase64: str


class GenerationRunInfo(TypedDict, total=False):
    workspacePath: str
    sessionId: str
    stopReason: str


class GenerationResult(TypedDict):
    cards: list[GeneratedCard]
    run: GenerationRunInfo


class CardRegenerationResult(TypedDict):
    fields: RegeneratedCardFields
    run: GenerationRunInfo


class ClaudeRunMetadata(TypedDict, total=False):
    sessionId: str
    stopReason: str


GenerationLogLevel = Literal["debug", "info", "warning", "error"]
GenerationLogSource = Literal["app", "claude", "llm"]


class GenerationLogEvent(TypedDict, total=False):
    level: GenerationLogLevel
    source: GenerationLogSource
    role: str
    message: str
    part: dict[str, Any]


class MaterialConverter(Protocol):
    def convert_file(
        self,
        *,
        file: FileConversionInput,
    ) -> FileConversionResult:
        ...


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
GenerationLogSink = Callable[[GenerationLogEvent], None]
WorkspaceFactory = Callable[[], Path]
RATE_LIMIT_ERROR_CODE = "claude_generation_rate_limited"
LOG_LEVEL_RANKS = {
    "trace": 0,
    "debug": 10,
    "info": 20,
    "notice": 25,
    "warn": 30,
    "warning": 30,
    "error": 40,
    "fatal": 50,
    "critical": 50,
}
MAX_GENERATION_LOG_MESSAGE_LENGTH = 4000
MARKDOWN_MATERIAL_EXTENSIONS = frozenset({".md", ".markdown"})
TEXT_FALLBACK_MATERIAL_EXTENSIONS = frozenset(
    {
        ".atom",
        ".csv",
        ".htm",
        ".html",
        ".ipynb",
        ".json",
        ".jsonl",
        ".rss",
        ".text",
        ".txt",
    }
)
ADDON_DIR = Path(__file__).resolve().parent
ADDON_VENDOR_DIR = ADDON_DIR / "vendor"
PROJECT_ROOT = ADDON_DIR.parent
ADDON_CONFIG_PATH = ADDON_DIR / "config.json"
ADDON_LOCAL_CONFIG_PATH = ADDON_DIR / "config.local.json"
GENERATION_ENV_CONFIG_KEYS = {
    "anthropicApiKey": "ANTHROPIC_API_KEY",
    "anthropicAuthToken": "ANTHROPIC_AUTH_TOKEN",
    "anthropicBaseUrl": "ANTHROPIC_BASE_URL",
    "anthropicModel": "ANTHROPIC_MODEL",
    "claudeCodeOAuthToken": "CLAUDE_CODE_OAUTH_TOKEN",
    "claudeConfigDir": "CLAUDE_CONFIG_DIR",
    "claudeCodeUseBedrock": "CLAUDE_CODE_USE_BEDROCK",
    "awsProfile": "AWS_PROFILE",
    "awsRegion": "AWS_REGION",
    "awsDefaultRegion": "AWS_DEFAULT_REGION",
    "httpProxy": "HTTP_PROXY",
    "httpsProxy": "HTTPS_PROXY",
    "noProxy": "NO_PROXY",
}
GENERATION_ENV_KEYS = tuple(GENERATION_ENV_CONFIG_KEYS.values())


def _default_workspace_factory() -> Path:
    return Path(tempfile.mkdtemp(prefix="anki-ai-generation-"))


class ClaudeCardGenerationService:
    """Prepare generation materials and collect Claude Code output."""

    DEFAULT_CARD_COUNT = 5
    MAX_CARD_COUNT = 200

    def __init__(
        self,
        *,
        runner: ClaudeRunner | None = None,
        workspace_factory: WorkspaceFactory = _default_workspace_factory,
        material_converter: MaterialConverter | None = None,
    ) -> None:
        self._runner = runner
        self._workspace_factory = workspace_factory
        self._material_converter = (
            MarkItDownFileConversionService()
            if material_converter is None
            else material_converter
        )

    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: Sequence[MaterialInput] = (),
        card_count: int = DEFAULT_CARD_COUNT,
        card_type: str = DEFAULT_CARD_TYPE_ID,
        instructions: str | None = None,
        log_sink: GenerationLogSink | None = None,
    ) -> GenerationResult:
        has_source_text = source_text is not None and bool(source_text.strip())
        if not has_source_text and not materials:
            raise GenerationServiceError(
                "missing_generation_input",
                "Provide source text or at least one material file to generate cards.",
            )

        try:
            card_type_id = normalize_card_type_id(card_type)
            get_generation_workflow(card_type_id)
        except CardTypeError as error:
            raise GenerationServiceError(
                "invalid_card_type",
                str(error),
                {"cardType": card_type},
            ) from error

        normalized_card_count = max(1, min(card_count, self.MAX_CARD_COUNT))
        workspace_path = self._workspace_factory()
        workspace_path.mkdir(parents=True, exist_ok=True)
        materials_dir = workspace_path / "materials"
        materials_dir.mkdir(exist_ok=True)

        material_names: list[str] = []
        used_names: set[str] = set()
        if has_source_text and source_text is not None:
            source_path = materials_dir / self._unique_material_name(
                "user_input.txt",
                used_names=used_names,
            )
            source_path.write_text(source_text, encoding="utf-8")
            material_names.append(source_path.name)

        for index, material in enumerate(materials):
            filename = self._sanitize_material_filename(material, index=index)
            try:
                content = base64.b64decode(material["contentBase64"], validate=True)
            except (ValueError, TypeError) as error:
                raise GenerationServiceError(
                    "invalid_material_payload",
                    f"Material {index + 1} did not contain valid base64 content.",
                    {"materialName": material.get("name", "")},
                ) from error

            if self._is_markdown_material(filename):
                material_path = materials_dir / self._unique_material_name(
                    filename,
                    used_names=used_names,
                )
                material_path.write_bytes(content)
                material_names.append(material_path.name)
                continue

            self._log(
                log_sink,
                f"Converting {filename} to markdown for card generation.",
            )

            try:
                converted = self._material_converter.convert_file(file=material)
            except FileConversionServiceError as error:
                self._log(
                    log_sink,
                    f"Failed to convert {filename} to markdown: {error.message}",
                )
                fallback_name = self._write_raw_text_material_if_supported(
                    filename=filename,
                    content=content,
                    materials_dir=materials_dir,
                    used_names=used_names,
                )
                if fallback_name is not None:
                    material_names.append(fallback_name)
                    self._log(
                        log_sink,
                        (
                            f"Using raw text from {filename} as {fallback_name} "
                            "for card generation."
                        ),
                    )
                    continue

                raise GenerationServiceError(
                    "material_conversion_failed",
                    f"Could not convert {filename} to markdown for card generation.",
                    self._merge_details(
                        error.details,
                        {
                            "materialName": filename,
                            "conversionCode": error.code,
                            "conversionMessage": error.message,
                            "workspacePath": str(workspace_path),
                        },
                    ),
                ) from error

            markdown = converted["document"]["markdown"]
            converted_name = self._unique_material_name(
                self._converted_markdown_filename(filename),
                used_names=used_names,
            )
            material_path = materials_dir / converted_name
            material_path.write_text(markdown, encoding="utf-8")
            material_names.append(material_path.name)
            self._log(
                log_sink,
                (
                    f"Converted {filename} to {converted_name} "
                    f"({len(markdown)} characters)."
                ),
            )

        prompt = self._build_prompt(
            material_names=material_names,
            card_count=normalized_card_count,
            card_type_id=card_type_id,
            instructions=instructions,
        )

        run_info: GenerationRunInfo = {"workspacePath": str(workspace_path)}
        try:
            run_metadata = self._run_claude(prompt, workspace_path, log_sink)
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
                    {
                        "workspacePath": str(workspace_path),
                        "errorType": type(error).__name__,
                        "error": str(error),
                        "runtime": _runtime_diagnostics(),
                    },
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
                    {
                        "workspacePath": str(workspace_path),
                        "errorType": type(error).__name__,
                        "error": str(error),
                        "runtime": _runtime_diagnostics(),
                    },
                ) from error
            raise GenerationServiceError(
                "claude_generation_failed",
                "Claude Code generation failed.",
                {
                    "workspacePath": str(workspace_path),
                    "errorType": type(error).__name__,
                    "error": str(error),
                    "runtime": _runtime_diagnostics(),
                },
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
            "cards": self._normalize_cards(parsed_cards, card_type_id),
            "run": run_info,
        }

    def regenerate_answer(
        self,
        *,
        question: str,
        answer: str,
        explanation: str | None = None,
        instructions: str | None = None,
        log_sink: GenerationLogSink | None = None,
    ) -> CardRegenerationResult:
        return self._regenerate_card_fields(
            workflow_id=REGENERATE_ANSWER_WORKFLOW_ID,
            question=question,
            answer=answer,
            explanation=explanation,
            instructions=instructions,
            log_sink=log_sink,
        )

    def _regenerate_card_fields(
        self,
        *,
        workflow_id: str,
        question: str,
        answer: str,
        explanation: str | None,
        instructions: str | None,
        log_sink: GenerationLogSink | None,
    ) -> CardRegenerationResult:
        if not question.strip():
            raise GenerationServiceError(
                "missing_regeneration_input",
                "Provide the card question to regenerate an answer.",
            )
        if not answer.strip():
            raise GenerationServiceError(
                "missing_regeneration_input",
                "Provide the original answer to regenerate an answer.",
            )

        try:
            workflow = get_regeneration_workflow(workflow_id)
        except CardRegenerationWorkflowError as error:
            raise GenerationServiceError(error.code, error.message, error.details) from error

        workspace_path = self._workspace_factory()
        workspace_path.mkdir(parents=True, exist_ok=True)
        input_path = workspace_path / CARD_REGENERATION_INPUT_FILENAME
        input_payload = {
            "Question": question,
            "OriginalAnswer": answer,
            "OriginalExplanation": "" if explanation is None else explanation,
        }
        input_path.write_text(
            json.dumps(input_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        try:
            prompt = workflow.build_prompt(instructions=instructions)
        except CardRegenerationWorkflowError as error:
            raise GenerationServiceError(error.code, error.message, error.details) from error

        run_info: GenerationRunInfo = {"workspacePath": str(workspace_path)}
        try:
            run_metadata = self._run_claude(prompt, workspace_path, log_sink)
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
                    {
                        "workspacePath": str(workspace_path),
                        "errorType": type(error).__name__,
                        "error": str(error),
                        "runtime": _runtime_diagnostics(),
                    },
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
                    {
                        "workspacePath": str(workspace_path),
                        "errorType": type(error).__name__,
                        "error": str(error),
                        "runtime": _runtime_diagnostics(),
                    },
                ) from error
            raise GenerationServiceError(
                "claude_generation_failed",
                "Claude Code generation failed.",
                {
                    "workspacePath": str(workspace_path),
                    "errorType": type(error).__name__,
                    "error": str(error),
                    "runtime": _runtime_diagnostics(),
                },
            ) from error

        if "sessionId" in run_metadata:
            run_info["sessionId"] = run_metadata["sessionId"]
        if "stopReason" in run_metadata:
            run_info["stopReason"] = run_metadata["stopReason"]

        output_path = workspace_path / workflow.output_filename
        if not output_path.is_file():
            raise GenerationServiceError(
                "missing_regenerated_card_output",
                f"Claude Code did not create {workflow.output_filename} in the workspace root.",
                {"workspacePath": str(workspace_path)},
            )

        try:
            raw_output = output_path.read_text(encoding="utf-8")
        except OSError as error:
            raise GenerationServiceError(
                "regenerated_card_output_unreadable",
                f"{workflow.output_filename} could not be read.",
                {"workspacePath": str(workspace_path)},
            ) from error

        try:
            parsed_output = json.loads(raw_output)
        except json.JSONDecodeError as error:
            raise GenerationServiceError(
                "invalid_regenerated_card_output",
                f"{workflow.output_filename} was not valid JSON.",
                {"workspacePath": str(workspace_path)},
            ) from error

        try:
            fields = workflow.normalize_output(parsed_output)
        except CardRegenerationWorkflowError as error:
            raise GenerationServiceError(error.code, error.message, error.details) from error

        return {
            "fields": fields,
            "run": run_info,
        }

    def _build_prompt(
        self,
        *,
        material_names: Sequence[str],
        card_count: int,
        card_type_id: str = DEFAULT_CARD_TYPE_ID,
        instructions: str | None = None,
    ) -> str:
        try:
            return get_generation_workflow(card_type_id).build_prompt(
                material_names=material_names,
                card_count=card_count,
                instructions=instructions,
            )
        except CardGenerationWorkflowError as error:
            raise GenerationServiceError(error.code, error.message, error.details) from error

    def _normalize_cards(
        self,
        value: Any,
        card_type_id: str = DEFAULT_CARD_TYPE_ID,
    ) -> list[GeneratedCard]:
        try:
            return get_generation_workflow(card_type_id).normalize_cards(value)
        except CardGenerationWorkflowError as error:
            raise GenerationServiceError(error.code, error.message, error.details) from error

    def _sanitize_material_filename(
        self,
        material: MaterialInput,
        *,
        index: int,
    ) -> str:
        raw_name = material.get("name", "").strip()
        filename = Path(raw_name).name
        if not filename:
            filename = f"material-{index + 1}.bin"

        sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        sanitized = sanitized.lstrip(".")
        if not sanitized:
            sanitized = f"material-{index + 1}.bin"

        return sanitized

    def _material_filename(
        self,
        material: MaterialInput,
        *,
        index: int,
        used_names: set[str],
    ) -> str:
        sanitized = self._sanitize_material_filename(material, index=index)
        return self._unique_material_name(sanitized, used_names=used_names)

    @staticmethod
    def _is_markdown_material(filename: str) -> bool:
        return Path(filename).suffix.lower() in MARKDOWN_MATERIAL_EXTENSIONS

    @staticmethod
    def _converted_markdown_filename(filename: str) -> str:
        stem = Path(filename).stem
        if not stem:
            stem = "material"
        return f"{stem}.md"

    @classmethod
    def _write_raw_text_material_if_supported(
        cls,
        *,
        filename: str,
        content: bytes,
        materials_dir: Path,
        used_names: set[str],
    ) -> str | None:
        if Path(filename).suffix.lower() not in TEXT_FALLBACK_MATERIAL_EXTENSIONS:
            return None

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None

        if "\x00" in text or not text.strip():
            return None

        fallback_name = cls._unique_material_name(filename, used_names=used_names)
        (materials_dir / fallback_name).write_text(text, encoding="utf-8")
        return fallback_name

    @staticmethod
    def _log(log_sink: GenerationLogSink | None, message: str) -> None:
        _emit_generation_log(log_sink, message, source="app")

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

    def _run_claude(
        self,
        prompt: str,
        workspace_path: Path,
        log_sink: GenerationLogSink | None,
    ) -> ClaudeRunMetadata:
        if self._runner is not None:
            return self._runner(prompt, workspace_path)

        return _run_claude_generation(
            prompt,
            workspace_path,
            log_sink=log_sink,
        )


def _run_claude_generation(
    prompt: str,
    workspace_path: Path,
    *,
    log_sink: GenerationLogSink | None = None,
) -> ClaudeRunMetadata:
    return asyncio.run(
        _run_claude_generation_async(
            prompt,
            workspace_path,
            log_sink=log_sink,
        )
    )


async def _run_claude_generation_async(
    prompt: str,
    workspace_path: Path,
    *,
    log_sink: GenerationLogSink | None = None,
) -> ClaudeRunMetadata:
    _bootstrap_generation_runtime()
    sdk = importlib.import_module("claude_agent_sdk")

    stderr_lines: list[str] = []
    result_message: Any | None = None

    def handle_stderr(line: str) -> None:
        stderr_lines.append(line)
        if _stderr_log_rank(line) >= LOG_LEVEL_RANKS["error"]:
            _emit_generation_log(
                log_sink,
                line,
                level="error",
                source="claude",
                role="Claude Code",
            )

    options = sdk.ClaudeAgentOptions(
        cwd=workspace_path,
        cli_path=_configured_claude_cli_path(),
        permission_mode="bypassPermissions",
        max_turns=200,
        stderr=handle_stderr,
        env=_generation_environment(),
        extra_args={"debug-to-stderr": None},
        thinking={"type": "adaptive", "display": "summarized"},
    )

    try:
        async for message in sdk.query(prompt=prompt, options=options):
            _emit_claude_message_logs(log_sink, message)
            if type(message).__name__ == "ResultMessage":
                result_message = message
    except Exception as error:
        details = _claude_failure_details(
            error=error,
            stderr_lines=stderr_lines,
        )
        raise _claude_failure_error(
            details=details,
            auth_missing=_looks_auth_missing(error, stderr_lines),
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
            auth_missing=_looks_auth_missing(
                result_message.errors,
                getattr(result_message, "result", None),
                stderr_lines,
            ),
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


def _emit_generation_log(
    log_sink: GenerationLogSink | None,
    message: str,
    *,
    level: GenerationLogLevel = "info",
    source: GenerationLogSource = "app",
    role: str | None = None,
    part: dict[str, Any] | None = None,
) -> None:
    if log_sink is None:
        return

    event: GenerationLogEvent = {
        "level": level,
        "source": source,
        "message": _truncate_generation_log_message(message),
    }
    if role is not None:
        event["role"] = role
    if part is not None:
        event["part"] = part
    log_sink(event)


def _emit_claude_message_logs(
    log_sink: GenerationLogSink | None,
    message: Any,
) -> None:
    if log_sink is None:
        return

    message_type = type(message).__name__
    if message_type == "UserMessage":
        for log_event in _content_log_events(
            getattr(message, "content", None),
            role="Claude Code -> LLM",
        ):
            _emit_generation_log(
                log_sink,
                log_event["message"],
                source="llm",
                role="Claude Code -> LLM",
                part=log_event.get("part"),
            )
        return

    if message_type == "AssistantMessage":
        error = getattr(message, "error", None)
        if error:
            _emit_generation_log(
                log_sink,
                f"LLM -> Claude Code error: {error}",
                level="error",
                source="llm",
                role="LLM -> Claude Code",
            )

        for log_event in _content_log_events(
            getattr(message, "content", None),
            role="LLM -> Claude Code",
        ):
            _emit_generation_log(
                log_sink,
                log_event["message"],
                source="llm",
                role="LLM -> Claude Code",
                part=log_event.get("part"),
            )


def _content_messages(content: Any, *, role: str) -> list[str]:
    return [event["message"] for event in _content_log_events(content, role=role)]


def _content_log_events(content: Any, *, role: str) -> list[GenerationLogEvent]:
    if isinstance(content, str):
        text = content.strip()
        return [
            {
                "message": f"{role}: {text}",
                "part": {"type": "text", "text": text},
            }
        ] if text else []

    if not isinstance(content, list):
        return []

    events: list[GenerationLogEvent] = []
    for block in content:
        block_event = _content_block_log_event(block, role=role)
        if block_event is not None:
            events.append(block_event)
    return events


def _content_block_message(block: Any, *, role: str) -> str | None:
    event = _content_block_log_event(block, role=role)
    return event["message"] if event is not None else None


def _content_block_log_event(
    block: Any,
    *,
    role: str,
) -> GenerationLogEvent | None:
    block_type = type(block).__name__

    text = getattr(block, "text", None)
    if isinstance(text, str) and text.strip():
        normalized_text = text.strip()
        return {
            "message": f"{role}: {normalized_text}",
            "part": {"type": "text", "text": normalized_text},
        }

    if block_type == "ThinkingBlock":
        thinking = getattr(block, "thinking", None)
        if isinstance(thinking, str) and thinking.strip():
            normalized_thinking = thinking.strip()
            part: dict[str, Any] = {
                "type": "reasoning",
                "text": normalized_thinking,
            }
            signature = getattr(block, "signature", None)
            if isinstance(signature, str) and signature:
                part["signature"] = signature
            return {
                "message": f"{role} thinking: {normalized_thinking}",
                "part": part,
            }
        return None

    tool_name = getattr(block, "name", None)
    tool_input = getattr(block, "input", None)
    if isinstance(tool_name, str):
        suffix = f" {_compact_json(tool_input)}" if tool_input is not None else ""
        tool_id = getattr(block, "id", None)
        part = {
            "type": "tool-call",
            "toolName": tool_name,
            "argsText": _compact_json(tool_input) if tool_input is not None else "",
        }
        if isinstance(tool_id, str) and tool_id:
            part["toolCallId"] = tool_id
        if block_type == "ServerToolUseBlock":
            part["serverSide"] = True
        return {
            "message": f"{role} tool request: {tool_name}{suffix}",
            "part": part,
        }

    tool_use_id = getattr(block, "tool_use_id", None)
    tool_content = getattr(block, "content", None)
    is_error = getattr(block, "is_error", None)
    if tool_use_id is not None or tool_content is not None or is_error is not None:
        state = " error" if is_error else ""
        identifier = f" {tool_use_id}" if tool_use_id else ""
        summary = _compact_json(tool_content) if tool_content is not None else ""
        return {
            "message": f"{role} tool result{state}{identifier}: {summary}".rstrip(),
            "part": {
                "type": "data",
                "name": (
                    "server-tool-result"
                    if block_type == "ServerToolResultBlock"
                    else "tool-result"
                ),
                "data": {
                    "toolUseId": tool_use_id,
                    "content": tool_content,
                    "isError": is_error,
                },
            },
        }

    return None


def _compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _truncate_generation_log_message(message: str) -> str:
    if len(message) <= MAX_GENERATION_LOG_MESSAGE_LENGTH:
        return message
    return f"{message[:MAX_GENERATION_LOG_MESSAGE_LENGTH]}..."


def _stderr_log_rank(line: str) -> int:
    level = _stderr_log_level(line)
    if level is None:
        return LOG_LEVEL_RANKS["info"]
    return LOG_LEVEL_RANKS.get(level, LOG_LEVEL_RANKS["info"])


def _stderr_log_level(line: str) -> str | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        value = None

    if isinstance(value, dict):
        for key in ("level", "levelname", "severity", "logLevel", "lvl"):
            normalized = _normalize_log_level(value.get(key))
            if normalized is not None:
                return normalized

    for pattern in (
        r"\b(?:level|severity|lvl|log_level)\s*[:=]\s*\"?([A-Za-z]+)\"?",
        r"^\s*(?:\[[^\]]+\]\s*)?\[?(trace|debug|info|notice|warn|warning|error|fatal|critical)\]?\b",
    ):
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match is not None:
            return _normalize_log_level(match.group(1))

    if re.search(r"\b(error|fatal|critical|exception|traceback)\b", line, flags=re.IGNORECASE):
        return "error"

    return None


def _normalize_log_level(value: Any) -> str | None:
    if isinstance(value, int):
        if value >= LOG_LEVEL_RANKS["error"]:
            return "error"
        if value >= LOG_LEVEL_RANKS["warning"]:
            return "warning"
        if value >= LOG_LEVEL_RANKS["info"]:
            return "info"
        if value >= LOG_LEVEL_RANKS["debug"]:
            return "debug"
        return "trace"

    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    if normalized == "warn":
        normalized = "warning"
    if normalized == "critical":
        normalized = "fatal"
    return normalized if normalized in LOG_LEVEL_RANKS else None


def _claude_failure_details(
    *,
    stderr_lines: Sequence[str],
    error: Exception | None = None,
    errors: Any | None = None,
    result: Any | None = None,
) -> dict[str, Any] | None:
    details: dict[str, Any] = {}
    if error is not None:
        details["errorType"] = type(error).__name__
        details["error"] = str(error)
    if errors:
        details["errors"] = errors
    if result not in (None, ""):
        details["result"] = result
    if stderr_lines:
        details["stderr"] = list(stderr_lines[-40:])
    details["runtime"] = _runtime_diagnostics()
    return details or None


def _runtime_diagnostics() -> dict[str, Any]:
    path_value = os.environ.get("PATH", "")
    env_keys_to_report = (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_USE_BEDROCK",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    )
    return {
        "pythonExecutable": sys.executable,
        "processCwd": os.getcwd(),
        "claudePath": shutil.which("claude"),
        "configuredClaudePath": str(_configured_claude_cli_path() or ""),
        "nodePath": shutil.which("node"),
        "pathEntries": [entry for entry in path_value.split(os.pathsep) if entry],
        "envKeysPresent": [
            key for key in env_keys_to_report if os.environ.get(key)
        ],
        "configuredEnvKeysPresent": sorted(_generation_environment().keys()),
    }


def _bootstrap_generation_runtime() -> None:
    """Make bundled/local generation dependencies visible inside Anki."""
    _prepend_sys_path(_dependency_path_candidates())
    _prepend_process_path(_cli_path_candidates())


def _dependency_path_candidates() -> list[Path]:
    candidates: list[Path] = []

    if ADDON_VENDOR_DIR.is_dir():
        candidates.append(ADDON_VENDOR_DIR)

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

    return candidates


def _cli_path_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / ".local" / "bin",
        home / ".claude" / "local",
        home / ".npm-global" / "bin",
        home / ".yarn" / "bin",
        home / ".cargo" / "bin",
        Path("/opt/homebrew/opt/node@20/bin"),
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]


def _prepend_sys_path(paths: Sequence[Path]) -> None:
    for path in reversed([candidate for candidate in paths if candidate.is_dir()]):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


def _prepend_process_path(paths: Sequence[Path]) -> None:
    current_entries = [
        entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry
    ]
    current_entry_set = set(current_entries)
    next_entries = [
        str(path)
        for path in paths
        if path.is_dir() and str(path) not in current_entry_set
    ]
    if not next_entries:
        return

    os.environ["PATH"] = os.pathsep.join([*next_entries, *current_entries])


def _generation_environment() -> dict[str, str]:
    env: dict[str, str] = {}

    for key in GENERATION_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value

    shell_env = _load_shell_generation_environment()
    for key, value in shell_env.items():
        if key not in env and value:
            env[key] = value

    config = _generation_config()
    for config_key, env_key in GENERATION_ENV_CONFIG_KEYS.items():
        value = config.get(config_key)
        if isinstance(value, str) and value.strip():
            env[env_key] = value.strip()

    return env


def _load_shell_generation_environment() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in _shell_env_file_candidates():
        env.update(_read_shell_generation_environment(path))
    return env


def _shell_env_file_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / ".zshenv",
        home / ".zprofile",
        home / ".zshrc",
        home / ".profile",
        home / ".bash_profile",
        home / ".bashrc",
    ]


def _read_shell_generation_environment(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    env: dict[str, str] = {}
    allowed_keys = set(GENERATION_ENV_KEYS)
    for line in lines:
        parsed = _parse_shell_env_assignment(line)
        if parsed is None:
            continue

        key, value = parsed
        if key in allowed_keys and value:
            env[key] = value

    return env


def _parse_shell_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()

    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return None

    value = _strip_shell_comment(raw_value.strip())
    return key, _unquote_shell_value(value.strip())


def _strip_shell_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "#":
            return value[:index].rstrip()
    return value


def _unquote_shell_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value.replace(r"\'", "'").replace(r'\"', '"')


def _configured_claude_cli_path() -> str | None:
    configured = _generation_config().get("claudeCliPath")
    if isinstance(configured, str) and configured.strip():
        return str(Path(configured).expanduser())

    discovered = shutil.which("claude")
    return discovered if discovered else None


def _generation_config() -> dict[str, Any]:
    raw_config = _load_generation_config()
    generation_config = raw_config.get("generation")
    if isinstance(generation_config, dict):
        merged = dict(raw_config)
        merged.update(generation_config)
        return merged
    return raw_config


def _load_generation_config() -> dict[str, Any]:
    override_path = os.environ.get("ANKI_AI_CONFIG_PATH")
    if override_path:
        return _read_config_file(Path(override_path))

    config = _read_config_file(ADDON_CONFIG_PATH)
    local_config = _read_config_file(ADDON_LOCAL_CONFIG_PATH)
    if local_config:
        config = _merge_config(config, local_config)
    return config


def _read_config_file(config_path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _claude_failure_error(
    *,
    details: dict[str, Any] | None,
    auth_missing: bool = False,
    rate_limited: bool,
    default_message: str,
) -> GenerationServiceError:
    if auth_missing:
        return GenerationServiceError(
            "claude_auth_missing",
            (
                "Claude Code authentication is not configured for Anki. "
                "Set generation.anthropicAuthToken or generation.anthropicApiKey "
                "in the add-on config, define ANTHROPIC_AUTH_TOKEN or "
                "ANTHROPIC_API_KEY as a simple export in your shell startup file, "
                "or launch Anki from an environment that provides one of those "
                "variables."
            ),
            details,
        )
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


def _looks_auth_missing(*values: Any) -> bool:
    for value in values:
        if value is None:
            continue
        lowered = _serialize_detail_value(value).lower()
        if (
            "could not resolve authentication method" in lowered
            or "auth error: no api key available" in lowered
            or "expected either apikey or authtoken" in lowered
            or "no api key available" in lowered
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
