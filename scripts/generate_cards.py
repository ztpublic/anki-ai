#!/usr/bin/env python3

from __future__ import annotations

"""Debug Claude Code card generation by printing the full message trace."""

import argparse
import asyncio
import base64
import json
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query

from anki_ai.generation_service import ClaudeCardGenerationService


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Claude Code card-generation prompt in a temp workspace and "
            "print the full SDK message trace."
        )
    )
    parser.add_argument(
        "material_path",
        help="Path to a local file to copy into the Claude materials workspace.",
    )
    parser.add_argument(
        "--card-count",
        type=int,
        default=ClaudeCardGenerationService.DEFAULT_CARD_COUNT,
        help=(
            "Approximate number of cards to request from Claude Code. "
            f"Defaults to {ClaudeCardGenerationService.DEFAULT_CARD_COUNT}."
        ),
    )
    return parser.parse_args(list(argv) if argv is not None else None)


async def _run(args: argparse.Namespace) -> int:
    material_path = Path(args.material_path).expanduser()
    if not material_path.is_file():
        print(f"Material file not found: {material_path}")
        return 2

    workspace_path = Path(tempfile.mkdtemp(prefix="anki-ai-generation-debug-"))
    materials_dir = workspace_path / "materials"
    materials_dir.mkdir(parents=True, exist_ok=True)

    material_name = _sanitize_filename(material_path.name)
    workspace_material = materials_dir / material_name
    shutil.copy2(material_path, workspace_material)

    prompt = ClaudeCardGenerationService()._build_prompt(
        material_names=[material_name],
        card_count=max(1, min(args.card_count, ClaudeCardGenerationService.MAX_CARD_COUNT)),
    )

    stderr_lines: list[str] = []
    options = ClaudeAgentOptions(
        cwd=workspace_path,
        permission_mode="bypassPermissions",
        max_turns=200,
        stderr=stderr_lines.append,
        extra_args={"debug-to-stderr": None},
    )

    print(f"Workspace: {workspace_path}")
    print(f"Material: {workspace_material.relative_to(workspace_path)}")
    print("\n=== Prompt Sent To Claude Code ===")
    print(prompt)
    print("=== End Prompt ===\n")
    print("=== Message Trace ===")

    try:
        async for message in query(prompt=prompt, options=options):
            _print_message(message)
    except Exception as error:
        print(f"\n=== Exception ===\n{type(error).__name__}: {error}")
        _print_stderr(stderr_lines)
        _print_workspace_summary(workspace_path)
        return 1

    print("=== End Message Trace ===")
    _print_cards_json(workspace_path)
    _print_stderr(stderr_lines)
    _print_workspace_summary(workspace_path)
    return 0


def _print_message(message: Any) -> None:
    message_type = type(message).__name__
    print(f"\n[{message_type}]")

    if message_type == "SystemMessage":
        print(f"subtype: {getattr(message, 'subtype', None)}")
        return

    if message_type == "ResultMessage":
        print(f"is_error: {getattr(message, 'is_error', None)}")
        print(f"stop_reason: {getattr(message, 'stop_reason', None)}")
        errors = getattr(message, "errors", None)
        if errors:
            print("errors:")
            print(_pretty_json(errors))
        result = getattr(message, "result", None)
        if result:
            print("result:")
            print(result)
        return

    print(f"stop_reason: {getattr(message, 'stop_reason', None)}")
    content = getattr(message, "content", None)
    if isinstance(content, list):
        for index, block in enumerate(content, start=1):
            block_type = getattr(block, "type", type(block).__name__)
            print(f"  block {index}: {block_type}")
            text = getattr(block, "text", None)
            if isinstance(text, str):
                print(_indent(text))
                continue

            thinking = getattr(block, "thinking", None)
            if isinstance(thinking, str):
                print(_indent(thinking))
                continue

            name = getattr(block, "name", None)
            tool_input = getattr(block, "input", None)
            if isinstance(name, str):
                print(f"    name: {name}")
            if tool_input is not None:
                print("    input:")
                print(_indent(_pretty_json(tool_input), prefix="      "))
                continue

            tool_result = {
                "tool_use_id": getattr(block, "tool_use_id", None),
                "content": getattr(block, "content", None),
                "is_error": getattr(block, "is_error", None),
            }
            if any(value is not None for value in tool_result.values()):
                print(_indent(_pretty_json(tool_result), prefix="    "))


def _print_cards_json(workspace_path: Path) -> None:
    cards_path = workspace_path / "cards.json"
    if not cards_path.is_file():
        print("\n=== cards.json ===")
        print("cards.json was not created.")
        return

    print(f"\n=== cards.json ({cards_path}) ===")
    print(cards_path.read_text(encoding="utf-8"))


def _print_stderr(stderr_lines: Sequence[str]) -> None:
    if not stderr_lines:
        return

    print("\n=== Claude stderr (tail) ===")
    for line in stderr_lines[-80:]:
        print(line)


def _print_workspace_summary(workspace_path: Path) -> None:
    print("\n=== Workspace Files ===")
    for path in sorted(workspace_path.rglob("*")):
        print(path.relative_to(workspace_path))


def _sanitize_filename(name: str) -> str:
    material = {
        "name": name,
        "contentBase64": base64.b64encode(b"placeholder").decode("ascii"),
    }
    return ClaudeCardGenerationService()._material_filename(
        material,
        index=0,
        used_names=set(),
    )


def _pretty_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)


def _indent(value: str, *, prefix: str = "    ") -> str:
    return "\n".join(f"{prefix}{line}" for line in value.splitlines())


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_run(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
