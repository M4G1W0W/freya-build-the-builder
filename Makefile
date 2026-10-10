# Dev shortcuts. Secrets come from .env (see .env.example). `make help` lists targets.
SHELL := /bin/bash
PY := .venv/bin/python
ENV := set -a; [ -f .env ] && . ./.env; set +a;
TS := $(shell date +%Y%m%d-%H%M%S)
BRIEF ?= A
REPS ?= 1
CASE ?= PUB-01

.PHONY: help setup check test lint fmt credits cases show call chat baseline

help:  ## list targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

setup:  ## install the locked environment
	uv sync

check:  ## env vars, Freya API, workspace, credits (read-only)
	$(PY) scripts/env_check.py

test:  ## unit + smoke tests
	uv run pytest -q

lint:  ## ruff lint + format check
	uv run ruff check . && uv run ruff format --check .

fmt:  ## ruff format
	uv run ruff format .

credits:  ## log credits: make credits LABEL="after X"
	$(PY) scripts/credits.py $(LABEL)

cases:  ## practice run: make cases AGENT=<agent_id> [BRIEF=A] [REPS=3] [STYLE=talkative] [ONLY=PUB-04]
	@test -n "$(AGENT)" || (echo "AGENT=<agent_id> required"; exit 1)
	$(ENV) $(PY) -u kit/tools/run_cases.py $(AGENT) --brief $(BRIEF) --reps $(REPS) \
		$(if $(STYLE),--style $(STYLE)) $(if $(ONLY),--only $(ONLY)) \
		--out $(CURDIR)/runs/$(TS)-$(BRIEF).json 2>&1 | tee runs/$(TS)-$(BRIEF).log

show:  ## summarise a run + failed transcripts: make show RUN=runs/<file>.json
	$(PY) scripts/show_run.py $(RUN) --calls

call:  ## one transcript: make call ID=<call_id>
	$(PY) scripts/show_call.py $(ID)

chat:  ## quick text chat: make chat WF=<workflow_id> [CASE=PUB-01]
	$(PY) scripts/chat.py $(WF) --case $(CASE)

baseline:  ## kit's minimal builder on brief A, then one practice run
	$(ENV) $(PY) kit/examples/minimal_builder.py kit/briefs/brief-a.md
	@echo "now: make cases AGENT=<agent_id printed above>"
