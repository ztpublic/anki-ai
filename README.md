# Anki AI Add-on

Anki AI is an Anki add-on that hosts a React-based flashcard generation
interface inside an Anki webview. The add-on currently provides the UI shell,
frontend build pipeline, Anki dialog integration, and a typed JSON bridge between
the web UI and Python backend.

The actual AI generation flow is not implemented yet. The current frontend
still simulates generated cards, but reviewed cards can now be inserted into
the active Anki collection through the webview bridge.

## Current State

- Registers a `Tools > Anki AI` menu item when loaded inside Anki.
- Opens a non-modal `AnkiWebView` dialog and restores its previous geometry.
- Builds the React app with Vite into `anki_ai/web/`, which is ignored by git and
  generated locally.
- Provides a JSON webview transport protocol in `anki_ai/transport.py`, with
  `system.ping` as the base connectivity check.
- Provides collection service infrastructure for reading deck/card snapshots,
  checking collection availability, creating/renaming decks, inserting notes as
  cards in batch, updating note fields, and moving cards between decks.
- Installs a `window.AnkiAI` frontend bridge with request, notification, and
  event helpers.
- Presents a flashcard generator UI with source text input, optional file
  selection, model selection, target deck selection, card count, simulated
  generation, and card review/edit/discard controls.
- Loads target decks from the active Anki collection through the webview bridge.
- Saves reviewed cards into the selected Anki deck with the stock `Basic`
  note type by default.

## Repository Layout

```text
anki_ai/              Anki add-on package loaded by Anki
anki_ai/gui.py        Dialog and webview host
anki_ai/collection_services.py
                      Deck, card, note, and collection service adapter
anki_ai/collection_transport.py
                      Bridge method registration for collection services
anki_ai/transport.py  JSON bridge router used by the webview
frontend/             React, TypeScript, Tailwind, and Vite frontend
tests/                Python unit tests for the transport layer
docs/addon-docs/      Local copy of Anki add-on documentation
Makefile              Build, typecheck, package, and clean targets
```

Generated paths:

```text
anki_ai/web/          Vite build output consumed by the add-on
dist/                 Packaged .ankiaddon archive output
frontend/node_modules/
```

## Requirements

- Python 3.9 or newer.
- Anki 24 or newer for local `aqt` development/type-checking support.
- Node.js and npm for the React frontend.
- `make` and `zip` for the included build/package targets.

## Local Development

Create a Python environment and install development dependencies:

```shell
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Install frontend dependencies:

```shell
npm install --prefix frontend
```

Run checks:

```shell
make typecheck
python -m unittest
npm --prefix frontend run typecheck
```

Build the frontend assets into the add-on package:

```shell
make frontend-build
```

For frontend-only iteration in a browser, you can run:

```shell
npm --prefix frontend run dev
```

The browser dev server does not run inside Anki, so Anki-only bridge behavior
must still be tested from the add-on dialog.

## Webview Bridge Methods

The Python backend currently registers these bridge methods:

```text
system.ping
anki.collection.status
anki.collection.snapshot
anki.decks.list
anki.decks.ensure
anki.decks.rename
anki.cards.search
anki.cards.get
anki.cards.addToDeck
anki.cards.updateNoteFields
anki.cards.moveToDeck
```

The React UI currently calls `anki.decks.list` to populate the target deck
selector, and `anki.cards.addToDeck` to persist reviewed generated cards. The
remaining methods are available for wiring live card data into the webview and
sending reviewed card updates back to Anki.

## Batch Card Insert Format

Generated cards are inserted with `anki.cards.addToDeck`. The method creates one
note per payload entry, using the provided note type and destination deck.

Request:

```json
{
  "protocol": "anki-ai.transport.v1",
  "kind": "request",
  "id": "req-1",
  "method": "anki.cards.addToDeck",
  "params": {
    "deckId": "1",
    "noteTypeName": "Basic",
    "cards": [
      {
        "fields": {
          "Front": "What is the capital of France?",
          "Back": "Paris"
        },
        "tags": ["geography", "ai-generated"]
      },
      {
        "fields": {
          "Front": "2 + 2",
          "Back": "4"
        }
      }
    ]
  }
}
```

Rules:

- Provide either `deckId` or `deckName`.
- `noteTypeName` is optional and defaults to `Basic`.
- `noteTypeId` may be provided instead of `noteTypeName`.
- Each entry in `cards` must include a non-empty `fields` object.
- `fields` keys must exactly match the selected note type's field names.
- `tags` is optional and must be a list of strings when provided.

Response:

```json
{
  "protocol": "anki-ai.transport.v1",
  "kind": "response",
  "id": "req-1",
  "ok": true,
  "result": {
    "deck": {
      "id": "1",
      "name": "Default",
      "cardCount": null
    },
    "noteType": {
      "id": "1001",
      "name": "Basic",
      "fieldNames": ["Front", "Back"]
    },
    "cards": [
      {
        "id": "1234567890",
        "noteId": "1234567891",
        "deckId": "1",
        "question": "What is the capital of France?",
        "answer": "Paris",
        "fields": {
          "Front": "What is the capital of France?",
          "Back": "Paris"
        },
        "tags": ["geography", "ai-generated"],
        "state": {
          "queue": 0,
          "type": 0,
          "due": 1,
          "interval": 0,
          "factor": 2500,
          "reps": 0,
          "lapses": 0,
          "ordinal": 0
        }
      }
    ]
  }
}
```

## Install Into Anki

Build the frontend first:

```shell
make frontend-build
```

Find your Anki `addons21` folder with `Tools > Add-ons > View Files`, then copy
or symlink this repo's `anki_ai/` folder into it.

On macOS, the add-ons folder is commonly:

```shell
~/Library/Application Support/Anki2/addons21
```

Example symlink:

```shell
ln -s "$(pwd)/anki_ai" "$HOME/Library/Application Support/Anki2/addons21/anki_ai"
```

Restart Anki, then open `Tools > Anki AI`.

If the dialog says the frontend assets are missing, run `make frontend-build`
again and restart or reload the add-on.

## Package

Build a distributable add-on archive:

```shell
make package
```

The package target builds the React frontend first, then writes
`dist/anki_ai.ankiaddon`. The archive contents are rooted at the add-on files
themselves, as required by Anki, rather than inside an extra `anki_ai/` parent
directory.

## Configuration

The add-on includes Anki configuration files:

- `anki_ai/config.json` currently contains `{"enabled": true}`.
- `anki_ai/config.md` documents that setting.

The setting is present for future behavior gates. The current add-on still
registers its menu item regardless of this value.

## Known Gaps

- No LLM provider integration is wired up yet.
- Uploaded files are selected in the UI but not parsed.
- Generated cards are simulated, not produced by a backend model.
