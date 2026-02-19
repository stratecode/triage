#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

echo "=========================================="
echo "TrIAge Endpoint Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local method=${3:-GET}
    local data=${4:-}
    local expected_status=${5:-200}
    
    echo -n "Testing $name... "
    
    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" 2>&1)
    fi
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $http_code)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_status, got $http_code)"
        echo "Response: $body"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Test health endpoints
echo "=== Health Checks ==="
test_endpoint "API Health" "http://localhost:8000/api/v1/health" "GET" "" "200"
test_endpoint "Plugin Health" "http://localhost:8000/plugins/health" "GET" "" "200"
echo ""

# Test plan generation
echo "=== Plan Generation ==="
test_endpoint "Generate Plan (empty body)" "http://localhost:8000/api/v1/plan" "POST" "{}" "200"
test_endpoint "Generate Plan (with date)" "http://localhost:8000/api/v1/plan" "POST" '{"date":"2026-02-19"}' "200"
echo ""

# Test OAuth
echo "=== OAuth Flow ==="
test_endpoint "OAuth Authorize" "http://localhost:8000/plugins/slack/oauth/authorize" "GET" "" "302"
echo ""

# Summary
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
