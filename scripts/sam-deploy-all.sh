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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TrIAge - Complete SAM Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Validate
echo -e "${YELLOW}Step 1/4: Validating setup...${NC}"
if ./scripts/validate-sam-deployment.sh > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Validation passed"
else
    echo -e "${RED}✗${NC} Validation failed"
    echo ""
    echo "Running full validation to show errors:"
    ./scripts/validate-sam-deployment.sh
    exit 1
fi
echo ""

# Step 2: Build
echo -e "${YELLOW}Step 2/4: Building Lambda functions...${NC}"
echo "This may take 2-3 minutes on first run..."
if sam build --use-container > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Build completed"
else
    echo -e "${RED}✗${NC} Build failed"
    echo ""
    echo "Running build with output:"
    sam build --use-container
    exit 1
fi
echo ""

# Step 3: Test
echo -e "${YELLOW}Step 3/4: Testing Lambda functions...${NC}"
if ./scripts/test-sam-functions.sh > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} All tests passed"
else
    echo -e "${RED}✗${NC} Tests failed"
    echo ""
    echo "Running tests with output:"
    ./scripts/test-sam-functions.sh
    exit 1
fi
echo ""

# Step 4: Start
echo -e "${YELLOW}Step 4/4: Starting SAM Local API...${NC}"
echo ""
echo -e "${GREEN}✓${NC} Setup complete!"
echo ""
echo -e "${BLUE}API will be available at: http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}Endpoints:${NC}"
echo -e "  ${BLUE}GET${NC}  http://localhost:3000/api/v1/health"
echo -e "  ${BLUE}POST${NC} http://localhost:3000/api/v1/plan"
echo -e "  ${BLUE}GET${NC}  http://localhost:3000/api/v1/plan/{date}"
echo ""
echo -e "${YELLOW}Test in another terminal:${NC}"
echo -e "  curl http://localhost:3000/api/v1/health"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Load environment variables
set -a
source .env
set +a

# Create env vars file
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
    "REGION": "eu-south-2",
    "Environment": "local"
  }
}
EOF

# Cleanup function
cleanup() {
    rm -f "$ENV_FILE"
}
trap cleanup EXIT

# Start API
sam local start-api \
    --port 3000 \
    --env-vars "$ENV_FILE" \
    --warm-containers EAGER
