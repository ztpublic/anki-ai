"""Service helpers for reading and updating Anki collection data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from typing import Any, TypedDict, cast


class DeckSnapshot(TypedDict):
    id: str
    name: str
    cardCount: int | None


class CardSnapshot(TypedDict):
    id: str
    noteId: str
    deckId: str
    question: str
    answer: str
    fields: dict[str, str]
    tags: list[str]
    state: dict[str, Any]


class CollectionSnapshot(TypedDict):
    available: bool
    cardCount: int | None
    deckCount: int
    decks: list[DeckSnapshot]


class CollectionServiceError(Exception):
    """A domain error that can be safely surfaced to bridge callers."""

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


class AnkiCollectionService:
    """Read/write adapter around the active Anki collection.

    The service intentionally avoids importing Anki modules so tests can run
    without Anki installed. Runtime integration is structural: the provided
    collection only needs the methods used here.
    """

    DEFAULT_CARD_SEARCH_LIMIT = 50
    MAX_CARD_SEARCH_LIMIT = 500

    def __init__(self, collection: Any) -> None:
        self._collection = collection

    def collection_snapshot(
        self,
        *,
        include_card_counts: bool = True,
    ) -> CollectionSnapshot:
        decks = self.list_decks(include_card_counts=include_card_counts)
        return {
            "available": True,
            "cardCount": self.card_count(),
            "deckCount": len(decks),
            "decks": decks,
        }

    def card_count(self) -> int | None:
        card_count = getattr(self._collection, "card_count", None)
        if callable(card_count):
            return self._coerce_int(card_count(), "card_count")

        return None

    def list_decks(self, *, include_card_counts: bool = False) -> list[DeckSnapshot]:
        deck_manager = self._deck_manager()

        all_names_and_ids = getattr(deck_manager, "all_names_and_ids", None)
        if callable(all_names_and_ids):
            return sorted(
                [
                    self._deck_snapshot_from_record(
                        record,
                        include_card_counts=include_card_counts,
                    )
                    for record in all_names_and_ids()
                ],
                key=lambda deck: deck["name"].lower(),
            )

        all_decks = getattr(deck_manager, "all", None)
        if callable(all_decks):
            return sorted(
                [
                    self._deck_snapshot_from_mapping(
                        self._require_mapping(record, "deck"),
                        include_card_counts=include_card_counts,
                    )
                    for record in all_decks()
                ],
                key=lambda deck: deck["name"].lower(),
            )

        raise CollectionServiceError(
            "unsupported_deck_api",
            "The active Anki collection does not expose a supported deck API.",
        )

    def get_deck(
        self,
        deck_id: int,
        *,
        include_card_counts: bool = False,
    ) -> DeckSnapshot:
        deck_manager = self._deck_manager()
        get_deck = getattr(deck_manager, "get", None)
        if not callable(get_deck):
            raise CollectionServiceError(
                "unsupported_deck_api",
                "The active Anki collection cannot fetch decks by id.",
            )

        deck = get_deck(deck_id)
        if deck is None:
            raise CollectionServiceError(
                "deck_not_found",
                f"Deck not found: {deck_id}",
                {"deckId": str(deck_id)},
            )

        return self._deck_snapshot_from_mapping(
            self._require_mapping(deck, "deck"),
            include_card_counts=include_card_counts,
        )

    def get_deck_by_name(
        self,
        name: str,
        *,
        include_card_counts: bool = False,
    ) -> DeckSnapshot | None:
        deck_manager = self._deck_manager()
        by_name = getattr(deck_manager, "by_name", None)
        if callable(by_name):
            deck = by_name(name)
            if deck is not None:
                return self._deck_snapshot_from_mapping(
                    self._require_mapping(deck, "deck"),
                    include_card_counts=include_card_counts,
                )

        for deck in self.list_decks(include_card_counts=include_card_counts):
            if deck["name"] == name:
                return deck

        return None

    def ensure_deck(self, name: str) -> dict[str, Any]:
        existing = self.get_deck_by_name(name, include_card_counts=False)
        if existing is not None:
            return {"created": False, "deck": existing}

        deck_manager = self._deck_manager()
        deck_id_method = getattr(deck_manager, "id", None)
        if not callable(deck_id_method):
            raise CollectionServiceError(
                "unsupported_deck_api",
                "The active Anki collection cannot create decks.",
            )

        deck_id = self._coerce_int(deck_id_method(name), "deck_id")
        return {
            "created": True,
            "deck": self.get_deck(deck_id, include_card_counts=False),
        }

    def rename_deck(self, deck_id: int, name: str) -> DeckSnapshot:
        deck_manager = self._deck_manager()
        get_deck = getattr(deck_manager, "get", None)
        save_deck = getattr(deck_manager, "save", None)
        if not callable(get_deck) or not callable(save_deck):
            raise CollectionServiceError(
                "unsupported_deck_api",
                "The active Anki collection cannot rename decks.",
            )

        deck = get_deck(deck_id)
        if deck is None:
            raise CollectionServiceError(
                "deck_not_found",
                f"Deck not found: {deck_id}",
                {"deckId": str(deck_id)},
            )

        deck_mapping = self._require_mutable_mapping(deck, "deck")
        deck_mapping["name"] = name
        save_deck(deck_mapping)
        return self.get_deck(deck_id, include_card_counts=False)

    def find_cards(
        self,
        query: str,
        *,
        limit: int = DEFAULT_CARD_SEARCH_LIMIT,
    ) -> list[CardSnapshot]:
        normalized_limit = max(1, min(limit, self.MAX_CARD_SEARCH_LIMIT))
        find_cards = getattr(self._collection, "find_cards", None)
        if not callable(find_cards):
            raise CollectionServiceError(
                "unsupported_card_api",
                "The active Anki collection cannot search cards.",
            )

        raw_card_ids = find_cards(query)
        if not isinstance(raw_card_ids, Iterable):
            raise CollectionServiceError(
                "invalid_card_search_result",
                "Anki returned an invalid card search result.",
            )

        snapshots: list[CardSnapshot] = []
        for raw_card_id in raw_card_ids:
            snapshots.append(self.get_card(self._coerce_int(raw_card_id, "card_id")))
            if len(snapshots) >= normalized_limit:
                break

        return snapshots

    def get_card(self, card_id: int) -> CardSnapshot:
        card = self._get_card_object(card_id)
        note = self._note_for_card(card)
        return self._card_snapshot(card, note, fallback_card_id=card_id)

    def update_note_fields(
        self,
        card_id: int,
        fields: Mapping[str, str],
    ) -> CardSnapshot:
        card = self._get_card_object(card_id)
        note = self._note_for_card(card)
        existing_fields = self._note_fields(note)
        unknown_fields = sorted(set(fields) - set(existing_fields))
        if unknown_fields:
            raise CollectionServiceError(
                "unknown_note_field",
                "Cannot update note fields that are not present on the note.",
                {"fields": unknown_fields},
            )

        for field_name, value in fields.items():
            note[field_name] = value

        update_note = getattr(self._collection, "update_note", None)
        if not callable(update_note):
            raise CollectionServiceError(
                "unsupported_note_api",
                "The active Anki collection cannot update notes.",
            )

        update_note(note)
        return self.get_card(card_id)

    def move_cards_to_deck(
        self,
        card_ids: Sequence[int],
        *,
        deck_id: int | None = None,
        deck_name: str | None = None,
    ) -> dict[str, Any]:
        if deck_id is None:
            if deck_name is None:
                raise CollectionServiceError(
                    "missing_deck",
                    "Either deck_id or deck_name must be provided.",
                )
            deck_result = self.ensure_deck(deck_name)
            deck = cast(DeckSnapshot, deck_result["deck"])
            deck_id = self._coerce_int(deck["id"], "deck_id")
        else:
            deck = self.get_deck(deck_id, include_card_counts=False)

        update_card = getattr(self._collection, "update_card", None)
        if not callable(update_card):
            raise CollectionServiceError(
                "unsupported_card_api",
                "The active Anki collection cannot update cards.",
            )

        updated_card_ids: list[str] = []
        for card_id in card_ids:
            card = self._get_card_object(card_id)
            setattr(card, "did", deck_id)

            if getattr(card, "odid", 0):
                setattr(card, "odid", 0)
            if getattr(card, "odue", 0):
                setattr(card, "due", getattr(card, "odue"))
                setattr(card, "odue", 0)

            update_card(card)
            updated_card_ids.append(str(card_id))

        return {
            "deck": deck,
            "updatedCardIds": updated_card_ids,
        }

    def _deck_manager(self) -> Any:
        deck_manager = getattr(self._collection, "decks", None)
        if deck_manager is None:
            raise CollectionServiceError(
                "collection_unavailable",
                "The active Anki collection is not available.",
            )
        return deck_manager

    def _get_card_object(self, card_id: int) -> Any:
        get_card = getattr(self._collection, "get_card", None)
        if not callable(get_card):
            raise CollectionServiceError(
                "unsupported_card_api",
                "The active Anki collection cannot fetch cards by id.",
            )

        card = get_card(card_id)
        if card is None:
            raise CollectionServiceError(
                "card_not_found",
                f"Card not found: {card_id}",
                {"cardId": str(card_id)},
            )

        return card

    def _note_for_card(self, card: Any) -> Any:
        note_method = getattr(card, "note", None)
        if callable(note_method):
            return note_method()

        note_id = getattr(card, "nid", None)
        get_note = getattr(self._collection, "get_note", None)
        if note_id is not None and callable(get_note):
            note = get_note(note_id)
            if note is not None:
                return note

        raise CollectionServiceError(
            "note_not_found",
            "Could not resolve the note for the requested card.",
        )

    def _card_snapshot(
        self,
        card: Any,
        note: Any,
        *,
        fallback_card_id: int,
    ) -> CardSnapshot:
        note_id = getattr(note, "id", getattr(card, "nid", None))
        deck_id = getattr(card, "did", None)
        return {
            "id": str(getattr(card, "id", fallback_card_id)),
            "noteId": "" if note_id is None else str(note_id),
            "deckId": "" if deck_id is None else str(deck_id),
            "question": self._call_text_method(card, "question"),
            "answer": self._call_text_method(card, "answer"),
            "fields": self._note_fields(note),
            "tags": self._note_tags(note),
            "state": self._card_state(card),
        }

    def _note_fields(self, note: Any) -> dict[str, str]:
        items = getattr(note, "items", None)
        if not callable(items):
            raise CollectionServiceError(
                "unsupported_note_api",
                "The note does not expose editable fields.",
            )

        return {
            str(field_name): self._coerce_text(value)
            for field_name, value in items()
        }

    def _note_tags(self, note: Any) -> list[str]:
        tags = getattr(note, "tags", [])
        if not isinstance(tags, Iterable) or isinstance(tags, (str, bytes)):
            return []
        return [str(tag) for tag in tags]

    def _card_state(self, card: Any) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for attr_name, output_name in (
            ("queue", "queue"),
            ("type", "type"),
            ("due", "due"),
            ("ivl", "interval"),
            ("factor", "factor"),
            ("reps", "reps"),
            ("lapses", "lapses"),
            ("ord", "ordinal"),
        ):
            value = getattr(card, attr_name, None)
            if isinstance(value, (bool, int, float, str)):
                state[output_name] = value

        return state

    def _deck_snapshot_from_record(
        self,
        record: Any,
        *,
        include_card_counts: bool,
    ) -> DeckSnapshot:
        if isinstance(record, Mapping):
            return self._deck_snapshot_from_mapping(
                record,
                include_card_counts=include_card_counts,
            )

        deck_id = getattr(record, "id", None)
        name = getattr(record, "name", None)

        if deck_id is None or name is None:
            sequence_record = self._sequence_record(record)
            if sequence_record is not None and len(sequence_record) >= 2:
                first = sequence_record[0]
                second = sequence_record[1]
                if isinstance(first, str):
                    name = first
                    deck_id = second
                else:
                    deck_id = first
                    name = second

        return self._deck_snapshot(
            self._coerce_int(deck_id, "deck_id"),
            self._coerce_required_text(name, "deck_name"),
            include_card_counts=include_card_counts,
        )

    def _deck_snapshot_from_mapping(
        self,
        deck: Mapping[str, Any],
        *,
        include_card_counts: bool,
    ) -> DeckSnapshot:
        return self._deck_snapshot(
            self._coerce_int(deck.get("id"), "deck_id"),
            self._coerce_required_text(deck.get("name"), "deck_name"),
            include_card_counts=include_card_counts,
        )

    def _deck_snapshot(
        self,
        deck_id: int,
        name: str,
        *,
        include_card_counts: bool,
    ) -> DeckSnapshot:
        return {
            "id": str(deck_id),
            "name": name,
            "cardCount": self._deck_card_count(name) if include_card_counts else None,
        }

    def _deck_card_count(self, name: str) -> int | None:
        find_cards = getattr(self._collection, "find_cards", None)
        if not callable(find_cards):
            return None

        try:
            return len(find_cards(f'deck:"{self._escape_search_value(name)}"'))
        except Exception:
            return None

    @staticmethod
    def _escape_search_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _call_text_method(target: Any, method_name: str) -> str:
        method = getattr(target, method_name, None)
        if not callable(method):
            return ""
        return AnkiCollectionService._coerce_text(method())

    @staticmethod
    def _coerce_int(value: Any, label: str) -> int:
        if isinstance(value, bool):
            raise CollectionServiceError(
                "invalid_id",
                f"{label} must be an integer.",
                {label: value},
            )
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as error:
                raise CollectionServiceError(
                    "invalid_id",
                    f"{label} must be an integer.",
                    {label: value},
                ) from error

        raise CollectionServiceError(
            "invalid_id",
            f"{label} must be an integer.",
            {label: value},
        )

    @staticmethod
    def _coerce_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _coerce_required_text(value: Any, label: str) -> str:
        text = AnkiCollectionService._coerce_text(value).strip()
        if not text:
            raise CollectionServiceError(
                "invalid_text",
                f"{label} must be a non-empty string.",
                {label: value},
            )
        return text

    @staticmethod
    def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise CollectionServiceError(
                "invalid_collection_object",
                f"{label} must be a mapping.",
            )
        return cast(Mapping[str, Any], value)

    @staticmethod
    def _require_mutable_mapping(value: Any, label: str) -> MutableMapping[str, Any]:
        if not isinstance(value, MutableMapping):
            raise CollectionServiceError(
                "invalid_collection_object",
                f"{label} must be a mutable mapping.",
            )
        return cast(MutableMapping[str, Any], value)

    @staticmethod
    def _sequence_record(value: Any) -> Sequence[Any] | None:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return cast(Sequence[Any], value)
        return None
