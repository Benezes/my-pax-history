.PHONY: install dev

install:
	python3 -m venv .venv || python3 -m virtualenv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

dev:
	bash scripts/dev.sh
