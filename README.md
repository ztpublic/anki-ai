# Anki AI Add-on

This repository contains a basic Anki add-on scaffold. The add-on package is `anki_ai/`.

## What It Does

The current add-on registers a `Tools > Anki AI: Test` menu item in Anki. Selecting it shows the number of cards in the currently open collection.

## Local Development

Create a Python environment and install development dependencies:

```shell
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run type checking:

```shell
make typecheck
```

Anki add-ons must run inside Anki. The local Python environment is only for editor support and static checks.

## Install Into Anki

Find your Anki `addons21` folder with `Tools > Add-ons > View Files`, then either copy or symlink this repo's `anki_ai/` folder into it.

On macOS, the add-ons folder is commonly:

```shell
~/Library/Application Support/Anki2/addons21
```

Example symlink:

```shell
ln -s "$(pwd)/anki_ai" "$HOME/Library/Application Support/Anki2/addons21/anki_ai"
```

Restart Anki after installing or changing the add-on.

## Package

Build a distributable add-on archive:

```shell
make package
```

The archive will be written to `dist/anki_ai.ankiaddon`. Its contents are rooted at the add-on files themselves, as required by Anki, rather than containing an extra `anki_ai/` parent directory.
