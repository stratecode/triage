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

API_URL="${1:-http://localhost:3000}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TrIAge - SAM Local API Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Testing API at: ${API_URL}${NC}"
echo ""

# Test 1: Health Check (no auth required)
echo -e "${YELLOW}Test 1: Health Check${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" "${API_URL}/api/v1/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC} Health check passed"
    echo "Response: $BODY"
else
    echo -e "${RED}✗${NC} Health check failed (HTTP $HTTP_CODE)"
    echo "Response: $BODY"
    exit 1
fi

echo ""

# Test 2: Generate Plan (requires auth - will fail without token, but tests endpoint)
echo -e "${YELLOW}Test 2: Generate Plan Endpoint${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/api/v1/plan" \
    -H "Content-Type: application/json" \
    -d '{}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo -e "${GREEN}✓${NC} Endpoint is protected (expected 401/403)"
    echo "Response: $BODY"
elif [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC} Plan generated successfully"
    echo "Response: $BODY"
else
    echo -e "${YELLOW}⚠${NC} Unexpected response (HTTP $HTTP_CODE)"
    echo "Response: $BODY"
fi

echo ""

# Test 3: Plugin Health Check
echo -e "${YELLOW}Test 3: Plugin Health Check${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" "${API_URL}/plugins/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC} Plugin health check passed"
    echo "Response: $BODY"
else
    echo -e "${YELLOW}⚠${NC} Plugin health check returned HTTP $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Basic connectivity tests completed${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Note:${NC} To test authenticated endpoints, generate a token with:"
echo -e "  ${BLUE}./scripts/generate-token.sh local${NC}"
echo ""
