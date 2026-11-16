PYTHON ?= python3.11
VENV := .venv/bin/python

.PHONY: setup doctor test smoke reproduce report demo
setup:
	$(PYTHON) -m venv .venv
	$(VENV) -m pip install -e '.[metal,dev]'
doctor:
	$(VENV) -m plawbench doctor
test:
	$(VENV) -m pytest -q
smoke:
	$(VENV) -m plawbench run --per-task 1 --output experiments/smoke
reproduce:
	sh scripts/reproduce.sh
report:
	$(VENV) -m plawbench report --output experiments/m1-public
demo:
	$(VENV) scripts/record_demo.py --report experiments/m1-public/report.html
	$(VENV) scripts/verify_demo.py
