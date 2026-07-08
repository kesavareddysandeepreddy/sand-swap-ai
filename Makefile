install:
	pip install -r requirements.txt

format:
	black .
	isort .

lint:
	ruff check .

typecheck:
	mypy backend

test:
	pytest

check: lint typecheck test
