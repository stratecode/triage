#!/usr/bin/env python3
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Initialize LocalStack resources for TrIAge
Creates SQS queues, SNS topics, and secrets needed for local development
"""

import os
import sys
import time
import json
import boto3
import requests
from botocore.config import Config

# LocalStack configuration
LOCALSTACK_ENDPOINT = "http://localstack:4566"
AWS_REGION = "eu-south-2"

# Wait for LocalStack to be ready
print("Waiting for LocalStack to be ready...")
max_attempts = 60
for attempt in range(max_attempts):
    try:
        response = requests.get(f"{LOCALSTACK_ENDPOINT}/_localstack/health", timeout=5)
        health = response.json()
        sqs_status = health.get("services", {}).get("sqs")
        if sqs_status in ["available", "running"]:
            print("LocalStack is ready!")
            break
    except Exception as e:
        if attempt % 10 == 0:  # Print every 10 attempts
            print(f"Waiting... (attempt {attempt + 1}/{max_attempts})")
    time.sleep(2)
else:
    print("ERROR: LocalStack did not become ready in time")
    sys.exit(1)

# Configure boto3 clients
config = Config(region_name=AWS_REGION)
sqs = boto3.client("sqs", endpoint_url=LOCALSTACK_ENDPOINT, config=config)
sns = boto3.client("sns", endpoint_url=LOCALSTACK_ENDPOINT, config=config)
secretsmanager = boto3.client("secretsmanager", endpoint_url=LOCALSTACK_ENDPOINT, config=config)
ssm = boto3.client("ssm", endpoint_url=LOCALSTACK_ENDPOINT, config=config)

print("Creating SQS queues...")

# Create dead letter queue
try:
    dlq_response = sqs.create_queue(
        QueueName="triage-dlq",
        Attributes={"MessageRetentionPeriod": "1209600"}
    )
    dlq_url = dlq_response["QueueUrl"]
    print(f"Created DLQ: {dlq_url}")
except sqs.exceptions.QueueNameExists:
    print("DLQ already exists")
    dlq_response = sqs.get_queue_url(QueueName="triage-dlq")
    dlq_url = dlq_response["QueueUrl"]

# Get DLQ ARN
dlq_attrs = sqs.get_queue_attributes(
    QueueUrl=dlq_url,
    AttributeNames=["QueueArn"]
)
dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
print(f"DLQ ARN: {dlq_arn}")

# Create core events queue with DLQ
try:
    queue_response = sqs.create_queue(
        QueueName="triage-core-events",
        Attributes={
            "MessageRetentionPeriod": "345600",
            "VisibilityTimeout": "300",
            "RedrivePolicy": json.dumps({
                "deadLetterTargetArn": dlq_arn,
                "maxReceiveCount": "3"
            })
        }
    )
    queue_url = queue_response["QueueUrl"]
    print(f"Created core events queue: {queue_url}")
except sqs.exceptions.QueueNameExists:
    print("Core events queue already exists")
    queue_response = sqs.get_queue_url(QueueName="triage-core-events")
    queue_url = queue_response["QueueUrl"]

print("Creating SNS topics...")

# Create core events topic
try:
    topic_response = sns.create_topic(Name="triage-core-events")
    topic_arn = topic_response["TopicArn"]
    print(f"Created topic: {topic_arn}")
except Exception as e:
    print(f"Topic already exists or error: {e}")
    topics = sns.list_topics()
    topic_arn = next(
        (t["TopicArn"] for t in topics["Topics"] if "triage-core-events" in t["TopicArn"]),
        None
    )

if topic_arn:
    print(f"Topic ARN: {topic_arn}")
    
    # Subscribe SQS queue to SNS topic
    queue_attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["QueueArn"]
    )
    queue_arn = queue_attrs["Attributes"]["QueueArn"]
    
    try:
        sns.subscribe(
            TopicArn=topic_arn,
            Protocol="sqs",
            Endpoint=queue_arn
        )
        print("Subscribed queue to topic")
    except Exception as e:
        print(f"Subscription already exists or error: {e}")

print("Creating secrets...")

# Create JIRA credentials secret
jira_secret = {
    "jira_base_url": os.environ.get("JIRA_BASE_URL", "https://example.atlassian.net"),
    "jira_email": os.environ.get("JIRA_EMAIL", "test@example.com"),
    "jira_api_token": os.environ.get("JIRA_API_TOKEN", "test-token"),
    "jira_project": os.environ.get("JIRA_PROJECT", "TEST")
}

try:
    secretsmanager.create_secret(
        Name="triage/jira",
        SecretString=json.dumps(jira_secret)
    )
    print("Created JIRA secret")
except secretsmanager.exceptions.ResourceExistsException:
    print("JIRA secret already exists")

# Create JWT secret for API authentication
jwt_secret = {
    "jwt_secret": os.environ.get("JWT_SECRET", "dev-secret-change-in-production-please-use-a-long-random-string")
}

try:
    secretsmanager.create_secret(
        Name="/local/triage/jwt-secret",
        SecretString=json.dumps(jwt_secret)
    )
    print("Created JWT secret")
except secretsmanager.exceptions.ResourceExistsException:
    print("JWT secret already exists")

# Create Slack credentials secret (if configured)
slack_client_id = os.environ.get("SLACK_CLIENT_ID")
if slack_client_id:
    slack_secret = {
        "client_id": slack_client_id,
        "client_secret": os.environ.get("SLACK_CLIENT_SECRET", ""),
        "signing_secret": os.environ.get("SLACK_SIGNING_SECRET", ""),
        "bot_token": os.environ.get("SLACK_BOT_TOKEN", "")
    }
    
    try:
        secretsmanager.create_secret(
            Name="triage/slack",
            SecretString=json.dumps(slack_secret)
        )
        print("Created Slack secret")
    except secretsmanager.exceptions.ResourceExistsException:
        print("Slack secret already exists")

print("Creating SSM parameters...")

# Create Slack signing secret parameter
slack_signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
if slack_signing_secret:
    try:
        ssm.put_parameter(
            Name="/triage/slack/signing_secret",
            Value=slack_signing_secret,
            Type="SecureString",
            Overwrite=True
        )
        print("Created Slack signing secret parameter")
    except Exception as e:
        print(f"Slack signing secret parameter already exists or error: {e}")

print("")
print("LocalStack initialization complete!")
print("")
print("Resources created:")
print("  - SQS Queue: triage-core-events")
print("  - SQS Queue: triage-dlq (dead letter queue)")
print("  - SNS Topic: triage-core-events")
print("  - Secret: triage/jira")
print("  - Secret: /local/triage/jwt-secret")
if slack_client_id:
    print("  - Secret: triage/slack")
    print("  - Parameter: /triage/slack/signing_secret")
print("")
print(f"Queue URLs (internal): {queue_url}")
print(f"Queue URLs (external): {queue_url.replace('localstack', 'localhost')}")
print(f"DLQ URL (internal): {dlq_url}")
print(f"DLQ URL (external): {dlq_url.replace('localstack', 'localhost')}")
print(f"Topic ARN: {topic_arn}")
print("")
print("JWT Configuration:")
print(f"  Secret: dev-secret-change-in-production-please-use-a-long-random-string")
print(f"  Algorithm: HS256")
print(f"  Use this to generate tokens for API testing")
