from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeNote:
    def __init__(
        self,
        note_id: int,
        fields: dict[str, str],
        tags: list[str] | None = None,
        note_type: dict[str, Any] | None = None,
    ) -> None:
        self.id = note_id
        self.fields = fields
        self.tags = [] if tags is None else tags
        self.note_type = note_type

    def items(self) -> list[tuple[str, str]]:
        return list(self.fields.items())

    def __getitem__(self, key: str) -> str:
        return self.fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value

    def fields_check(self) -> int:
        first_field = next(iter(self.fields.values()), "")
        return 1 if not first_field.strip() else 0


class FakeModels:
    def __init__(self) -> None:
        self.note_types: dict[int, dict[str, Any]] = {
            1001: {
                "id": 1001,
                "name": "Basic",
                "flds": [{"name": "Front"}, {"name": "Back"}],
            }
        }

    def by_name(self, name: str) -> dict[str, Any] | None:
        for note_type in self.note_types.values():
            if note_type["name"] == name:
                return note_type
        return None

    def get(self, note_type_id: int) -> dict[str, Any] | None:
        return self.note_types.get(note_type_id)


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
        if "Front" in self._note.fields:
            return self._note.fields.get("Front", "")
        values = list(self._note.fields.values())
        return values[0] if values else ""

    def answer(self) -> str:
        if "Back" in self._note.fields:
            return self._note.fields.get("Back", "")
        values = list(self._note.fields.values())
        return values[1] if len(values) > 1 else ""


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
        self.models = FakeModels()
        basic_note_type = self.models.by_name("Basic")
        assert basic_note_type is not None
        first_note = FakeNote(
            201,
            {"Front": "Capital of France?", "Back": "Paris"},
            ["geography"],
            basic_note_type,
        )
        second_note = FakeNote(202, {"Front": "2 + 2", "Back": "4"}, note_type=basic_note_type)
        self.notes = {
            201: first_note,
            202: second_note,
        }
        self.cards = {
            101: FakeCard(101, first_note, 1),
            102: FakeCard(102, second_note, 2),
        }
        self.updated_notes: list[FakeNote] = []
        self.updated_cards: list[FakeCard] = []
        self.next_note_id = 203
        self.next_card_id = 103

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

    def get_note(self, note_id: int) -> FakeNote | None:
        return self.notes.get(note_id)

    def new_note(self, note_type: dict[str, Any]) -> FakeNote:
        field_values = {
            str(field["name"]): ""
            for field in note_type.get("flds", [])
        }
        return FakeNote(0, field_values, note_type=note_type)

    def update_note(self, note: FakeNote) -> None:
        self.updated_notes.append(note)
        self.notes[note.id] = note

    def update_card(self, card: FakeCard) -> None:
        self.updated_cards.append(card)

    def add_note(self, note: FakeNote, deck_id: int) -> SimpleNamespace:
        if note.id == 0:
            note.id = self.next_note_id
            self.next_note_id += 1
        self.notes[note.id] = note

        card = FakeCard(self.next_card_id, note, deck_id)
        self.cards[self.next_card_id] = card
        self.next_card_id += 1
        return SimpleNamespace(count=1, note_id=note.id)

    def add_notes(self, requests: list[Any]) -> SimpleNamespace:
        note_ids: list[int] = []
        for request in requests:
            response = self.add_note(request.note, request.deck_id)
            note_ids.append(int(response.note_id))
        return SimpleNamespace(nids=note_ids)

    def card_ids_of_note(self, note_id: int) -> list[int]:
        return sorted(
            card_id for card_id, card in self.cards.items() if card.nid == note_id
        )
