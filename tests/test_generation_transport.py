from __future__ import annotations

import json
import unittest
from collections.abc import Callable

from anki_ai.generation_service import GenerationLogEvent, GenerationServiceError
from anki_ai.generation_transport import register_generation_transport_handlers
from anki_ai.transport import PROTOCOL, JsonObject, TransportRouter


def request_message(
    method: str,
    params: JsonObject | None = None,
    request_id: str = "req-1",
) -> str:
    return json.dumps(
        {
            "protocol": PROTOCOL,
            "kind": "request",
            "id": request_id,
            "method": method,
            "params": {} if params is None else params,
        }
    )


class FakeGenerationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: list[dict[str, str]] | None = None,
        card_count: int = 5,
        card_type: str = "basic",
        log_sink: Callable[[GenerationLogEvent], None] | None = None,
    ) -> JsonObject:
        if log_sink is not None:
            log_sink(
                {
                    "level": "info",
                    "source": "llm",
                    "role": "LLM -> Claude Code",
                    "message": "LLM -> Claude Code: draft cards",
                }
            )
        self.calls.append(
            {
                "source_text": source_text,
                "materials": [] if materials is None else materials,
                "card_count": card_count,
                "card_type": card_type,
            }
        )
        return {
            "cards": [
                {
                    "id": "generated-1",
                    "cardType": card_type,
                    "front": "Front",
                    "back": "Back",
                }
            ],
            "run": {"workspacePath": "/tmp/fake-run"},
        }


class RateLimitedGenerationService:
    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: list[dict[str, str]] | None = None,
        card_count: int = 5,
        card_type: str = "basic",
        log_sink: Callable[[GenerationLogEvent], None] | None = None,
    ) -> JsonObject:
        _ = source_text
        _ = materials
        _ = card_count
        _ = card_type
        _ = log_sink
        raise GenerationServiceError(
            "claude_generation_rate_limited",
            "Claude Code generation was rate limited by the configured API provider.",
            {
                "workspacePath": "/tmp/fake-run",
                "stderr": ["429 429 rate_limit"],
            },
        )


class GenerationTransportHandlersTest(unittest.TestCase):
    def test_generate_cards_accepts_source_text_and_materials(self) -> None:
        service = FakeGenerationService()
        router = TransportRouter()
        register_generation_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message(
                "anki.generation.generateCards",
                {
                    "sourceText": "Important facts",
                    "cardCount": 7,
                    "materials": [
                        {
                            "name": "notes.md",
                            "contentBase64": "aGVsbG8=",
                        }
                    ],
                },
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["cards"][0]["front"], "Front")
        self.assertEqual(
            service.calls,
            [
                {
                    "source_text": "Important facts",
                    "materials": [{"name": "notes.md", "contentBase64": "aGVsbG8="}],
                    "card_count": 7,
                    "card_type": "basic",
                }
            ],
        )

    def test_generate_cards_accepts_card_type(self) -> None:
        service = FakeGenerationService()
        router = TransportRouter()
        register_generation_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message(
                "anki.generation.generateCards",
                {
                    "sourceText": "Important facts",
                    "cardType": "answer_with_explanation",
                },
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(
            response["result"]["cards"][0]["cardType"],
            "answer_with_explanation",
        )
        self.assertEqual(service.calls[0]["card_type"], "answer_with_explanation")

    def test_generate_cards_rejects_unknown_card_type(self) -> None:
        router = TransportRouter()
        register_generation_transport_handlers(router, FakeGenerationService())

        response = router.handle_raw_message(
            request_message(
                "anki.generation.generateCards",
                {"sourceText": "Important facts", "cardType": "cloze"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")

    def test_generate_cards_requires_input_material(self) -> None:
        service = FakeGenerationService()
        router = TransportRouter()
        register_generation_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message("anki.generation.generateCards", {"materials": []})
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")

    def test_generate_cards_rejects_invalid_material_shape(self) -> None:
        service = FakeGenerationService()
        router = TransportRouter()
        register_generation_transport_handlers(router, service)

        response = router.handle_raw_message(
            request_message(
                "anki.generation.generateCards",
                {
                    "materials": [
                        {
                            "name": "",
                            "contentBase64": "aGVsbG8=",
                        }
                    ]
                },
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")

    def test_generate_cards_preserves_rate_limit_error_code(self) -> None:
        router = TransportRouter()
        register_generation_transport_handlers(router, RateLimitedGenerationService())

        response = router.handle_raw_message(
            request_message(
                "anki.generation.generateCards",
                {"sourceText": "Important facts"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "claude_generation_rate_limited")
        self.assertIn("stderr", response["error"]["details"])

    def test_start_generate_cards_returns_job_and_emits_events(self) -> None:
        service = FakeGenerationService()
        events: list[tuple[str, JsonObject]] = []

        def run_immediately(
            operation: Callable[[], JsonObject],
            on_done: Callable[[JsonObject | BaseException], None],
        ) -> None:
            try:
                outcome: JsonObject | BaseException = operation()
            except BaseException as error:
                outcome = error
            on_done(outcome)

        router = TransportRouter()
        register_generation_transport_handlers(
            router,
            service,
            background_runner=run_immediately,
            event_emitter=lambda event, payload: events.append((event, payload)),
        )

        response = router.handle_raw_message(
            request_message(
                "anki.generation.startGenerateCards",
                {"sourceText": "Important facts"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        job_id = response["result"]["jobId"]
        self.assertIsInstance(job_id, str)
        self.assertEqual(
            [payload["status"] for _, payload in events],
            ["started", "log", "succeeded"],
        )
        self.assertTrue(all(payload["jobId"] == job_id for _, payload in events))
        self.assertEqual(events[1][1]["message"], "LLM -> Claude Code: draft cards")
        self.assertEqual(events[1][1]["source"], "llm")
        self.assertEqual(events[1][1]["role"], "LLM -> Claude Code")
        self.assertEqual(events[2][1]["result"]["cards"][0]["front"], "Front")

    def test_start_generate_cards_reports_event_unavailable_without_emitter(
        self,
    ) -> None:
        router = TransportRouter()
        register_generation_transport_handlers(router, FakeGenerationService())

        response = router.handle_raw_message(
            request_message(
                "anki.generation.startGenerateCards",
                {"sourceText": "Important facts"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(
            response["error"]["code"],
            "generation_events_unavailable",
        )

    def test_start_generate_cards_emits_failure_event(self) -> None:
        events: list[tuple[str, JsonObject]] = []

        def run_immediately(
            operation: Callable[[], JsonObject],
            on_done: Callable[[JsonObject | BaseException], None],
        ) -> None:
            try:
                outcome: JsonObject | BaseException = operation()
            except BaseException as error:
                outcome = error
            on_done(outcome)

        router = TransportRouter()
        register_generation_transport_handlers(
            router,
            RateLimitedGenerationService(),
            background_runner=run_immediately,
            event_emitter=lambda event, payload: events.append((event, payload)),
        )

        response = router.handle_raw_message(
            request_message(
                "anki.generation.startGenerateCards",
                {"sourceText": "Important facts"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(
            [payload["status"] for _, payload in events],
            ["started", "failed"],
        )
        self.assertEqual(
            events[1][1]["error"]["code"],
            "claude_generation_rate_limited",
        )
        self.assertIn("stderr", events[1][1]["error"]["details"])


if __name__ == "__main__":
    unittest.main()
