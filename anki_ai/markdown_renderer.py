"""Markdown-to-Anki-HTML rendering helpers."""

from __future__ import annotations

import html
import importlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ADDON_DIR = Path(__file__).resolve().parent
ADDON_VENDOR_DIR = ADDON_DIR / "vendor"


class MarkdownRenderError(Exception):
    """Markdown could not be rendered into safe Anki HTML."""

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


ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "col",
    "colgroup",
    "dd",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "code": {"class"},
    "td": {"align", "colspan", "rowspan"},
    "th": {"align", "colspan", "rowspan"},
}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def render_markdown_to_anki_html(markdown: str) -> str:
    """Render Markdown to sanitized HTML while preserving Anki MathJax."""
    if not isinstance(markdown, str):
        raise MarkdownRenderError(
            "invalid_markdown",
            "Markdown input must be a string.",
        )
    if not markdown.strip():
        return ""

    markdown_it, texmath_plugin, nh3 = _runtime_modules()
    md = markdown_it.MarkdownIt(
        "commonmark",
        {
            "breaks": False,
            "html": True,
            "linkify": False,
            "typographer": False,
        },
    )
    _enable_rule_if_available(md, "table")
    _enable_rule_if_available(md, "strikethrough")
    md.use(texmath_plugin, delimiters="dollars")
    md.use(texmath_plugin, delimiters="brackets")
    _install_math_render_rules(md)

    try:
        rendered = str(md.render(markdown))
        return str(
            nh3.clean(
                rendered,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                url_schemes=ALLOWED_URL_SCHEMES,
                link_rel="noopener noreferrer",
            )
        ).strip()
    except Exception as error:
        if isinstance(error, MarkdownRenderError):
            raise
        raise MarkdownRenderError(
            "markdown_render_failed",
            "Markdown could not be rendered.",
            {"error": str(error)},
        ) from error


def _runtime_modules() -> tuple[Any, Any, Any]:
    _bootstrap_runtime()
    try:
        markdown_it = importlib.import_module("markdown_it")
        texmath = importlib.import_module("mdit_py_plugins.texmath")
        nh3 = importlib.import_module("nh3")
    except ImportError as error:
        raise MarkdownRenderError(
            "missing_markdown_renderer",
            "Markdown rendering dependencies are not available.",
            {"dependency": error.name},
        ) from error

    return markdown_it, texmath.texmath_plugin, nh3


def _bootstrap_runtime() -> None:
    if ADDON_VENDOR_DIR.is_dir():
        vendor_path = str(ADDON_VENDOR_DIR)
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)


def _enable_rule_if_available(md: Any, rule_name: str) -> None:
    try:
        md.enable(rule_name)
    except Exception:
        return


def _install_math_render_rules(md: Any) -> None:
    def render_math_inline(
        self: Any,
        tokens: Sequence[Any],
        idx: int,
        options: Any,
        env: Any,
    ) -> str:
        _ = self
        _ = options
        _ = env
        return _mathjax_text(tokens[idx].content, display=False)

    def render_math_block(
        self: Any,
        tokens: Sequence[Any],
        idx: int,
        options: Any,
        env: Any,
    ) -> str:
        _ = self
        _ = options
        _ = env
        return f"{_mathjax_text(tokens[idx].content, display=True)}\n"

    for rule_name in ("math_inline", "math_single"):
        md.add_render_rule(rule_name, render_math_inline)

    for rule_name in ("math_block", "math_block_eqno"):
        md.add_render_rule(rule_name, render_math_block)


def _mathjax_text(tex: str, *, display: bool) -> str:
    escaped_tex = html.escape(tex.strip(), quote=False)
    if display:
        return f"\\[{escaped_tex}\\]"
    return f"\\({escaped_tex}\\)"
