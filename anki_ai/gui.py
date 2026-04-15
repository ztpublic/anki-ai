"""Custom Anki AI generator dialog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aqt import mw
from aqt.qt import QCloseEvent, QDialog, QVBoxLayout, Qt
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView

GEOMETRY_KEY = "anki_ai_generator"
WINDOW_TITLE = "Anki AI"

_dialog: GeneratorDialog | None = None


def _addon_web_base_url() -> str:
    addon_package = quote(mw.addonManager.addonFromModule(__name__))
    return f"{mw.serverURL()}_addons/{addon_package}/web/"


def _frontend_html() -> str:
    index_path = Path(__file__).with_name("web") / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except OSError:
        return """
<!doctype html>
<html>
<body>
<main style="font: 16px sans-serif; padding: 24px;">
Frontend assets are missing. Run <code>make frontend-build</code>.
</main>
</body>
</html>
"""

    base_url = _addon_web_base_url()
    return html.replace('src="./', f'src="{base_url}').replace(
        'href="./', f'href="{base_url}'
    )


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

        self.web.setHtml(_frontend_html())

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
