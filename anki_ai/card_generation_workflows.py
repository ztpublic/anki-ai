"""Card-type-specific Claude generation workflows."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, TypedDict

from .card_types import (
    BASIC_CARD_TYPE_ID,
    CardTypeError,
)


class GeneratedCardBase(TypedDict):
    id: str
    cardType: str
    front: str
    back: str


class GeneratedCard(GeneratedCardBase, total=False):
    explanation: str


class CardGenerationWorkflowError(Exception):
    """A card generation workflow could not render or normalize output."""

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


class CardGenerationWorkflow(Protocol):
    card_type_id: str

    def build_prompt(
        self,
        *,
        material_names: Sequence[str],
        card_count: int,
    ) -> str:
        ...

    def normalize_cards(self, value: Any) -> list[GeneratedCard]:
        ...


PROMPT_TEMPLATE_DIR = Path(__file__).with_name("prompts")
ADDON_DIR = Path(__file__).resolve().parent
ADDON_VENDOR_DIR = ADDON_DIR / "vendor"


class BaseCardGenerationWorkflow:
    """Shared prompt rendering and Front/Back validation."""

    card_type_id: str
    template_name: str

    def build_prompt(
        self,
        *,
        material_names: Sequence[str],
        card_count: int,
    ) -> str:
        try:
            template = _prompt_environment().get_template(self.template_name)
            return str(
                template.render(
                    target_card_count=card_count,
                    material_names=list(material_names),
                )
            )
        except Exception as error:
            if isinstance(error, CardGenerationWorkflowError):
                raise
            raise CardGenerationWorkflowError(
                "invalid_generation_prompt",
                "Card generation prompt template could not be rendered.",
                {
                    "cardType": self.card_type_id,
                    "template": self.template_name,
                    "error": str(error),
                },
            ) from error

    def normalize_cards(self, value: Any) -> list[GeneratedCard]:
        if not isinstance(value, list) or not value:
            raise CardGenerationWorkflowError(
                "invalid_cards_output",
                "cards.json must contain a non-empty JSON array.",
            )

        cards: list[GeneratedCard] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise CardGenerationWorkflowError(
                    "invalid_cards_output",
                    "Each cards.json entry must be an object.",
                    {"cardIndex": index},
                )

            card = self._normalize_card(item, index=index)
            cards.append(card)

        return cards

    def _normalize_card(self, item: dict[Any, Any], *, index: int) -> GeneratedCard:
        front = self._required_string_field(item, index=index, names=("Front", "front"))
        back = self._required_string_field(item, index=index, names=("Back", "back"))
        return {
            "id": f"generated-{index + 1}",
            "cardType": self.card_type_id,
            "front": front,
            "back": back,
        }

    @staticmethod
    def _required_string_field(
        item: dict[Any, Any],
        *,
        index: int,
        names: tuple[str, ...],
    ) -> str:
        value = next((item[name] for name in names if name in item), None)
        if not isinstance(value, str) or not value.strip():
            quoted_names = " or ".join(f'"{name}"' for name in names)
            raise CardGenerationWorkflowError(
                "invalid_cards_output",
                f"Each card must have a non-empty string field {quoted_names}.",
                {"cardIndex": index},
            )

        return value


class BasicQuestionAnswerGenerationWorkflow(BaseCardGenerationWorkflow):
    card_type_id = BASIC_CARD_TYPE_ID
    template_name = "basic.md.jinja"


GENERATION_WORKFLOWS: dict[str, CardGenerationWorkflow] = {
    BASIC_CARD_TYPE_ID: BasicQuestionAnswerGenerationWorkflow(),
}


def get_generation_workflow(card_type_id: str) -> CardGenerationWorkflow:
    try:
        return GENERATION_WORKFLOWS[card_type_id]
    except KeyError as error:
        raise CardTypeError(f"Unknown card type: {card_type_id}") from error


def _prompt_environment() -> Any:
    _bootstrap_prompt_runtime()
    try:
        jinja2 = importlib.import_module("jinja2")
    except ImportError as error:
        raise CardGenerationWorkflowError(
            "missing_prompt_renderer",
            "Jinja2 is not available for card generation prompt rendering.",
            {"dependency": "jinja2"},
        ) from error

    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(PROMPT_TEMPLATE_DIR),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )


def _bootstrap_prompt_runtime() -> None:
    if ADDON_VENDOR_DIR.is_dir():
        vendor_path = str(ADDON_VENDOR_DIR)
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)
