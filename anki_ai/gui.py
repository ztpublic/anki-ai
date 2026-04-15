"""Custom Anki AI generator dialog."""

from __future__ import annotations

import json
from typing import Any

from aqt import mw
from aqt.qt import QCloseEvent, QDialog, QVBoxLayout, Qt
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView

GEOMETRY_KEY = "anki_ai_generator"
WINDOW_TITLE = "Anki AI"

_dialog: GeneratorDialog | None = None


def _addon_web_path(path: str) -> str:
    addon_package = mw.addonManager.addonFromModule(__name__)
    return f"/_addons/{addon_package}/web/{path}"


def open_generator_dialog() -> None:
    """Open the generator dialog, reusing an existing window when possible."""
    global _dialog

    if _dialog is not None and _dialog.isVisible():
        _dialog.raise_()
        _dialog.activateWindow()
        return

    _dialog = GeneratorDialog()


class GeneratorDialog(QDialog):
    """A non-modal dialog that hosts the React web UI."""

    DEFAULT_SIZE = (1000, 720)
    MIN_SIZE = (640, 480)

    def __init__(self) -> None:
        super().__init__(mw, Qt.WindowType.Window)
        self.web: AnkiWebView | None = None
        self._cleaned_up = False

        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumSize(*self.MIN_SIZE)
        disable_help_button(self)
        mw.garbage_collect_on_dialog_finish(self)
        restoreGeom(self, GEOMETRY_KEY, default_size=self.DEFAULT_SIZE)

        self._setup_ui()
        self.show()

    def _setup_ui(self) -> None:
        self.web = AnkiWebView(parent=self, title=WINDOW_TITLE)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        self.web.stdHtml(
            body='<div id="anki-ai-root"></div>',
            css=[_addon_web_path("app.css")],
            js=[
                _addon_web_path("vendor/react.production.min.js"),
                _addon_web_path("vendor/react-dom.production.min.js"),
                _addon_web_path("app.js"),
            ],
            context=self,
        )

    def _on_bridge_cmd(self, cmd: str) -> dict[str, Any]:
        try:
            message = json.loads(cmd)
        except json.JSONDecodeError:
            return {"ok": False, "error": "Invalid JSON bridge command."}

        if not isinstance(message, dict):
            return {"ok": False, "error": "Bridge command must be an object."}

        command_type = message.get("type")
        if command_type == "ping":
            return {"ok": True, "type": "pong"}

        return {"ok": False, "error": f"Unknown bridge command: {command_type}"}

    def _cleanup(self) -> None:
        global _dialog

        if self._cleaned_up:
            return

        self._cleaned_up = True
        saveGeom(self, GEOMETRY_KEY)

        if self.web is not None:
            self.web.cleanup()
            self.web = None

        if _dialog is self:
            _dialog = None

    def reject(self) -> None:
        self._cleanup()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cleanup()
        super().closeEvent(event)
