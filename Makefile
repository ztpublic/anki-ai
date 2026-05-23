ADDON_PACKAGE := anki_ai
FRONTEND_DIR := frontend
DIST_DIR := dist
ADDON_ARCHIVE := $(DIST_DIR)/$(ADDON_PACKAGE).ankiaddon
VENDOR_DIR := $(ADDON_PACKAGE)/vendor
ZIP_FLAGS ?= -rq
VENDOR_STAMP := $(VENDOR_DIR)/.vendor-python.stamp
VENDOR_REQUEST := $(VENDOR_DIR)/.vendor-python.request
FRONTEND_STAMP := $(ADDON_PACKAGE)/web/.frontend-build.stamp
VENDOR_MARKITDOWN_EXTRAS ?= pdf,docx,pptx,xlsx,xls,youtube-transcription
VENDOR_INCLUDE_CLAUDE_CLI ?= 0
RUNTIME_DEPS := claude-agent-sdk openai-codex@git+https://github.com/openai/codex.git\#subdirectory=sdk/python jinja2 markitdown[$(VENDOR_MARKITDOWN_EXTRAS)] markdown-it-py mdit-py-plugins nh3
ANKI_PYTHON := $(HOME)/Library/Application Support/AnkiProgramFiles/.venv/bin/python
VENDOR_PYTHON ?= python
FRONTEND_SOURCES := $(shell find $(FRONTEND_DIR)/src $(FRONTEND_DIR)/index.html $(FRONTEND_DIR)/vite.config.ts $(FRONTEND_DIR)/package.json $(FRONTEND_DIR)/package-lock.json -type f 2>/dev/null)
ADDON_SOURCES := $(shell find $(ADDON_PACKAGE) -type f \( -path '$(VENDOR_DIR)/*' -o -path '$(ADDON_PACKAGE)/web/*' -o -path '*/__pycache__/*' \) -prune -o -type f -print 2>/dev/null)

.PHONY: build frontend-build typecheck vendor-python vendor-python-refresh package clean

build: package

typecheck:
	python -m mypy $(ADDON_PACKAGE)

frontend-build: $(FRONTEND_STAMP)

$(FRONTEND_STAMP): $(FRONTEND_SOURCES)
	npm --prefix $(FRONTEND_DIR) run build
	touch $(FRONTEND_STAMP)

vendor-python: $(VENDOR_STAMP)

vendor-python-refresh:
	rm -rf $(VENDOR_DIR)
	$(MAKE) vendor-python

$(VENDOR_STAMP): Makefile pyproject.toml
	@set -eu; \
	request='deps=$(RUNTIME_DEPS);include_claude_cli=$(VENDOR_INCLUDE_CLAUDE_CLI);prune=2'; \
	if [ -d "$(VENDOR_DIR)" ] && [ -f "$(VENDOR_REQUEST)" ] && [ "$$(cat "$(VENDOR_REQUEST)")" = "$$request" ]; then \
		echo "Python vendor dependencies are up to date."; \
	else \
		rm -rf $(VENDOR_DIR); \
		mkdir -p $(VENDOR_DIR); \
		if [ -x "$(ANKI_PYTHON)" ]; then \
			"$(ANKI_PYTHON)" -m pip install --upgrade --no-compile --target $(VENDOR_DIR) $(RUNTIME_DEPS); \
		else \
			"$(VENDOR_PYTHON)" -m pip install --upgrade --no-compile --target $(VENDOR_DIR) $(RUNTIME_DEPS); \
		fi; \
		find $(VENDOR_DIR) -type d -name __pycache__ -prune -exec rm -rf {} +; \
		find $(VENDOR_DIR) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete; \
		find $(VENDOR_DIR) -type d \( -name tests -o -name test \) -prune -exec rm -rf {} +; \
		rm -rf $(VENDOR_DIR)/bin; \
		if [ "$(VENDOR_INCLUDE_CLAUDE_CLI)" != "1" ]; then \
			rm -rf $(VENDOR_DIR)/claude_agent_sdk/_bundled; \
		fi; \
		printf '%s' "$$request" > $(VENDOR_REQUEST); \
	fi
	touch $(VENDOR_STAMP)

$(ADDON_ARCHIVE): $(FRONTEND_STAMP) $(VENDOR_STAMP) $(ADDON_SOURCES)
	mkdir -p $(DIST_DIR)
	rm -f $(ADDON_ARCHIVE)
	cd $(ADDON_PACKAGE) && zip $(ZIP_FLAGS) ../$(ADDON_ARCHIVE) . -x '__pycache__/' '__pycache__/*' '*/__pycache__/' '*/__pycache__/*' '*.pyc' '*.pyo' '.DS_Store'

package: $(ADDON_ARCHIVE)

clean:
	rm -rf $(DIST_DIR)
	rm -rf $(ADDON_PACKAGE)/web
	rm -rf $(VENDOR_DIR)
	find $(ADDON_PACKAGE) -type d -name __pycache__ -prune -exec rm -rf {} +
	find $(ADDON_PACKAGE) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
