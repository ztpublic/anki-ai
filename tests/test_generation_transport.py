from __future__ import annotations

import json
import unittest

from anki_ai.generation_service import GenerationServiceError
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
    ) -> JsonObject:
        self.calls.append(
            {
                "source_text": source_text,
                "materials": [] if materials is None else materials,
                "card_count": card_count,
            }
        )
        return {
            "cards": [{"id": "generated-1", "front": "Front", "back": "Back"}],
            "run": {"workspacePath": "/tmp/fake-run"},
        }


class RateLimitedGenerationService:
    def generate_cards(
        self,
        *,
        source_text: str | None = None,
        materials: list[dict[str, str]] | None = None,
        card_count: int = 5,
    ) -> JsonObject:
        _ = source_text
        _ = materials
        _ = card_count
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
                }
            ],
        )

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


if __name__ == "__main__":
    unittest.main()
