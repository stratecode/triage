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
	uv pip install -e . --no-deps

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-property: ## Run property-based tests
	pytest tests/property/ -v

test-integration: ## Run integration tests
	pytest tests/integration/ -v

lint: ## Run linting checks
	uv run ruff check triage/ lambda/event_processor.py tests/

format: ## Format code
	uv run ruff format triage/ lambda/event_processor.py tests/

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

docker-restart: ## Restart Docker local stack (clean restart)
	@echo "Stopping containers..."
	docker compose -p triage down
	@echo "Waiting for cleanup..."
	sleep 2
	@echo "Starting containers..."
	docker compose -p triage up -d
	@echo "Waiting for initialization..."
	sleep 5
	@echo "Checking status..."
	docker compose -p triage ps

docker-logs: ## View Docker logs
	./scripts/docker-local.sh logs api

docker-test: ## Test Docker local stack
	./scripts/docker-local.sh test

docker-rebuild: ## Rebuild Docker images
	./scripts/docker-local.sh rebuild

docker-clean: ## Clean up Docker resources
	./scripts/docker-local.sh clean

docker-logs-localstack: ## View LocalStack initialization logs
	docker compose -p triage logs localstack-init

docker-lambda-list: ## List deployed Lambda functions in LocalStack
	@echo "Listing Lambda functions in LocalStack..."
	@docker compose -p triage exec localstack awslocal lambda list-functions --query 'Functions[*].[FunctionName,Runtime,Handler]' --output table || echo "LocalStack not running"

docker-api-gateway: ## Show API Gateway ID and routes
	@echo "API Gateway ID:"
	@docker compose -p triage exec api cat /tmp/api_gateway_id.txt 2>/dev/null || echo "API Gateway ID not found (init may not be complete)"
	@echo ""
	@echo "API Gateway Routes:"
	@docker compose -p triage exec localstack awslocal apigateway get-rest-apis --query 'items[*].[id,name]' --output table 2>/dev/null || echo "LocalStack not running"

docker-stack-outputs: ## Show CloudFormation stack outputs
	@echo "CloudFormation Stack Outputs:"
	@docker compose -p triage exec localstack awslocal cloudformation describe-stacks --stack-name triage-api-local --query 'Stacks[0].Outputs' --output table 2>/dev/null || echo "Stack not deployed yet"

docker-test-oauth: ## Test OAuth authorize endpoint
	@echo "Testing OAuth authorize endpoint..."
	@curl -v http://localhost:8000/plugins/slack/oauth/authorize 2>&1 | grep -E "(HTTP|Location|error)" || echo "Failed to connect"

docker-test-health: ## Test health endpoints
	@echo "Testing API health..."
	@curl -s http://localhost:8000/api/v1/health | python -m json.tool || echo "API not responding"
	@echo ""
	@echo "Testing plugin health..."
	@curl -s http://localhost:8000/plugins/health | python -m json.tool || echo "Plugin handler not responding"

docker-test-endpoints: ## Run comprehensive endpoint tests
	@./scripts/test-endpoints.sh

# AWS Deployment
prune-dev: ## Forcefully delete all dev stack resources (DESTRUCTIVE!)
	./scripts/prune-stack.sh dev

prune-staging: ## Forcefully delete all staging stack resources (DESTRUCTIVE!)
	./scripts/prune-stack.sh staging

prune-prod: ## Forcefully delete all prod stack resources (DESTRUCTIVE!)
	./scripts/prune-stack.sh prod

deploy-dev: ## Deploy to AWS dev environment
	./scripts/deploy.sh dev

deploy-staging: ## Deploy to AWS staging environment
	./scripts/deploy.sh staging

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
sam-deploy-all: ## Complete SAM deployment (validate + build + test + start) - ONE COMMAND
	./scripts/sam-deploy-all.sh

sam-validate-deployment: ## Validate SAM deployment setup
	./scripts/validate-sam-deployment.sh

sam-build: ## Build SAM application
	sam build --use-container

sam-start: ## Start SAM local API (requires build first)
	./scripts/sam-local-start.sh

sam-deploy-local: ## Build and start SAM local API (no validation/tests)
	./scripts/sam-local-deploy.sh

sam-test: ## Test SAM local API endpoints
	./scripts/test-sam-local.sh

sam-test-functions: ## Test SAM Lambda functions directly
	./scripts/test-sam-functions.sh

sam-validate: ## Validate SAM template
	sam validate --lint

sam-invoke-health: ## Invoke HealthCheck function locally
	sam local invoke HealthCheckFunction -e events/health-check.json

sam-invoke-plan: ## Invoke GeneratePlan function locally
	sam local invoke GeneratePlanFunction -e events/generate-plan.json

sam-clean: ## Clean SAM build artifacts
	rm -rf .aws-sam/build/

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

all: clean install lint ## Run full build pipeline
