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
echo -e "${BLUE}TrIAge - SAM Function Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if build exists
if [ ! -d ".aws-sam/build" ]; then
    echo -e "${RED}Error: SAM build not found${NC}"
    echo "Run 'make sam-build' first"
    exit 1
fi

PASSED=0
FAILED=0

# Test 1: Health Check Function
echo -e "${YELLOW}Test 1: HealthCheckFunction${NC}"
RESULT=$(sam local invoke HealthCheckFunction -e events/health-check.json 2>&1)
if echo "$RESULT" | grep -q "healthy"; then
    echo -e "${GREEN}✓${NC} Health check passed"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}✗${NC} Health check failed"
    echo "$RESULT" | tail -5
    FAILED=$((FAILED + 1))
fi
echo ""

# Test 2: Generate Plan Function (will fail without JIRA, but tests invocation)
echo -e "${YELLOW}Test 2: GeneratePlanFunction${NC}"
RESULT=$(sam local invoke GeneratePlanFunction -e events/generate-plan.json 2>&1)
if echo "$RESULT" | grep -q "RequestId"; then
    echo -e "${GREEN}✓${NC} Function invoked successfully"
    PASSED=$((PASSED + 1))
    
    # Check if it's an auth error (expected) or other error
    if echo "$RESULT" | grep -q "Unauthorized\|Missing Authorization"; then
        echo -e "${BLUE}ℹ${NC} Auth required (expected)"
    elif echo "$RESULT" | grep -q "JIRA"; then
        echo -e "${BLUE}ℹ${NC} JIRA connection attempted"
    fi
else
    echo -e "${RED}✗${NC} Function invocation failed"
    echo "$RESULT" | tail -5
    FAILED=$((FAILED + 1))
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed${NC}"
    exit 1
fi
