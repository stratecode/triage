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
echo -e "${BLUE}TrIAge - SAM Deployment Validation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

ERRORS=0

# Check 1: SAM CLI installed
echo -e "${YELLOW}Check 1: SAM CLI Installation${NC}"
if command -v sam &> /dev/null; then
    VERSION=$(sam --version)
    echo -e "${GREEN}✓${NC} SAM CLI installed: $VERSION"
else
    echo -e "${RED}✗${NC} SAM CLI not found"
    echo "  Install with: brew install aws-sam-cli"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 2: Docker running
echo -e "${YELLOW}Check 2: Docker${NC}"
if docker info &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker is running"
else
    echo -e "${RED}✗${NC} Docker is not running"
    echo "  Start Docker Desktop"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 3: .env file exists
echo -e "${YELLOW}Check 3: Environment Configuration${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    
    # Check required variables
    if grep -q "JIRA_BASE_URL=" .env && \
       grep -q "JIRA_EMAIL=" .env && \
       grep -q "JIRA_API_TOKEN=" .env; then
        echo -e "${GREEN}✓${NC} Required JIRA variables configured"
    else
        echo -e "${RED}✗${NC} Missing required JIRA variables"
        echo "  Configure: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗${NC} .env file not found"
    echo "  Copy from: cp .env.example .env"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 4: SAM template valid
echo -e "${YELLOW}Check 4: SAM Template${NC}"
if sam validate --lint &> /dev/null; then
    echo -e "${GREEN}✓${NC} SAM template is valid"
else
    echo -e "${RED}✗${NC} SAM template validation failed"
    sam validate --lint
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 5: Lambda directory structure
echo -e "${YELLOW}Check 5: Lambda Directory${NC}"
if [ -d lambda ]; then
    echo -e "${GREEN}✓${NC} lambda/ directory exists"
    
    # Check for required files
    if [ -f lambda/handlers.py ] && \
       [ -f lambda/requirements.txt ] && \
       [ -d lambda/triage ]; then
        echo -e "${GREEN}✓${NC} Required Lambda files present"
    else
        echo -e "${RED}✗${NC} Missing required Lambda files"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗${NC} lambda/ directory not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 6: SAM build exists
echo -e "${YELLOW}Check 6: SAM Build${NC}"
if [ -d .aws-sam/build ]; then
    echo -e "${GREEN}✓${NC} SAM build exists"
    
    # Count built functions
    FUNCTIONS=$(find .aws-sam/build -maxdepth 1 -type d -name "*Function" | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} $FUNCTIONS Lambda functions built"
else
    echo -e "${YELLOW}⚠${NC} SAM build not found"
    echo "  Run: make sam-build"
fi
echo ""

# Check 7: Event files
echo -e "${YELLOW}Check 7: Event Files${NC}"
if [ -f events/health-check.json ] && [ -f events/generate-plan.json ]; then
    echo -e "${GREEN}✓${NC} Event files present"
else
    echo -e "${YELLOW}⚠${NC} Event files missing"
    echo "  Some test commands may not work"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Build: make sam-build"
    echo "  2. Test:  make sam-test-functions"
    echo "  3. Start: make sam-start"
    echo "  4. Test:  make sam-test (in another terminal)"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) found${NC}"
    echo ""
    echo "Fix the errors above and try again"
    exit 1
fi
