"""Transport handlers for Anki collection deck/card services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from .collection_services import AnkiCollectionService, CollectionServiceError
from .transport import JsonObject, TransportError, TransportRouter

CollectionProvider = Callable[[], Any | None]


def register_collection_transport_handlers(
    router: TransportRouter,
    collection_provider: CollectionProvider,
) -> None:
    """Register collection-backed bridge methods on a transport router."""
    handlers = CollectionTransportHandlers(collection_provider)

    router.register("anki.collection.status", handlers.collection_status)
    router.register("anki.collection.snapshot", handlers.collection_snapshot)
    router.register("anki.decks.list", handlers.list_decks)
    router.register("anki.decks.ensure", handlers.ensure_deck)
    router.register("anki.decks.rename", handlers.rename_deck)
    router.register("anki.cards.search", handlers.search_cards)
    router.register("anki.cards.get", handlers.get_card)
    router.register("anki.cards.updateNoteFields", handlers.update_note_fields)
    router.register("anki.cards.moveToDeck", handlers.move_cards_to_deck)


class CollectionTransportHandlers:
    """Bridge-facing wrappers around AnkiCollectionService."""

    def __init__(self, collection_provider: CollectionProvider) -> None:
        self._collection_provider = collection_provider

    def collection_status(self, params: JsonObject) -> JsonObject:
        collection = self._collection_provider()
        if collection is None:
            return {
                "available": False,
                "cardCount": None,
                "deckCount": 0,
            }

        return self._run(
            lambda service: {
                "available": True,
                "cardCount": service.card_count(),
                "deckCount": len(service.list_decks(include_card_counts=False)),
            }
        )

    def collection_snapshot(self, params: JsonObject) -> JsonObject:
        include_card_counts = _optional_bool(params, "includeCardCounts", True)
        return self._run(
            lambda service: service.collection_snapshot(
                include_card_counts=include_card_counts,
            )
        )

    def list_decks(self, params: JsonObject) -> JsonObject:
        include_card_counts = _optional_bool(params, "includeCardCounts", False)
        return self._run(
            lambda service: {
                "decks": service.list_decks(include_card_counts=include_card_counts)
            }
        )

    def ensure_deck(self, params: JsonObject) -> JsonObject:
        deck_name = _required_string(params, "name")
        return self._run(lambda service: service.ensure_deck(deck_name))

    def rename_deck(self, params: JsonObject) -> JsonObject:
        deck_id = _required_id(params, "deckId")
        deck_name = _required_string(params, "name")
        return self._run(
            lambda service: {"deck": service.rename_deck(deck_id, deck_name)}
        )

    def search_cards(self, params: JsonObject) -> JsonObject:
        query = _required_string(params, "query")
        limit = _optional_int(
            params,
            "limit",
            AnkiCollectionService.DEFAULT_CARD_SEARCH_LIMIT,
            minimum=1,
            maximum=AnkiCollectionService.MAX_CARD_SEARCH_LIMIT,
        )
        return self._run(
            lambda service: {"cards": service.find_cards(query, limit=limit)}
        )

    def get_card(self, params: JsonObject) -> JsonObject:
        card_id = _required_id(params, "cardId")
        return self._run(lambda service: {"card": service.get_card(card_id)})

    def update_note_fields(self, params: JsonObject) -> JsonObject:
        card_id = _required_id(params, "cardId")
        fields = _required_string_mapping(params, "fields")
        return self._run(
            lambda service: {
                "card": service.update_note_fields(card_id, fields),
            }
        )

    def move_cards_to_deck(self, params: JsonObject) -> JsonObject:
        card_ids = _required_id_sequence(params, "cardIds")
        deck_id = _optional_id(params, "deckId")
        deck_name = _optional_string(params, "deckName")
        if deck_id is None and deck_name is None:
            raise TransportError(
                "invalid_params",
                "Either deckId or deckName must be provided.",
            )

        return self._run(
            lambda service: service.move_cards_to_deck(
                card_ids,
                deck_id=deck_id,
                deck_name=deck_name,
            )
        )

    def _service(self) -> AnkiCollectionService:
        collection = self._collection_provider()
        if collection is None:
            raise TransportError(
                "collection_unavailable",
                "Anki collection is not available.",
            )
        return AnkiCollectionService(collection)

    def _run(self, callback: Callable[[AnkiCollectionService], Any]) -> JsonObject:
        try:
            result = callback(self._service())
        except CollectionServiceError as error:
            raise TransportError(error.code, error.message, error.details) from error

        if not isinstance(result, dict):
            raise TransportError(
                "invalid_service_result",
                "Collection service returned a non-object payload.",
            )
        return cast(JsonObject, result)


def _required_string(params: JsonObject, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty string.",
        )
    return value.strip()


def _optional_string(params: JsonObject, key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty string when provided.",
        )
    return value.strip()


def _optional_bool(params: JsonObject, key: str, default: bool) -> bool:
    value = params.get(key, default)
    if not isinstance(value, bool):
        raise TransportError(
            "invalid_params",
            f"{key} must be a boolean.",
        )
    return value


def _optional_int(
    params: JsonObject,
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TransportError(
            "invalid_params",
            f"{key} must be an integer.",
        )

    if value < minimum or value > maximum:
        raise TransportError(
            "invalid_params",
            f"{key} must be between {minimum} and {maximum}.",
        )

    return value


def _required_id(params: JsonObject, key: str) -> int:
    if key not in params:
        raise TransportError(
            "invalid_params",
            f"{key} is required.",
        )
    return _coerce_id(params[key], key)


def _optional_id(params: JsonObject, key: str) -> int | None:
    if key not in params or params[key] is None:
        return None
    return _coerce_id(params[key], key)


def _coerce_id(value: Any, key: str) -> int:
    if isinstance(value, bool):
        raise TransportError(
            "invalid_params",
            f"{key} must be an integer id.",
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value:
        try:
            return int(value)
        except ValueError as error:
            raise TransportError(
                "invalid_params",
                f"{key} must be an integer id.",
            ) from error

    raise TransportError(
        "invalid_params",
        f"{key} must be an integer id.",
    )


def _required_id_sequence(params: JsonObject, key: str) -> list[int]:
    value = params.get(key)
    if not isinstance(value, list) or not value:
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty list of ids.",
        )
    return [_coerce_id(item, key) for item in value]


def _required_string_mapping(params: JsonObject, key: str) -> Mapping[str, str]:
    value = params.get(key)
    if not isinstance(value, dict) or not value:
        raise TransportError(
            "invalid_params",
            f"{key} must be a non-empty object.",
        )

    fields: dict[str, str] = {}
    for field_name, field_value in value.items():
        if not isinstance(field_name, str) or not field_name:
            raise TransportError(
                "invalid_params",
                f"{key} must have non-empty string keys.",
            )
        if not isinstance(field_value, str):
            raise TransportError(
                "invalid_params",
                f"{key}.{field_name} must be a string.",
            )
        fields[field_name] = field_value

    return fields
