"""JSON transport for the Anki AI webview bridge."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol, cast

PROTOCOL = "anki-ai.transport.v1"

JsonObject = dict[str, Any]
TransportHandler = Callable[[JsonObject], Any]


class WebEvaluator(Protocol):
    def eval(self, js: str) -> None:
        ...


class TransportError(Exception):
    """Error payload that can be returned over the transport."""

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

    def to_payload(self) -> JsonObject:
        payload: JsonObject = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


class TransportRouter:
    """Routes JSON bridge messages to named backend handlers."""

    def __init__(self, web: WebEvaluator | None = None) -> None:
        self._web = web
        self._handlers: dict[str, TransportHandler] = {}
        self.register("system.ping", self._handle_ping)

    def register(self, method: str, handler: TransportHandler) -> None:
        if not method:
            raise ValueError("Transport method name must not be empty.")

        self._handlers[method] = handler

    def handle_raw_message(self, raw_message: str) -> JsonObject | None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            return self._error_response(
                None,
                TransportError("invalid_json", "Bridge command must be valid JSON."),
            )

        if not isinstance(message, dict):
            return self._error_response(
                None,
                TransportError("invalid_message", "Bridge command must be an object."),
            )

        message = cast(JsonObject, message)
        request_id = self._message_id(message)

        if message.get("protocol") != PROTOCOL:
            return self._error_response(
                request_id,
                TransportError(
                    "invalid_protocol",
                    "Bridge command uses an unsupported protocol.",
                    {"expected": PROTOCOL},
                ),
            )

        kind = message.get("kind")
        if kind == "request":
            return self._handle_request(message)

        if kind == "notification":
            self._handle_notification(message)
            return None

        return self._error_response(
            request_id,
            TransportError(
                "invalid_kind",
                "Bridge command kind must be 'request' or 'notification'.",
            ),
        )

    def emit(self, event: str, payload: Any | None = None) -> None:
        if not event:
            raise ValueError("Transport event name must not be empty.")

        if self._web is None:
            raise RuntimeError("Cannot emit a transport event without a webview.")

        message: JsonObject = {
            "protocol": PROTOCOL,
            "kind": "event",
            "event": event,
            "payload": {} if payload is None else payload,
        }
        self._web.eval(
            f"window.AnkiAI && window.AnkiAI.receive({json.dumps(message)});"
        )

    def _handle_request(self, message: JsonObject) -> JsonObject:
        request_id = self._message_id(message)
        if request_id is None:
            return self._error_response(
                None,
                TransportError("invalid_request", "Bridge request id must be a string."),
            )

        try:
            result = self._dispatch(message)
        except TransportError as error:
            return self._error_response(request_id, error)
        except Exception as error:
            return self._error_response(
                request_id,
                TransportError("internal_error", "Transport handler failed.", str(error)),
            )

        return {
            "protocol": PROTOCOL,
            "kind": "response",
            "id": request_id,
            "ok": True,
            "result": result,
        }

    def _handle_notification(self, message: JsonObject) -> None:
        try:
            self._dispatch(message)
        except Exception as error:
            print(f"ignored failed transport notification: {error}")

    def _dispatch(self, message: JsonObject) -> Any:
        method = message.get("method")
        if not isinstance(method, str) or not method:
            raise TransportError(
                "invalid_method",
                "Bridge method must be a non-empty string.",
            )

        params = message.get("params", {})
        if not isinstance(params, dict):
            raise TransportError(
                "invalid_params",
                "Bridge params must be an object.",
            )

        handler = self._handlers.get(method)
        if handler is None:
            raise TransportError(
                "unknown_method",
                f"Unknown bridge method: {method}",
            )

        return handler(cast(JsonObject, params))

    def _handle_ping(self, params: JsonObject) -> JsonObject:
        return {"pong": True}

    @staticmethod
    def _message_id(message: JsonObject) -> str | None:
        request_id = message.get("id")
        if isinstance(request_id, str):
            return request_id

        return None

    @staticmethod
    def _error_response(
        request_id: str | None,
        error: TransportError,
    ) -> JsonObject:
        return {
            "protocol": PROTOCOL,
            "kind": "response",
            "id": request_id,
            "ok": False,
            "error": error.to_payload(),
        }
