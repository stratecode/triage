# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

.PHONY: help install test deploy local clean

PROFILE := stratecode
REGION := eu-south-2
ENV := dev

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv pip install -r requirements.txt
	uv pip install -e .

test: ## Run tests
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-property: ## Run property-based tests
	uv run pytest tests/property/ -v

test-integration: ## Run integration tests
	uv run pytest tests/integration/ -v

coverage: ## Run tests with coverage
	uv run pytest --cov=triage --cov-report=html --cov-report=term

setup-iam: ## Setup IAM permissions for user (requires USERNAME)
	@if [ -z "$(USERNAME)" ]; then \
		echo "Usage: make setup-iam USERNAME=<iam-username>"; \
		exit 1; \
	fi
	./scripts/setup-iam-permissions.sh $(USERNAME)

setup-secrets: ## Setup AWS secrets (requires .env)
	./scripts/setup-secrets.sh $(ENV)

deploy: ## Deploy to AWS
	./scripts/deploy.sh $(ENV)

deploy-prod: ## Deploy to production
	./scripts/deploy.sh prod

local: ## Run API locally
	./scripts/local-test.sh

generate-token: ## Generate JWT token
	./scripts/generate-token.sh $(ENV) admin 30

test-api: ## Test deployed API (requires API_URL and TOKEN)
	@if [ -z "$(API_URL)" ] || [ -z "$(TOKEN)" ]; then \
		echo "Usage: make test-api API_URL=<url> TOKEN=<token>"; \
		exit 1; \
	fi
	./scripts/test-api.sh $(API_URL) $(TOKEN)

logs: ## Tail Lambda logs
	sam logs -n GeneratePlanFunction --stack-name triage-api-$(ENV) --tail --profile $(PROFILE) --region $(REGION)

clean: ## Clean build artifacts
	rm -rf .aws-sam/
	rm -rf lambda/triage/
	rm -rf lambda/__pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

clean-all: clean ## Clean everything including venv
	rm -rf .venv/
	rm -rf .pytest_cache/
	rm -rf .hypothesis/
	rm -rf htmlcov/

build: ## Build SAM application
	sam build --profile $(PROFILE) --region $(REGION)

validate: ## Validate SAM template
	sam validate --profile $(PROFILE) --region $(REGION)

package: ## Package for deployment
	sam package --profile $(PROFILE) --region $(REGION)

delete-stack: ## Delete CloudFormation stack
	aws cloudformation delete-stack \
		--profile $(PROFILE) \
		--region $(REGION) \
		--stack-name triage-api-$(ENV)

describe-stack: ## Describe CloudFormation stack
	aws cloudformation describe-stacks \
		--profile $(PROFILE) \
		--region $(REGION) \
		--stack-name triage-api-$(ENV)

list-secrets: ## List AWS secrets
	aws secretsmanager list-secrets \
		--profile $(PROFILE) \
		--region $(REGION) \
		--filters Key=name,Values=/$(ENV)/triage/

cli-plan: ## Generate plan using CLI
	triage generate-plan --debug

cli-help: ## Show CLI help
	triage --help
