# Lancements des tests — uv uniquement, pas de pip ni de venv (cf. README).
# Les variables d'environnement viennent de .env ou du shell (cf. .env.example).
#
#   make test          API / caisse / DB, sans l'UI, sans écriture sous garde
#   make test-ui       tests navigateur (*_ui.py), Playwright
#   make ui-browsers   installe le Chromium qui correspond à PLAYWRIGHT_VERSION
#   make test-writes   test_nr_* qui créent des tickets / modifient une config (NR_ALLOW_WRITES=1)
#   make test-all      test + test-ui
#
# Arguments pytest supplémentaires : make test PYTEST_ARGS="-k 2190 -x"

PYTEST_ARGS ?= -v

# Playwright et ses navigateurs vont par version : une version non figée tire le dernier
# Playwright, qui réclame un Chromium absent (« Executable doesn't exist … headless_shell-XXXX »).
PLAYWRIGHT_VERSION ?= 1.63.0
PYTEST_PLAYWRIGHT_VERSION ?= 0.9.0

DEPS = --with pytest --with httpx --with python-dotenv --with pydantic \
       --with pytest-dependency --with "psycopg[binary]" --with openpyxl
UI_DEPS = --with "playwright==$(PLAYWRIGHT_VERSION)" --with "pytest-playwright==$(PYTEST_PLAYWRIGHT_VERSION)"

# test_test.py ne s'importe pas (SyntaxError de génération Postman), cf. README.
IGNORE = --ignore=tests/test_test.py

.PHONY: help test test-ui ui-browsers test-writes test-all

help:
	@sed -n '1,10p' Makefile

test:
	uv run $(DEPS) pytest tests/ $(IGNORE) --ignore-glob='tests/*_ui.py' $(PYTEST_ARGS)

ui-browsers:
	uv run $(UI_DEPS) playwright install chromium

test-ui:
	uv run $(DEPS) $(UI_DEPS) pytest tests/*_ui.py $(PYTEST_ARGS)

test-writes:
	NR_ALLOW_WRITES=1 uv run $(DEPS) pytest tests/test_nr_*.py $(PYTEST_ARGS)

test-all: test test-ui
