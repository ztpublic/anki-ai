from __future__ import annotations

import json
import unittest
from typing import Any

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


class FakeWeb:
    def __init__(self) -> None:
        self.evaluated_js: list[str] = []

    def eval(self, js: str) -> None:
        self.evaluated_js.append(js)


class TransportRouterTest(unittest.TestCase):
    def test_ping_returns_success_response(self) -> None:
        router = TransportRouter()

        response = router.handle_raw_message(request_message("system.ping"))

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["protocol"], PROTOCOL)
        self.assertEqual(response["kind"], "response")
        self.assertEqual(response["id"], "req-1")
        self.assertIs(response["ok"], True)
        self.assertEqual(response["result"], {"pong": True})

    def test_invalid_json_returns_transport_error(self) -> None:
        router = TransportRouter()

        response = router.handle_raw_message("{")

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIs(response["ok"], False)
        self.assertEqual(response["id"], None)
        self.assertEqual(response["error"]["code"], "invalid_json")

    def test_unknown_method_returns_transport_error(self) -> None:
        router = TransportRouter()

        response = router.handle_raw_message(request_message("missing.method"))

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIs(response["ok"], False)
        self.assertEqual(response["id"], "req-1")
        self.assertEqual(response["error"]["code"], "unknown_method")

    def test_handler_exception_is_normalized(self) -> None:
        router = TransportRouter()

        def explode(params: JsonObject) -> Any:
            raise RuntimeError("boom")

        router.register("test.explode", explode)

        response = router.handle_raw_message(request_message("test.explode"))

        self.assertIsNotNone(response)
        assert response is not None
        self.assertIs(response["ok"], False)
        self.assertEqual(response["error"]["code"], "internal_error")
        self.assertEqual(response["error"]["details"], "boom")

    def test_notification_dispatches_without_response(self) -> None:
        router = TransportRouter()
        calls: list[JsonObject] = []

        router.register("test.note", calls.append)

        response = router.handle_raw_message(
            json.dumps(
                {
                    "protocol": PROTOCOL,
                    "kind": "notification",
                    "method": "test.note",
                    "params": {"value": 1},
                }
            )
        )

        self.assertIsNone(response)
        self.assertEqual(calls, [{"value": 1}])

    def test_emit_sends_event_to_window_receiver(self) -> None:
        web = FakeWeb()
        router = TransportRouter(web)

        router.emit("status.changed", {"status": "ready"})

        self.assertEqual(len(web.evaluated_js), 1)
        js = web.evaluated_js[0]
        prefix = "window.AnkiAI && window.AnkiAI.receive("
        suffix = ");"
        self.assertTrue(js.startswith(prefix))
        self.assertTrue(js.endswith(suffix))

        message = json.loads(js[len(prefix) : -len(suffix)])
        self.assertEqual(
            message,
            {
                "protocol": PROTOCOL,
                "kind": "event",
                "event": "status.changed",
                "payload": {"status": "ready"},
            },
        )


if __name__ == "__main__":
    unittest.main()
