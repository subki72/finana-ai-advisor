.PHONY: install lint format test run-api run-ui docker-build clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests
	$(PYTHON) -m flake8 --max-line-length=120 src tests

format:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=75

run-api:
	$(PYTHON) -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	$(PYTHON) -m streamlit run src/main.py

docker-build:
	docker build -t finana-ai-advisor:latest .

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in list(pathlib.Path('.').rglob('__pycache__')) + [pathlib.Path(x) for x in ('.pytest_cache', '.ruff_cache', '.mypy_cache', 'htmlcov', 'dist', 'build')]]"
