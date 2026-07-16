# ==============================================================
# Makefile — AI E-Commerce Multi-Agent System
# ==============================================================
# Usage:
#   make build       Build all Docker images
#   make up          Start all services in background
#   make down        Stop all services
#   make logs        View service logs
#   make restart     Restart all services
#   make test        Run backend tests
#   make clean       Remove containers, images, and volumes
# ==============================================================

.PHONY: build up down logs restart test clean

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart: down up

test:
	python -m pytest tests/ -v --timeout=120

clean:
	docker compose down -v --rmi all --remove-orphans