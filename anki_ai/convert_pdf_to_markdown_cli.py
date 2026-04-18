"""Command-line entry point for file-to-markdown conversion."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TextIO

from anki_ai.file_conversion_service import (
    FileConversionInput,
    FileConversionResult,
    FileConversionServiceError,
    MarkItDownFileConversionService,
)


class FileConverter(Protocol):
    def convert_file(
        self,
        *,
        file: FileConversionInput,
    ) -> FileConversionResult: ...


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a local file to markdown using the Anki AI file "
            "conversion service."
        )
    )
    parser.add_argument(
        "material_path",
        help="Path to a local file to convert.",
    )
    parser.add_argument(
        "--output",
        help=(
            "Path to write the markdown output. Defaults to "
            "<input filename>.md next to the source file."
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

    material_path = Path(args.material_path).expanduser()
    if not material_path.is_file():
        error_stream.write(f"Material file not found: {material_path}\n")
        return 2

    try:
        material_bytes = material_path.read_bytes()
    except OSError as error:
        error_stream.write(f"Failed to read material file: {error}\n")
        return 2

    converter = MarkItDownFileConversionService() if service is None else service
    material: FileConversionInput = {
        "name": material_path.name,
        "contentBase64": base64.b64encode(material_bytes).decode("ascii"),
    }

    try:
        result = converter.convert_file(file=material)
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
        material_path=material_path,
        output_arg=args.output,
    )

    try:
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as error:
        error_stream.write(f"Failed to write output: {error}\n")
        return 2

    output_stream.write(f"{output_path}\n")
    return 0


def _resolve_output_path(*, material_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).expanduser()
    return material_path.with_name(f"{material_path.name}.md")


if __name__ == "__main__":
    raise SystemExit(main())
