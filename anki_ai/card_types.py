"""Application-level card type identifiers."""

from __future__ import annotations


class CardTypeError(ValueError):
    """Raised when an unknown application card type is requested."""


BASIC_CARD_TYPE_ID = "basic"
ANSWER_WITH_EXPLANATION_CARD_TYPE_ID = "answer_with_explanation"
DEFAULT_CARD_TYPE_ID = BASIC_CARD_TYPE_ID

CARD_TYPE_IDS = (
    BASIC_CARD_TYPE_ID,
    ANSWER_WITH_EXPLANATION_CARD_TYPE_ID,
)


def card_type_ids() -> tuple[str, ...]:
    return CARD_TYPE_IDS


def normalize_card_type_id(card_type_id: str | None) -> str:
    normalized_id = DEFAULT_CARD_TYPE_ID if card_type_id is None else card_type_id
    if normalized_id not in CARD_TYPE_IDS:
        raise CardTypeError(f"Unknown card type: {normalized_id}")
    return normalized_id
