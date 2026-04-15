"""Anki AI add-on entrypoint."""

from __future__ import annotations

MENU_ACTION_LABEL = "Anki AI"


def setup_menu() -> None:
    """Register the add-on action in Anki's Tools menu."""
    from aqt import mw
    from aqt.qt import QAction
    from aqt.utils import qconnect

    from .gui import open_generator_dialog

    mw.addonManager.setWebExports(__name__, r"web/.*")

    action = QAction(MENU_ACTION_LABEL, mw)
    qconnect(action.triggered, open_generator_dialog)
    mw.form.menuTools.addAction(action)


try:
    import aqt as _aqt  # noqa: F401
except ModuleNotFoundError as error:
    if error.name != "aqt":
        raise
else:
    setup_menu()
