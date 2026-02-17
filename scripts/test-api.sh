#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

API_URL="${1}"
TOKEN="${2}"

if [ -z "$API_URL" ]; then
    echo "Usage: ./scripts/test-api.sh <API_URL> [TOKEN]"
    echo "Example: ./scripts/test-api.sh https://xxx.execute-api.eu-south-2.amazonaws.com/dev eyJhbGc..."
    exit 1
fi

echo "🧪 Testing TrIAge API"
echo "API URL: $API_URL"
echo ""

# Test 1: Health check (no auth required)
echo "1️⃣ Testing health check..."
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "${API_URL}/api/v1/health")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -1)
BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Health check passed"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
else
    echo "❌ Health check failed (HTTP $HTTP_CODE)"
    echo "$BODY"
fi
echo ""

# If no token provided, stop here
if [ -z "$TOKEN" ]; then
    echo "ℹ️  No token provided. Skipping authenticated endpoints."
    echo "Generate a token with: ./scripts/generate-token.sh"
    exit 0
fi

# Test 2: Generate plan
echo "2️⃣ Testing plan generation..."
PLAN_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"date":"2026-02-17"}' \
    "${API_URL}/api/v1/plan")
HTTP_CODE=$(echo "$PLAN_RESPONSE" | tail -1)
BODY=$(echo "$PLAN_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Plan generation passed"
    echo "$BODY" | jq '.plan.priorities | length' 2>/dev/null | xargs echo "Priorities:" || echo "Response received"
else
    echo "❌ Plan generation failed (HTTP $HTTP_CODE)"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
fi
echo ""

# Test 3: Get plan
echo "3️⃣ Testing get plan..."
GET_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "${API_URL}/api/v1/plan/2026-02-17")
HTTP_CODE=$(echo "$GET_RESPONSE" | tail -1)
BODY=$(echo "$GET_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Get plan passed"
else
    echo "❌ Get plan failed (HTTP $HTTP_CODE)"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
fi
echo ""

# Test 4: Approve plan
echo "4️⃣ Testing plan approval..."
APPROVE_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"approved":true,"feedback":"Looks good!"}' \
    "${API_URL}/api/v1/plan/2026-02-17/approve")
HTTP_CODE=$(echo "$APPROVE_RESPONSE" | tail -1)
BODY=$(echo "$APPROVE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Plan approval passed"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
else
    echo "❌ Plan approval failed (HTTP $HTTP_CODE)"
    echo "$BODY" | jq '.' 2>/dev/null || echo "$BODY"
fi
echo ""

echo "✅ API testing complete!"
