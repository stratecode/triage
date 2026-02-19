#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Initialize LocalStack secrets for TrIAge
# SAM will handle Lambda, API Gateway, SNS, SQS, and EventBridge deployment

set -e

echo "🔧 Initializing LocalStack secrets..."

# Run Python initialization script for secrets only
python3 /app/docker/init-localstack.py
