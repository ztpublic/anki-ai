ADDON_PACKAGE := anki_ai
FRONTEND_DIR := frontend
DIST_DIR := dist
ADDON_ARCHIVE := $(DIST_DIR)/$(ADDON_PACKAGE).ankiaddon
VENDOR_DIR := $(ADDON_PACKAGE)/vendor
RUNTIME_DEPS := claude-agent-sdk jinja2 markitdown[all]
ANKI_PYTHON := $(HOME)/Library/Application Support/AnkiProgramFiles/.venv/bin/python
VENDOR_PYTHON ?= python

.PHONY: build frontend-build typecheck vendor-python package clean

build: package

typecheck:
	python -m mypy $(ADDON_PACKAGE)

frontend-build:
	npm --prefix $(FRONTEND_DIR) run build

vendor-python:
	rm -rf $(VENDOR_DIR)
	if [ -x "$(ANKI_PYTHON)" ]; then \
		"$(ANKI_PYTHON)" -m pip install --upgrade --target $(VENDOR_DIR) $(RUNTIME_DEPS); \
	else \
		"$(VENDOR_PYTHON)" -m pip install --upgrade --target $(VENDOR_DIR) $(RUNTIME_DEPS); \
	fi
	find $(VENDOR_DIR) -type d -name __pycache__ -prune -exec rm -rf {} +
	find $(VENDOR_DIR) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

package: frontend-build vendor-python
	mkdir -p $(DIST_DIR)
	rm -f $(ADDON_ARCHIVE)
	cd $(ADDON_PACKAGE) && zip -r ../$(ADDON_ARCHIVE) . -x '__pycache__/' '__pycache__/*' '*/__pycache__/' '*/__pycache__/*' '*.pyc' '*.pyo' '.DS_Store'

clean:
	rm -rf $(DIST_DIR)
	rm -rf $(ADDON_PACKAGE)/web
	rm -rf $(VENDOR_DIR)
	find $(ADDON_PACKAGE) -type d -name __pycache__ -prune -exec rm -rf {} +
	find $(ADDON_PACKAGE) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
