#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Deploy Lambda functions to LocalStack
# This script is a wrapper that calls the Python deployment script

set -e

echo "🚀 Deploying Lambda functions to LocalStack..."

# Run Python deployment script
python3 /app/docker/deploy-to-localstack.py


