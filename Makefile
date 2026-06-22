.PHONY: help install setup fixture-test author validate smoke analyze-smoke phase0 analyze clean

RUN ?= phase0

help:
	@echo "Redundra-Bench targets:"
	@echo "  make install        install Python deps"
	@echo "  make setup          create the pinned fixture git repo locally (run after clone)"
	@echo "  make fixture-test   run the fixture's own pytest suite (baseline)"
	@echo "  make author         regenerate task dirs from specs"
	@echo "  make validate       validate gold patches + reuse verdicts (no model calls)"
	@echo "  make smoke          cheap smoke run (3 tasks x 2 arms x 1 seed)"
	@echo "  make analyze-smoke  analyze the smoke run"
	@echo "  make phase0         full Phase-0 run (RUN=phase0, override with RUN=...)"
	@echo "  make analyze        analyze RUN (default phase0)"
	@echo "  make clean          remove runtime artifacts (.codex_home, results)"

install:
	pip install -r requirements.txt

setup:
	python3 benchmark/scripts/setup_fixture.py

fixture-test: setup
	cd fixtures/redundra-utils && python3 -m pytest -q

author:
	python3 benchmark/scripts/author_tasks.py
	python3 benchmark/scripts/gen_manifest.py

validate: setup
	python3 benchmark/scripts/validate_gold.py

smoke:
	python3 benchmark/runner/run_all.py --run-id smoke --smoke

analyze-smoke:
	python3 benchmark/analysis/analyze.py smoke

phase0:
	python3 benchmark/runner/run_all.py --run-id $(RUN) --seeds 5

analyze:
	python3 benchmark/analysis/analyze.py $(RUN)

clean:
	rm -rf benchmark/.codex_home benchmark/results
