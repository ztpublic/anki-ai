from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeNote:
    def __init__(
        self,
        note_id: int,
        fields: dict[str, str],
        tags: list[str] | None = None,
    ) -> None:
        self.id = note_id
        self.fields = fields
        self.tags = [] if tags is None else tags

    def items(self) -> list[tuple[str, str]]:
        return list(self.fields.items())

    def __getitem__(self, key: str) -> str:
        return self.fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value


class FakeCard:
    def __init__(
        self,
        card_id: int,
        note: FakeNote,
        deck_id: int,
    ) -> None:
        self.id = card_id
        self.nid = note.id
        self.did = deck_id
        self.queue = 0
        self.type = 0
        self.due = 1
        self.ivl = 0
        self.factor = 2500
        self.reps = 0
        self.lapses = 0
        self.ord = 0
        self.odid = 0
        self.odue = 0
        self._note = note

    def note(self) -> FakeNote:
        return self._note

    def question(self) -> str:
        return self._note.fields.get("Front", "")

    def answer(self) -> str:
        return self._note.fields.get("Back", "")


class FakeDecks:
    def __init__(self) -> None:
        self.decks: dict[int, dict[str, Any]] = {
            1: {"id": 1, "name": "Default"},
            2: {"id": 2, "name": "Archive"},
        }
        self.saved: list[dict[str, Any]] = []

    def all_names_and_ids(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(id=deck["id"], name=deck["name"])
            for deck in self.decks.values()
        ]

    def by_name(self, name: str) -> dict[str, Any] | None:
        for deck in self.decks.values():
            if deck["name"] == name:
                return deck
        return None

    def id(self, name: str) -> int:
        existing = self.by_name(name)
        if existing is not None:
            return int(existing["id"])

        deck_id = max(self.decks) + 1
        self.decks[deck_id] = {"id": deck_id, "name": name}
        return deck_id

    def get(self, deck_id: int) -> dict[str, Any] | None:
        return self.decks.get(deck_id)

    def save(self, deck: dict[str, Any]) -> None:
        self.saved.append(dict(deck))
        self.decks[int(deck["id"])] = dict(deck)


class FakeCollection:
    def __init__(self) -> None:
        self.decks = FakeDecks()
        first_note = FakeNote(
            201,
            {"Front": "Capital of France?", "Back": "Paris"},
            ["geography"],
        )
        second_note = FakeNote(202, {"Front": "2 + 2", "Back": "4"})
        self.cards = {
            101: FakeCard(101, first_note, 1),
            102: FakeCard(102, second_note, 2),
        }
        self.updated_notes: list[FakeNote] = []
        self.updated_cards: list[FakeCard] = []

    def card_count(self) -> int:
        return len(self.cards)

    def find_cards(self, query: str) -> list[int]:
        if query.startswith('deck:"') and query.endswith('"'):
            deck_name = query[len('deck:"') : -1].replace('\\"', '"')
            deck = self.decks.by_name(deck_name)
            if deck is None:
                return []
            deck_id = int(deck["id"])
            return [
                card_id
                for card_id, card in self.cards.items()
                if card.did == deck_id
            ]

        if query == "deck:Default":
            return [101]

        if query == "all":
            return list(self.cards)

        return []

    def get_card(self, card_id: int) -> FakeCard | None:
        return self.cards.get(card_id)

    def update_note(self, note: FakeNote) -> None:
        self.updated_notes.append(note)

    def update_card(self, card: FakeCard) -> None:
        self.updated_cards.append(card)
