.PHONY: help install dev test lint format docker-build docker-up docker-down clean list-channels

help:
	@echo "Hermine Media Downloader - Available Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install          Install dependencies"
	@echo "  make install-dev      Install with development dependencies"
	@echo ""
	@echo "Running:"
	@echo "  make run              Run the downloader"
	@echo "  make list-channels    List available channels"
	@echo "  make stats            Show download statistics"
	@echo ""
	@echo "Development:"
	@echo "  make test             Run tests"
	@echo "  make lint             Run linting"
	@echo "  make format           Format code"
	@echo "  make type-check       Type checking with mypy"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-up        Start with Docker Compose"
	@echo "  make docker-down      Stop Docker Compose"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Clean cache files"
	@echo "  make config           Create .env from template"

.DEFAULT_GOAL := help

install:
	pip install -q -r requirements.txt
	@echo "✓ Dependencies installed"

install-dev: install
	pip install -q pytest pytest-asyncio pytest-cov black flake8 mypy
	@echo "✓ Development dependencies installed"

run:
	python3 -m src.main

list-channels:
	python3 -m src.cli list-channels

stats:
	python3 -m src.cli stats

test:
	pytest tests/ -v --cov=src

lint:
	flake8 src/ --max-line-length=120

format:
	black src/ --line-length=120

type-check:
	mypy src/ --ignore-missing-imports

docker-build:
	docker build -t hermine-downloader .

config:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ .env created from template"; \
	else \
		echo "⚠️  .env already exists"; \
	fi

docker-up: config
	docker-compose up -d
	@echo "✓ Docker containers started"

docker-down:
	docker-compose down
	@echo "✓ Docker containers stopped"

clean:
	rm -rf __pycache__ build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	@echo "✓ Cache cleaned"
