#!/usr/bin/env python3

from __future__ import annotations

"""Minimal Claude Code SDK smoke test."""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query


PROMPT = "what is your model"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal Claude Code SDK smoke test.",
    )
    parser.add_argument(
        "--cwd",
        default=str(Path.cwd()),
        help="Working directory to pass to Claude Code. Defaults to the current directory.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


async def _run(prompt: str, cwd: Path) -> int:
    stderr_lines: list[str] = []
    assistant_text: list[str] = []
    result_message: Any | None = None

    options = ClaudeAgentOptions(
        cwd=cwd,
        permission_mode="dontAsk",
        max_turns=2,
        stderr=stderr_lines.append,
        extra_args={"debug-to-stderr": None},
    )

    try:
        async for message in query(prompt=prompt, options=options):
            if type(message).__name__ == "AssistantMessage":
                assistant_text.extend(_extract_text_blocks(message))
            elif type(message).__name__ == "ResultMessage":
                result_message = message
    except Exception as error:
        sys.stderr.write(f"Claude Code call failed: {error}\n")
        _write_stderr_lines(stderr_lines)
        return 1

    if result_message is not None and getattr(result_message, "is_error", False):
        sys.stderr.write("Claude Code returned an error result.\n")
        result_errors = getattr(result_message, "errors", None)
        if result_errors:
            sys.stderr.write(f"Errors: {result_errors}\n")
        result_payload = getattr(result_message, "result", None)
        if result_payload:
            sys.stderr.write(f"Result: {result_payload}\n")
        _write_stderr_lines(stderr_lines)
        return 1

    text_output = "\n".join(part.strip() for part in assistant_text if part.strip())
    if text_output:
        sys.stdout.write(text_output)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("Claude Code call succeeded, but no assistant text was returned.\n")

    return 0


def _extract_text_blocks(message: Any) -> list[str]:
    parts: list[str] = []
    for block in getattr(message, "content", []):
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return parts


def _write_stderr_lines(stderr_lines: Sequence[str]) -> None:
    if not stderr_lines:
        return
    sys.stderr.write("Claude stderr:\n")
    for line in stderr_lines[-40:]:
        sys.stderr.write(f"{line}\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cwd = Path(args.cwd).expanduser()
    return asyncio.run(_run(PROMPT, cwd))


if __name__ == "__main__":
    raise SystemExit(main())
