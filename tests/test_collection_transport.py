from __future__ import annotations

import json
import unittest

from anki_ai.collection_transport import register_collection_transport_handlers
from anki_ai.transport import PROTOCOL, JsonObject, TransportRouter

from .fakes import FakeCollection


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


class CollectionTransportHandlersTest(unittest.TestCase):
    def test_collection_status_reports_unavailable_without_error(self) -> None:
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: None)

        response = router.handle_raw_message(request_message("anki.collection.status"))

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(
            response["result"],
            {"available": False, "cardCount": None, "deckCount": 0},
        )

    def test_collection_snapshot_returns_collection_data(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message("anki.collection.snapshot", {"includeCardCounts": False})
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["deckCount"], 2)
        self.assertEqual(response["result"]["cardCount"], 2)
        self.assertEqual(
            response["result"]["decks"][0],
            {"id": "2", "name": "Archive", "cardCount": None},
        )

    def test_ensure_deck_returns_created_payload(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message("anki.decks.ensure", {"name": "Generated"})
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(
            response["result"],
            {
                "created": True,
                "deck": {"id": "3", "name": "Generated", "cardCount": None},
            },
        )

    def test_search_cards_returns_card_snapshots(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message("anki.cards.search", {"query": "deck:Default", "limit": 10})
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(len(response["result"]["cards"]), 1)
        self.assertEqual(response["result"]["cards"][0]["id"], "101")

    def test_add_cards_to_deck_accepts_batch_card_payloads(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message(
                "anki.cards.addToDeck",
                {
                    "deckName": "Generated",
                    "noteTypeName": "Basic",
                    "cards": [
                        {
                            "fields": {"Front": "Question 1", "Back": "Answer 1"},
                            "tags": ["ai", "reviewed"],
                        },
                        {
                            "fields": {"Front": "Question 2", "Back": "Answer 2"},
                        },
                    ],
                },
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["deck"]["id"], "3")
        self.assertEqual(response["result"]["noteType"]["name"], "Basic")
        self.assertEqual(len(response["result"]["cards"]), 2)
        self.assertEqual(response["result"]["cards"][0]["question"], "Question 1")
        self.assertEqual(response["result"]["cards"][0]["tags"], ["ai", "reviewed"])

    def test_update_note_fields_returns_domain_error(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message(
                "anki.cards.updateNoteFields",
                {"cardId": "101", "fields": {"Extra": "Nope"}},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "unknown_note_field")

    def test_move_cards_to_deck_accepts_ids_as_strings(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message(
                "anki.cards.moveToDeck",
                {"cardIds": ["101"], "deckName": "Generated"},
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["updatedCardIds"], ["101"])
        self.assertEqual(collection.cards[101].did, 3)

    def test_invalid_params_return_transport_error(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message("anki.cards.get", {"cardId": True})
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")

    def test_add_cards_to_deck_rejects_invalid_tag_payloads(self) -> None:
        collection = FakeCollection()
        router = TransportRouter()
        register_collection_transport_handlers(router, lambda: collection)

        response = router.handle_raw_message(
            request_message(
                "anki.cards.addToDeck",
                {
                    "deckId": "1",
                    "cards": [
                        {
                            "fields": {"Front": "Question", "Back": "Answer"},
                            "tags": [True],
                        }
                    ],
                },
            )
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_params")


if __name__ == "__main__":
    unittest.main()
