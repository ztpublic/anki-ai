"""Card answer regeneration workflows."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Protocol, TypedDict


REGENERATE_ANSWER_WORKFLOW_ID = "regenerate_answer"
REGENERATED_CARD_OUTPUT_FILENAME = "regenerated_card.json"
CARD_REGENERATION_INPUT_FILENAME = "card.json"


class RegeneratedCardFields(TypedDict):
    answer: str


class CardRegenerationWorkflowError(Exception):
    """A card regeneration workflow could not render or normalize output."""

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


class CardRegenerationWorkflow(Protocol):
    workflow_id: str
    output_filename: str

    def build_prompt(self) -> str:
        ...

    def normalize_output(self, value: Any) -> RegeneratedCardFields:
        ...


PROMPT_TEMPLATE_DIR = Path(__file__).with_name("prompts")
ADDON_DIR = Path(__file__).resolve().parent
ADDON_VENDOR_DIR = ADDON_DIR / "vendor"


class BaseCardRegenerationWorkflow:
    """Shared prompt rendering and answer validation."""

    workflow_id: str
    template_name: str
    output_filename = REGENERATED_CARD_OUTPUT_FILENAME

    def build_prompt(self) -> str:
        try:
            template = _prompt_environment().get_template(self.template_name)
            return str(
                template.render(
                    input_filename=CARD_REGENERATION_INPUT_FILENAME,
                    output_filename=self.output_filename,
                    include_explanation=False,
                )
            )
        except Exception as error:
            if isinstance(error, CardRegenerationWorkflowError):
                raise
            raise CardRegenerationWorkflowError(
                "invalid_regeneration_prompt",
                "Card regeneration prompt template could not be rendered.",
                {
                    "workflow": self.workflow_id,
                    "template": self.template_name,
                    "error": str(error),
                },
            ) from error

    def normalize_output(self, value: Any) -> RegeneratedCardFields:
        if not isinstance(value, dict):
            raise CardRegenerationWorkflowError(
                "invalid_regenerated_card_output",
                f"{self.output_filename} must contain a JSON object.",
            )

        output: RegeneratedCardFields = {
            "answer": self._required_string_field(
                value,
                names=("Back", "back", "Answer", "answer"),
            )
        }
        return output

    @staticmethod
    def _required_string_field(
        item: dict[Any, Any],
        *,
        names: tuple[str, ...],
    ) -> str:
        value = next((item[name] for name in names if name in item), None)
        if not isinstance(value, str) or not value.strip():
            quoted_names = " or ".join(f'"{name}"' for name in names)
            raise CardRegenerationWorkflowError(
                "invalid_regenerated_card_output",
                f"Regenerated card output must have a non-empty string field {quoted_names}.",
            )

        return value


class RegenerateAnswerWorkflow(BaseCardRegenerationWorkflow):
    workflow_id = REGENERATE_ANSWER_WORKFLOW_ID
    template_name = "regenerate_answer.md.jinja"


REGENERATION_WORKFLOWS: dict[str, CardRegenerationWorkflow] = {
    REGENERATE_ANSWER_WORKFLOW_ID: RegenerateAnswerWorkflow(),
}


def get_regeneration_workflow(workflow_id: str) -> CardRegenerationWorkflow:
    try:
        return REGENERATION_WORKFLOWS[workflow_id]
    except KeyError as error:
        raise CardRegenerationWorkflowError(
            "invalid_regeneration_workflow",
            f"Unknown card regeneration workflow: {workflow_id}",
            {
                "workflow": workflow_id,
                "supportedWorkflows": list(REGENERATION_WORKFLOWS),
            },
        ) from error


def _prompt_environment() -> Any:
    _bootstrap_prompt_runtime()
    try:
        jinja2 = importlib.import_module("jinja2")
    except ImportError as error:
        raise CardRegenerationWorkflowError(
            "missing_prompt_renderer",
            "Jinja2 is not available for card regeneration prompt rendering.",
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
