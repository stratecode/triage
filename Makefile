# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

.PHONY: help install test lint format clean docker-up docker-down docker-test deploy-dev deploy-prod

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development
install: ## Install dependencies using uv
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-property: ## Run property-based tests
	pytest tests/property/ -v

test-integration: ## Run integration tests
	pytest tests/integration/ -v

lint: ## Run linting checks
	ruff check triage/ lambda/ tests/
	mypy triage/ lambda/

format: ## Format code
	ruff format triage/ lambda/ tests/

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".hypothesis" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/
	rm -rf logs/*.log

# Docker Local
docker-up: ## Start Docker local stack
	./scripts/docker-local.sh up

docker-down: ## Stop Docker local stack
	./scripts/docker-local.sh down

docker-restart: ## Restart Docker local stack
	./scripts/docker-local.sh restart

docker-logs: ## View Docker logs
	./scripts/docker-local.sh logs api

docker-test: ## Test Docker local stack
	./scripts/docker-local.sh test

docker-token: ## Generate JWT token for local testing
	./scripts/docker-local.sh token admin 30

docker-rebuild: ## Rebuild Docker images
	./scripts/docker-local.sh rebuild

docker-clean: ## Clean up Docker resources
	./scripts/docker-local.sh clean

# AWS Deployment
deploy-dev: ## Deploy to AWS dev environment
	./scripts/deploy.sh dev

deploy-prod: ## Deploy to AWS prod environment
	./scripts/deploy.sh prod

aws-logs: ## View AWS Lambda logs
	sam logs -n GeneratePlanFunction --stack-name triage-api-dev --tail

aws-test: ## Test AWS deployment (requires API_URL and TOKEN env vars)
	@if [ -z "$$API_URL" ] || [ -z "$$TOKEN" ]; then \
		echo "Error: Set API_URL and TOKEN environment variables"; \
		echo "Example: API_URL=https://xxx.execute-api.eu-south-2.amazonaws.com/dev TOKEN=xxx make aws-test"; \
		exit 1; \
	fi
	./scripts/test-api.sh $$API_URL $$TOKEN

# SAM Local
sam-build: ## Build SAM application
	sam build

sam-local: ## Start SAM local API
	sam local start-api --warm-containers EAGER

sam-invoke: ## Invoke Lambda function locally
	sam local invoke GeneratePlanFunction --event events/generate-plan.json

# Examples
demo-mvp: ## Run MVP demo
	python examples/demo_mvp.py

demo-decomposition: ## Run decomposition demo
	python examples/demo_decomposition.py

demo-replanning: ## Run replanning demo
	python examples/demo_replanning.py

demo-closure: ## Run closure tracking demo
	python examples/demo_closure_tracking.py

validate-mvp: ## Validate MVP implementation
	python examples/validate_mvp.py

diagnose-jira: ## Diagnose JIRA connection
	python examples/diagnose-jira-connection.py

# Documentation
docs: ## Generate API documentation
	@echo "Generating API documentation..."
	@echo "TODO: Add OpenAPI spec generation"

# Quick workflows
dev: docker-up docker-test ## Start local development environment and run tests

ci: lint test ## Run CI checks (lint + test)

all: clean install lint test ## Run full build pipeline
