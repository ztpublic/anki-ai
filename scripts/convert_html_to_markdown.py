#!/usr/bin/env python3

from __future__ import annotations

"""Fetch an HTML URL and convert it to markdown."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TextIO

from anki_ai.file_conversion_service import (
    FileConversionResult,
    FileConversionServiceError,
    MarkItDownFileConversionService,
)


class FileConverter(Protocol):
    def convert_url(
        self,
        *,
        url: str,
    ) -> FileConversionResult: ...


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch an HTML URL and convert it to markdown.",
    )
    parser.add_argument(
        "url",
        help='HTML URL to convert, for example "https://example.com/page.html".',
    )
    parser.add_argument(
        "--output",
        help=(
            "Path to write the markdown output. Defaults to "
            "<URL filename>.md in the current directory."
        ),
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write converted markdown to stdout instead of a file.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(
    argv: Sequence[str] | None = None,
    *,
    service: FileConverter | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = parse_args(argv)
    output_stream = sys.stdout if stdout is None else stdout
    error_stream = sys.stderr if stderr is None else stderr

    converter = MarkItDownFileConversionService() if service is None else service
    try:
        result = converter.convert_url(url=args.url)
    except FileConversionServiceError as error:
        error_stream.write(f"File conversion failed: {error.message}\n")
        if error.details is not None:
            details = json.dumps(error.details, ensure_ascii=False, indent=2)
            error_stream.write(f"{details}\n")
        return 1

    markdown = result["document"]["markdown"]
    if args.stdout:
        output_stream.write(markdown)
        if not markdown.endswith("\n"):
            output_stream.write("\n")
        return 0

    output_path = _resolve_output_path(
        filename=result["document"]["name"],
        output_arg=args.output,
    )
    try:
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as error:
        error_stream.write(f"Failed to write output: {error}\n")
        return 2

    output_stream.write(f"{output_path}\n")
    return 0


def _resolve_output_path(*, filename: str, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).expanduser()
    return Path.cwd() / f"{filename}.md"


if __name__ == "__main__":
    raise SystemExit(main())
