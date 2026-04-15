"""Basic Anki add-on entrypoint."""

from __future__ import annotations

from aqt import mw
from aqt.qt import QAction
from aqt.utils import qconnect, showInfo

MENU_ACTION_LABEL = "Anki AI: Test"


def show_card_count() -> None:
    """Show the number of cards in the current Anki collection."""
    if mw.col is None:
        showInfo("No collection is currently open.")
        return

    card_count = mw.col.card_count()
    showInfo(f"Card count: {card_count}")


def setup_menu() -> None:
    """Register the add-on action in Anki's Tools menu."""
    action = QAction(MENU_ACTION_LABEL, mw)
    qconnect(action.triggered, show_card_count)
    mw.form.menuTools.addAction(action)


setup_menu()
