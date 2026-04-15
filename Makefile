ADDON_PACKAGE := anki_ai
FRONTEND_DIR := frontend
DIST_DIR := dist
ADDON_ARCHIVE := $(DIST_DIR)/$(ADDON_PACKAGE).ankiaddon

.PHONY: frontend-build typecheck package clean

typecheck:
	python -m mypy $(ADDON_PACKAGE)

frontend-build:
	npm --prefix $(FRONTEND_DIR) run build

package: frontend-build
	mkdir -p $(DIST_DIR)
	rm -f $(ADDON_ARCHIVE)
	cd $(ADDON_PACKAGE) && zip -r ../$(ADDON_ARCHIVE) . -x '__pycache__/' '__pycache__/*' '*/__pycache__/' '*/__pycache__/*' '*.pyc' '*.pyo' '.DS_Store'

clean:
	rm -rf $(DIST_DIR)
	rm -rf $(ADDON_PACKAGE)/web
	find $(ADDON_PACKAGE) -type d -name __pycache__ -prune -exec rm -rf {} +
	find $(ADDON_PACKAGE) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
