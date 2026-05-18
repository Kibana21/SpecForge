SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend
ENV_FILE     := $(BACKEND_DIR)/.env
VENV         := $(CURDIR)/$(BACKEND_DIR)/.venv
PYTHON       := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip
UVICORN      := $(VENV)/bin/uvicorn
ALEMBIC      := $(VENV)/bin/alembic
PYTEST       := $(VENV)/bin/pytest

# ── Colours ─────────────────────────────────────────────────────────────────
BOLD  := $(shell printf '\033[1m')
RESET := $(shell printf '\033[0m')
GREEN := $(shell printf '\033[32m')
CYAN  := $(shell printf '\033[36m')

.PHONY: help db-shell \
        install install-fe \
        migrate migrate-down \
        dev dev-be dev-fe \
        test test-be typecheck lint \
        clean

## ── Help ────────────────────────────────────────────────────────────────────

help: ## Show this help
	@echo ""
	@echo "  $(BOLD)SpecForge AI$(RESET) — available targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

## ── Database ─────────────────────────────────────────────────────────────────

db-shell: ## Open a psql shell using DATABASE_URL from backend/.env
	@if [ ! -f "$(ENV_FILE)" ]; then echo "$(ENV_FILE) not found"; exit 1; fi
	@DB_URL=$$(grep '^DATABASE_URL=' $(ENV_FILE) | cut -d= -f2-); \
	 PSQL_URL=$$(echo "$$DB_URL" | sed 's|+asyncpg||'); \
	 psql "$$PSQL_URL"

## ── Backend setup ────────────────────────────────────────────────────────────

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip

install: $(VENV)/bin/activate ## Create venv and install backend deps
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@echo "$(GREEN)Backend deps installed.$(RESET)"

## ── Frontend setup ───────────────────────────────────────────────────────────

install-fe: ## Install frontend npm deps
	cd $(FRONTEND_DIR) && npm install
	@echo "$(GREEN)Frontend deps installed.$(RESET)"

## ── Migrations ───────────────────────────────────────────────────────────────

migrate: ## Run alembic upgrade head
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head

migrate-down: ## Rollback last alembic migration
	cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

## ── Dev servers ──────────────────────────────────────────────────────────────

dev-be: ## Start backend dev server (hot-reload, port 8000)
	cd $(BACKEND_DIR) && $(UVICORN) app.main:app --reload --port 8000

dev-fe: ## Start frontend dev server (port 3000)
	cd $(FRONTEND_DIR) && npm run dev

dev: ## Start backend and frontend together (Ctrl-C stops both)
	@echo "Starting backend and frontend… (Ctrl-C stops both)"
	@trap 'kill 0' INT; \
	  (cd $(BACKEND_DIR) && $(UVICORN) app.main:app --reload --port 8000) & \
	  (cd $(FRONTEND_DIR) && npm run dev) & \
	  wait

## ── Tests / checks ───────────────────────────────────────────────────────────

test-be: ## Run backend pytest suite
	cd $(BACKEND_DIR) && $(PYTEST) -q

typecheck: ## Run frontend TypeScript check
	cd $(FRONTEND_DIR) && npm run typecheck

lint: ## Run frontend ESLint
	cd $(FRONTEND_DIR) && npm run lint

test: test-be typecheck lint ## Run all checks (backend + FE typecheck + lint)
	@echo "$(GREEN)All checks passed.$(RESET)"

## ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove venv, .next build cache, __pycache__
	rm -rf $(VENV) $(FRONTEND_DIR)/.next
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Cleaned.$(RESET)"
