"""Native Anki reviewer integration for answer regeneration."""

from __future__ import annotations

import json
import re
import threading
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .generation_service import ClaudeCardGenerationService, GenerationServiceError

REVIEWER_MESSAGE_PREFIX = "anki-ai-reviewer:"
REVIEWER_ENTRY_MANIFEST_KEY = "src/reviewer.tsx"
EXPLANATION_SEPARATOR = "\n\nExplanation:\n"

_registered = False


def register_reviewer_regeneration_hooks() -> None:
    """Register hooks that add regeneration controls to Anki's reviewer."""
    global _registered
    if _registered:
        return

    from aqt import gui_hooks

    gui_hooks.webview_will_set_content.append(_inject_reviewer_assets)
    gui_hooks.card_will_show.append(_append_reviewer_panel_mount)
    gui_hooks.webview_did_receive_js_message.append(_handle_reviewer_message)
    _registered = True


def _inject_reviewer_assets(web_content: Any, context: object | None) -> None:
    if not _is_reviewer_context(context):
        return

    assets = _reviewer_assets()
    if assets is None:
        return

    css_files, js_file = assets
    base_url = _addon_web_base_url()
    for css_file in css_files:
        web_content.head += (
            f'<link rel="stylesheet" href="{base_url}{escape(css_file)}">'
        )
    web_content.body += (
        f'<script type="module" src="{base_url}{escape(js_file)}"></script>'
    )


def _append_reviewer_panel_mount(text: str, card: Any, kind: str) -> str:
    if kind != "reviewAnswer" or not _can_update_card(card):
        return text

    card_id = escape(str(getattr(card, "id", "")), quote=True)
    if not card_id:
        return text

    return (
        text
        + "\n"
        + (
            '<div data-anki-ai-reviewer-regeneration="1" '
            f'data-card-id="{card_id}"></div>'
        )
    )


def _handle_reviewer_message(
    handled: tuple[bool, Any],
    message: str,
    context: object | None,
) -> tuple[bool, Any]:
    if not message.startswith(REVIEWER_MESSAGE_PREFIX):
        return handled
    if not _is_reviewer_context(context):
        return handled

    try:
        payload = json.loads(message[len(REVIEWER_MESSAGE_PREFIX) :])
    except json.JSONDecodeError:
        return (True, {"ok": False, "error": "Invalid Anki AI reviewer message."})
    if not isinstance(payload, dict):
        return (True, {"ok": False, "error": "Invalid Anki AI reviewer message."})

    action = payload.get("action")
    if action == "regenerate":
        _start_regeneration(context, payload)
        return (True, {"ok": True})
    if action == "accept":
        _accept_regeneration(context, payload)
        return (True, {"ok": True})

    return (True, {"ok": False, "error": "Unknown Anki AI reviewer action."})


def _start_regeneration(reviewer: object, payload: dict[str, Any]) -> None:
    request_id = _payload_string(payload, "requestId")
    card_id = _payload_string(payload, "cardId")
    mode = _payload_string(payload, "mode")
    if mode != "answer":
        _send_reviewer_result(
            reviewer,
            {
                "action": "regenerationResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": "Unsupported regeneration mode.",
            },
        )
        return

    card = getattr(reviewer, "card", None)
    if card is None or str(getattr(card, "id", "")) != card_id:
        _send_reviewer_result(
            reviewer,
            {
                "action": "regenerationResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": "The reviewed card changed before regeneration started.",
            },
        )
        return

    try:
        card_text = _extract_card_text(card)
    except ValueError as error:
        _send_reviewer_result(
            reviewer,
            {
                "action": "regenerationResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": str(error),
            },
        )
        return

    def run() -> None:
        try:
            service = ClaudeCardGenerationService()
            result = service.regenerate_answer(
                question=card_text["question"] or "",
                answer=card_text["answer"] or "",
                explanation=card_text["explanation"],
            )
            response: dict[str, Any] = {
                "action": "regenerationResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": True,
                "fields": result["fields"],
            }
        except GenerationServiceError as error:
            response = {
                "action": "regenerationResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": error.message,
            }
        except Exception as error:
            response = {
                "action": "regenerationResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": str(error),
            }

        _run_on_main(lambda: _send_reviewer_result(reviewer, response))

    threading.Thread(target=run, daemon=True).start()


def _accept_regeneration(reviewer: object, payload: dict[str, Any]) -> None:
    request_id = _payload_string(payload, "requestId")
    card_id = _payload_string(payload, "cardId")
    mode = _payload_string(payload, "mode")
    answer = _payload_string(payload, "answer")
    explanation = payload.get("explanation")
    if explanation is not None and not isinstance(explanation, str):
        explanation = None

    card = getattr(reviewer, "card", None)
    if card is None or str(getattr(card, "id", "")) != card_id:
        _send_reviewer_result(
            reviewer,
            {
                "action": "acceptResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": "The reviewed card changed before the suggestion was accepted.",
            },
        )
        return

    try:
        note = card.note()
        _write_regenerated_fields(
            note,
            mode=mode,
            answer=answer,
            explanation=explanation,
        )
        _update_note(note)
        _refresh_reviewer_answer(reviewer, card)
    except Exception as error:
        _send_reviewer_result(
            reviewer,
            {
                "action": "acceptResult",
                "requestId": request_id,
                "cardId": card_id,
                "ok": False,
                "error": str(error),
            },
        )
        return

    _send_reviewer_result(
        reviewer,
        {
            "action": "acceptResult",
            "requestId": request_id,
            "cardId": card_id,
            "ok": True,
        },
    )


def _extract_card_text(card: Any) -> dict[str, str | None]:
    note = card.note()
    question_field = _question_field_name(note)
    answer_field = _answer_field_name(note)
    if question_field is None or answer_field is None:
        raise ValueError(
            "This note type needs at least question and answer fields to regenerate."
        )

    raw_answer = str(note[answer_field])
    answer, combined_explanation = _split_combined_answer(raw_answer)
    explanation_field = _explanation_field_name(note)
    explanation = (
        str(note[explanation_field])
        if explanation_field is not None
        else combined_explanation
    )
    return {
        "question": str(note[question_field]),
        "answer": answer,
        "explanation": explanation,
    }


def _write_regenerated_fields(
    note: Any,
    *,
    mode: str,
    answer: str,
    explanation: str | None,
) -> None:
    answer_field = _answer_field_name(note)
    if answer_field is None:
        raise ValueError("Could not find an answer field on this note type.")
    if mode != "answer":
        raise ValueError("Unsupported regeneration mode.")

    explanation_field = _explanation_field_name(note)
    if explanation_field is not None:
        note[answer_field] = answer
        return

    _, existing_explanation = _split_combined_answer(str(note[answer_field]))
    note[answer_field] = _combine_answer_and_explanation(
        answer,
        existing_explanation,
    )


def _split_combined_answer(value: str) -> tuple[str, str | None]:
    match = re.search(r"\n\s*\n?Explanation:\s*", value, flags=re.IGNORECASE)
    if match is None:
        return value, None

    return value[: match.start()].strip(), value[match.end() :].strip()


def _combine_answer_and_explanation(
    answer: str,
    explanation: str | None,
) -> str:
    if explanation is None or not explanation.strip():
        return answer
    return f"{answer}{EXPLANATION_SEPARATOR}{explanation.strip()}"


def _can_update_card(card: Any) -> bool:
    try:
        note = card.note()
    except Exception:
        return False

    return _question_field_name(note) is not None and _answer_field_name(note) is not None


def _question_field_name(note: Any) -> str | None:
    return _preferred_field_name(note, ("Front", "Question", "Prompt"), fallback_index=0)


def _answer_field_name(note: Any) -> str | None:
    return _preferred_field_name(note, ("Back", "Answer"), fallback_index=1)


def _explanation_field_name(note: Any) -> str | None:
    return _preferred_field_name(note, ("Explanation", "Reasoning"), fallback_index=None)


def _preferred_field_name(
    note: Any,
    names: tuple[str, ...],
    *,
    fallback_index: int | None,
) -> str | None:
    field_names = _note_field_names(note)
    lower_to_name = {name.lower(): name for name in field_names}
    for name in names:
        existing_name = lower_to_name.get(name.lower())
        if existing_name is not None:
            return existing_name

    if fallback_index is not None and fallback_index < len(field_names):
        return field_names[fallback_index]
    return None


def _note_field_names(note: Any) -> list[str]:
    keys = getattr(note, "keys", None)
    if callable(keys):
        return [str(name) for name in keys()]

    items = getattr(note, "items", None)
    if callable(items):
        return [str(name) for name, _ in items()]

    return []


def _update_note(note: Any) -> None:
    from aqt import mw

    update_note = getattr(mw.col, "update_note", None)
    if callable(update_note):
        update_note(note)
        return

    flush = getattr(note, "flush", None)
    if callable(flush):
        flush()
        return

    raise RuntimeError("The active Anki collection cannot update this note.")


def _refresh_reviewer_answer(reviewer: object, card: Any) -> None:
    load = getattr(card, "load", None)
    if callable(load):
        load()

    show_answer = getattr(reviewer, "_showAnswer", None)
    if callable(show_answer):
        show_answer()


def _send_reviewer_result(reviewer: object, payload: dict[str, Any]) -> None:
    web = getattr(reviewer, "web", None)
    eval_js = getattr(web, "eval", None)
    if not callable(eval_js):
        return

    eval_js(
        "window.AnkiAIReviewer && "
        f"window.AnkiAIReviewer.receive({json.dumps(payload, ensure_ascii=False)});"
    )


def _payload_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _is_reviewer_context(context: object | None) -> bool:
    try:
        from aqt.reviewer import Reviewer
    except Exception:
        return False

    return isinstance(context, Reviewer)


def _reviewer_assets() -> tuple[list[str], str] | None:
    manifest_path = Path(__file__).with_name("web") / ".vite" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    entry = manifest.get(REVIEWER_ENTRY_MANIFEST_KEY)
    if not isinstance(entry, dict):
        return None

    js_file = entry.get("file")
    if not isinstance(js_file, str):
        return None

    css_files = _manifest_css_files(manifest, entry)
    return css_files, js_file


def _manifest_css_files(
    manifest: dict[str, Any],
    entry: dict[str, Any],
    *,
    seen: set[str] | None = None,
) -> list[str]:
    if seen is None:
        seen = set()

    css_files: list[str] = []
    for css_file in entry.get("css", []):
        if isinstance(css_file, str) and css_file not in css_files:
            css_files.append(css_file)

    for import_key in entry.get("imports", []):
        if not isinstance(import_key, str) or import_key in seen:
            continue
        seen.add(import_key)
        imported_entry = manifest.get(import_key)
        if not isinstance(imported_entry, dict):
            continue
        for css_file in _manifest_css_files(
            manifest,
            imported_entry,
            seen=seen,
        ):
            if css_file not in css_files:
                css_files.append(css_file)

    return css_files


def _addon_web_base_url() -> str:
    from aqt import mw

    addon_package = quote(mw.addonManager.addonFromModule(__name__))
    return f"/_addons/{addon_package}/web/"


def _run_on_main(callback: Any) -> None:
    from aqt import mw

    mw.taskman.run_on_main(callback)
