"""Command-line entry point for Claude Code-backed card generation."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TextIO

from anki_ai.card_types import DEFAULT_CARD_TYPE_ID, card_type_ids
from anki_ai.card_generation_workflows import GeneratedCard
from anki_ai.generation_service import (
    ClaudeCardGenerationService,
    GenerationResult,
    GenerationServiceError,
    MaterialInput,
)


class CardGenerator(Protocol):
    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: Sequence[MaterialInput] = (),
        card_count: int = ClaudeCardGenerationService.DEFAULT_CARD_COUNT,
        card_type: str = DEFAULT_CARD_TYPE_ID,
    ) -> GenerationResult: ...


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Anki cards from a local file using the Claude Code-backed "
            "generation workflow."
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
    parser.add_argument(
        "--card-type",
        choices=card_type_ids(),
        default=DEFAULT_CARD_TYPE_ID,
        help="Application card type to generate.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(
    argv: Sequence[str] | None = None,
    *,
    service: CardGenerator | None = None,
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

    generator = ClaudeCardGenerationService() if service is None else service
    material: MaterialInput = {
        "name": material_path.name,
        "contentBase64": base64.b64encode(material_bytes).decode("ascii"),
    }

    try:
        result = generator.generate_cards(
            materials=[material],
            card_count=args.card_count,
            card_type=args.card_type,
        )
    except GenerationServiceError as error:
        error_stream.write(f"Card generation failed: {error.message}\n")
        if error.details is not None:
            details = json.dumps(error.details, ensure_ascii=False, indent=2)
            error_stream.write(f"{details}\n")
        return 1

    rendered_cards = _render_cards_json(result["cards"])
    output_path = material_path.with_name(f"{material_path.name}.json")
    try:
        output_path.write_text(f"{rendered_cards}\n", encoding="utf-8")
    except OSError as error:
        error_stream.write(f"Failed to write output: {error}\n")
        return 2

    output_stream.write(f"{output_path}\n")
    return 0


def _render_cards_json(cards: Sequence[GeneratedCard]) -> str:
    payload: list[dict[str, str]] = []
    for card in cards:
        rendered = {
            "Front": card["front"],
            "Back": card["back"],
        }
        explanation = card.get("explanation")
        if explanation is not None:
            rendered["Explanation"] = explanation
        payload.append(rendered)
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
