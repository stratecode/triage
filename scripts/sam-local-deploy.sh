#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="triage-api-local"
REGION="eu-south-2"
ENVIRONMENT="local"
PORT="${SAM_LOCAL_PORT:-3000}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TrIAge - SAM Local Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure your settings"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Validate required environment variables
if [ -z "$JIRA_BASE_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo -e "${RED}Error: Missing required JIRA configuration${NC}"
    echo "Please configure JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN in .env"
    exit 1
fi

echo -e "${GREEN}✓${NC} Environment variables loaded"

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo -e "${RED}Error: AWS SAM CLI is not installed${NC}"
    echo "Install it with: brew install aws-sam-cli"
    exit 1
fi

echo -e "${GREEN}✓${NC} SAM CLI found: $(sam --version)"

# Build the Lambda functions
echo ""
echo -e "${YELLOW}Building Lambda functions...${NC}"
sam build --use-container

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Build completed successfully"
else
    echo -e "${RED}✗${NC} Build failed"
    exit 1
fi

# Create env vars file for SAM
ENV_FILE=$(mktemp)
cat > "$ENV_FILE" <<EOF
{
  "Parameters": {
    "JIRA_BASE_URL": "$JIRA_BASE_URL",
    "JIRA_EMAIL": "$JIRA_EMAIL",
    "JIRA_API_TOKEN": "$JIRA_API_TOKEN",
    "JIRA_PROJECT": "${JIRA_PROJECT:-}",
    "ADMIN_TIME_START": "${ADMIN_TIME_START:-14:00}",
    "ADMIN_TIME_END": "${ADMIN_TIME_END:-15:30}",
    "JWT_SECRET": "${JWT_SECRET:-dev-secret-change-in-production}",
    "LOG_LEVEL": "INFO",
    "REGION": "$REGION",
    "Environment": "$ENVIRONMENT"
  }
}
EOF

# Cleanup function
cleanup() {
    rm -f "$ENV_FILE"
}
trap cleanup EXIT

# Start SAM local API
echo ""
echo -e "${YELLOW}Starting SAM Local API...${NC}"
echo -e "${BLUE}API will be available at: http://localhost:${PORT}${NC}"
echo ""
echo -e "${YELLOW}Endpoints:${NC}"
echo -e "  ${BLUE}GET${NC}  http://localhost:${PORT}/api/v1/health"
echo -e "  ${BLUE}POST${NC} http://localhost:${PORT}/api/v1/plan"
echo -e "  ${BLUE}GET${NC}  http://localhost:${PORT}/api/v1/plan/{date}"
echo -e "  ${BLUE}POST${NC} http://localhost:${PORT}/api/v1/plan/{date}/approve"
echo -e "  ${BLUE}POST${NC} http://localhost:${PORT}/api/v1/task/{taskId}/decompose"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start local API with environment variables
sam local start-api \
    --port "$PORT" \
    --env-vars "$ENV_FILE" \
    --warm-containers EAGER
