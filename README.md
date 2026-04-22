# Anki AI Add-on

Anki AI is an Anki add-on that hosts a React-based flashcard generation
interface inside an Anki webview. The add-on currently provides the UI shell,
frontend build pipeline, Anki dialog integration, and a typed JSON bridge between
the web UI and Python backend.

Reviewed cards can be inserted into the active Anki collection through the
webview bridge. Card generation now runs through a Claude Code task in a
temporary workspace that produces a `cards.json` file for the review UI.

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
- Provides a MarkItDown-backed file conversion service for converting attached
  documents, spreadsheets, notebooks, archives, media, and text files into
  markdown, including `pdf`, `docx`, `pptx`, `xlsx`, `xls`, `ipynb`, `epub`,
  `csv`, `zip`, `txt`, `md`, `json`, `html`, `xml`, `rss`, `atom`, `msg`,
  `jpg`, `jpeg`, `png`, `mp3`, `mp4`, `m4a`, and `wav`.
- Provides a Claude Code-backed generation workflow that prepares a temporary
  workspace, converts non-markdown attachments into markdown materials, and
  validates the generated `cards.json` output.
- Installs a `window.AnkiAI` frontend bridge with request, notification, and
  event helpers.
- Presents a flashcard generator UI with source text input, optional file
  selection, target deck selection, card count, live generation, and card
  review/edit/discard controls.
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
anki_ai/vendor/       Bundled Python runtime dependencies for Anki
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

Bundle Python runtime dependencies into the add-on package:

```shell
make vendor-python
```

This is required because Anki runs add-ons with its own Python environment and
does not install this repository's `pyproject.toml` dependencies automatically.
The generation backend loads `claude-agent-sdk` and `markitdown[all]` from
`anki_ai/vendor/` when present, then falls back to the repo `.venv` for local
symlink development.

Claude Code generation must also have Anthropic-compatible authentication
available to the Anki process. Anki launched from Finder or Spotlight usually
does not inherit shell environment variables, so a terminal setup that works for
`claude` may still be invisible to the add-on. For custom providers, set the
values under `generation` in Anki's add-on config or in an ignored
`anki_ai/config.local.json`, for example:

```json
{
  "generation": {
    "anthropicAuthToken": "",
    "anthropicBaseUrl": "https://api.example.com",
    "anthropicModel": "provider-model-name",
    "claudeCliPath": "/Users/you/.local/bin/claude"
  }
}
```

`anthropicAuthToken` maps to `ANTHROPIC_AUTH_TOKEN`; alternatively use
`anthropicApiKey` for `ANTHROPIC_API_KEY`. Leave secrets out of commits and set
them only in your local add-on configuration.

As a convenience for local development, the add-on also reads simple
`export KEY=value` or `KEY=value` assignments for the same keys from common shell
startup files such as `~/.zshrc`, `~/.zprofile`, and `~/.zshenv`. It does not
execute those files, so computed values or assignments hidden behind shell
conditionals should go in `config.local.json` instead.

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
anki.files.convertToMarkdown
anki.generation.generateCards
anki.generation.startGenerateCards
anki.cards.addToDeck
anki.cards.updateNoteFields
anki.cards.moveToDeck
```

The React UI currently calls `anki.decks.list` to populate the target deck
selector, `anki.generation.startGenerateCards` to run Claude Code card
generation with live log events, and `anki.cards.addToDeck` to persist reviewed
generated cards.

## Card Generation Format

Card generation runs in a temporary workspace. The backend prepares a
`materials/` directory, writes pasted text to `materials/user_input.txt`, copies
markdown attachments into the same directory, converts non-markdown attachments
to markdown files in that directory, runs Claude Code with that workspace as the
current directory, and expects a single `cards.json` file in the workspace root.
Pasted text is optional; if the user only attaches files, no `user_input.txt`
file is created.

Bridge request:

```json
{
  "protocol": "anki-ai.transport.v1",
  "kind": "request",
  "id": "req-1",
  "method": "anki.generation.generateCards",
  "params": {
    "sourceText": "Paste your study notes here",
    "cardCount": 5,
    "materials": [
      {
        "name": "chapter-1.md",
        "contentBase64": "IyBDaGFwdGVyIDEKLi4u"
      }
    ]
  }
}
```

Claude Code output contract:

```json
[
  {
    "Front": "Question text",
    "Back": "Answer text"
  }
]
```

Generation response:

```json
{
  "protocol": "anki-ai.transport.v1",
  "kind": "response",
  "id": "req-1",
  "ok": true,
  "result": {
    "cards": [
      {
        "id": "generated-1",
        "front": "Question text",
        "back": "Answer text"
      }
    ],
    "run": {
      "workspacePath": "/tmp/anki-ai-generation-abc123",
      "sessionId": "..."
    }
  }
}
```

Standalone generation script:

```shell
python scripts/generate_cards.py /path/to/material.pdf --card-count 10
```

The script accepts one local file path, copies it into the same Claude Code
`materials/` workspace used by the add-on, and writes a JSON array of
`{"Front", "Back"}` card objects to `/path/to/material.pdf.json`.

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

The package target builds the React frontend, vendors the Python runtime
dependencies, then writes `dist/anki_ai.ankiaddon`. The archive contents are
rooted at the add-on files themselves, as required by Anki, rather than inside an
extra `anki_ai/` parent directory.

## Configuration

The add-on includes Anki configuration files:

- `anki_ai/config.json` currently contains `{"enabled": true}`.
- `anki_ai/config.md` documents that setting.

The setting is present for future behavior gates. The current add-on still
registers its menu item regardless of this value.

## Known Gaps

- The Claude generation prompt is intentionally simple and will likely need iteration.
- Uploaded files are passed to Claude Code as workspace materials without any local preprocessing.
- Generation runs synchronously through the current bridge request path, so there is no cancel/resume flow yet.
