#!/bin/bash
# Example script to generate a daily plan using AI Secretary

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    echo "Please copy .env.example to .env and fill in your JIRA credentials"
    exit 1
fi

# Generate daily plan
echo "Generating daily plan..."
ai-secretary generate-plan "$@"
