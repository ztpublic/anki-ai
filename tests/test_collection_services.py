from __future__ import annotations

import unittest

from anki_ai.collection_services import AnkiCollectionService, CollectionServiceError

from .fakes import FakeCollection


class AnkiCollectionServiceTest(unittest.TestCase):
    def test_collection_snapshot_lists_decks_with_counts(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        snapshot = service.collection_snapshot()

        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["cardCount"], 2)
        self.assertEqual(snapshot["deckCount"], 2)
        self.assertEqual(
            snapshot["decks"],
            [
                {"id": "2", "name": "Archive", "cardCount": 1},
                {"id": "1", "name": "Default", "cardCount": 1},
            ],
        )

    def test_ensure_deck_reuses_existing_deck(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        result = service.ensure_deck("Default")

        self.assertFalse(result["created"])
        self.assertEqual(result["deck"], {"id": "1", "name": "Default", "cardCount": None})
        self.assertEqual(len(collection.decks.decks), 2)

    def test_ensure_deck_creates_missing_deck(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        result = service.ensure_deck("AI Generated")

        self.assertTrue(result["created"])
        self.assertEqual(result["deck"], {"id": "3", "name": "AI Generated", "cardCount": None})
        self.assertEqual(collection.decks.decks[3]["name"], "AI Generated")

    def test_rename_deck_saves_mapping(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        deck = service.rename_deck(2, "Reviewed")

        self.assertEqual(deck, {"id": "2", "name": "Reviewed", "cardCount": None})
        self.assertEqual(collection.decks.saved, [{"id": 2, "name": "Reviewed"}])

    def test_get_card_returns_note_and_scheduling_snapshot(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        card = service.get_card(101)

        self.assertEqual(card["id"], "101")
        self.assertEqual(card["noteId"], "201")
        self.assertEqual(card["deckId"], "1")
        self.assertEqual(card["question"], "Capital of France?")
        self.assertEqual(card["answer"], "Paris")
        self.assertEqual(
            card["fields"],
            {"Front": "Capital of France?", "Back": "Paris"},
        )
        self.assertEqual(card["tags"], ["geography"])
        self.assertEqual(card["state"]["factor"], 2500)

    def test_update_note_fields_persists_note_and_returns_updated_card(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        card = service.update_note_fields(
            101,
            {"Front": "Capital of Germany?", "Back": "Berlin"},
        )

        self.assertEqual(card["question"], "Capital of Germany?")
        self.assertEqual(card["answer"], "Berlin")
        self.assertEqual(len(collection.updated_notes), 1)
        self.assertEqual(
            collection.updated_notes[0].fields,
            {"Front": "Capital of Germany?", "Back": "Berlin"},
        )

    def test_update_note_fields_rejects_unknown_field(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        with self.assertRaises(CollectionServiceError) as error:
            service.update_note_fields(101, {"Extra": "Nope"})

        self.assertEqual(error.exception.code, "unknown_note_field")
        self.assertEqual(collection.updated_notes, [])

    def test_move_cards_to_existing_deck_updates_cards(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        result = service.move_cards_to_deck([101, 102], deck_id=1)

        self.assertEqual(
            result,
            {
                "deck": {"id": "1", "name": "Default", "cardCount": None},
                "updatedCardIds": ["101", "102"],
            },
        )
        self.assertEqual(collection.cards[101].did, 1)
        self.assertEqual(collection.cards[102].did, 1)
        self.assertEqual([card.id for card in collection.updated_cards], [101, 102])

    def test_move_cards_to_named_deck_creates_deck(self) -> None:
        collection = FakeCollection()
        service = AnkiCollectionService(collection)

        result = service.move_cards_to_deck([101], deck_name="Generated")

        self.assertEqual(result["deck"], {"id": "3", "name": "Generated", "cardCount": None})
        self.assertEqual(collection.cards[101].did, 3)


if __name__ == "__main__":
    unittest.main()
