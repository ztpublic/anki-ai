#!/usr/bin/env python3

from __future__ import annotations

"""Fetch a YouTube transcript or markdown using MarkItDown."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from markitdown import MarkItDown
from youtube_transcript_api import YouTubeTranscriptApi


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch a YouTube transcript by default, or full markdown with "
            "MarkItDown when --markdown is set. In zsh, quote the URL so "
            "characters like '?' are not treated as glob patterns."
        ),
    )
    parser.add_argument(
        "url",
        help='YouTube URL to convert, for example "https://www.youtube.com/watch?v=...".',
    )
    parser.add_argument(
        "--output",
        help=(
            "Path to write output. By default the script writes the transcript "
            "to stdout."
        ),
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Return full markdown from MarkItDown instead of transcript-only text.",
    )
    parser.add_argument(
        "--language",
        action="append",
        dest="languages",
        help=(
            "Preferred transcript language code. Repeat to provide fallbacks, "
            'for example: --language en --language zh-Hans'
        ),
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    languages = args.languages or ["en"]

    try:
        if args.markdown:
            output = _convert_to_markdown(args.url, languages=languages)
        else:
            output = _fetch_transcript(args.url, languages=languages)
    except Exception as error:
        sys.stderr.write(f"Failed to fetch YouTube output: {error}\n")
        return 1

    if args.output:
        output_path = Path(args.output).expanduser()
        try:
            output_path.write_text(output, encoding="utf-8")
        except OSError as error:
            sys.stderr.write(f"Failed to write output: {error}\n")
            return 2
        sys.stdout.write(f"{output_path}\n")
        return 0

    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _convert_to_markdown(url: str, *, languages: list[str]) -> str:
    converter = MarkItDown()
    result = converter.convert(url, youtube_transcript_languages=languages)
    return result.markdown


def _fetch_transcript(url: str, *, languages: list[str]) -> str:
    video_id = _extract_video_id(url)
    if video_id is None:
        raise ValueError("Could not extract a YouTube video id from the URL.")

    transcript = YouTubeTranscriptApi().fetch(video_id, languages=languages)
    text = " ".join(part.text for part in transcript).strip()
    if not text:
        raise ValueError("The YouTube transcript was empty.")
    return text


def _extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.lstrip("/").strip()
        return video_id or None

    if parsed.netloc in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        video_ids = parse_qs(parsed.query).get("v")
        if video_ids:
            return video_ids[0].strip() or None

    return None


if __name__ == "__main__":
    raise SystemExit(main())
