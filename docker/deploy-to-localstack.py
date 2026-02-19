#!/usr/bin/env python3
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Deploy Lambda functions to LocalStack
Packages and deploys all Lambda functions with API Gateway and EventBridge
"""

import os
import sys
import time
import json
import zipfile
import tempfile
import shutil
from pathlib import Path
import boto3
import requests
from botocore.config import Config

# LocalStack configuration
LOCALSTACK_ENDPOINT = "http://localstack:4566"
AWS_REGION = "eu-south-2"

print("🚀 Deploying Lambda functions to LocalStack...")

# Wait for LocalStack Lambda service
print("⏳ Waiting for LocalStack to be ready...")
max_attempts = 60
for attempt in range(max_attempts):
    try:
        response = requests.get(f"{LOCALSTACK_ENDPOINT}/_localstack/health")
        health = response.json()
        if health.get("services", {}).get("lambda") == "available":
            print("✅ LocalStack is ready!")
            break
    except Exception:
        pass
    time.sleep(2)
else:
    print("ERROR: LocalStack Lambda service not available")
    sys.exit(1)

# Configure boto3 clients
config = Config(region_name=AWS_REGION)
lambda_client = boto3.client("lambda", endpoint_url=LOCALSTACK_ENDPOINT, config=config)
iam_client = boto3.client("iam", endpoint_url=LOCALSTACK_ENDPOINT, config=config)
apigateway = boto3.client("apigateway", endpoint_url=LOCALSTACK_ENDPOINT, config=config)
events_client = boto3.client("events", endpoint_url=LOCALSTACK_ENDPOINT, config=config)

# Create deployment package
print("📦 Packaging Lambda functions...")
deploy_dir = Path(tempfile.mkdtemp())
zip_path = deploy_dir / "lambda-layer.zip"

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    # Add lambda handlers
    lambda_dir = Path("/app/lambda")
    for file in lambda_dir.rglob("*.py"):
        arcname = file.relative_to("/app")
        zipf.write(file, arcname)
    
    # Add triage package
    triage_dir = Path("/app/triage")
    for file in triage_dir.rglob("*.py"):
        arcname = file.relative_to("/app")
        zipf.write(file, arcname)
    
    # Add site-packages (dependencies)
    import site
    site_packages = Path(site.getsitepackages()[0])
    
    # List of packages to include
    packages_to_include = [
        'httpx', 'httpcore', 'h11', 'certifi', 'sniffio', 'anyio',
        'pydantic', 'pydantic_core', 'annotated_types', 'typing_extensions',
        'requests', 'urllib3', 'charset_normalizer', 'idna',
        'boto3', 'botocore', 'jmespath', 'dateutil', 's3transfer'
    ]
    
    for package in packages_to_include:
        package_path = site_packages / package
        if package_path.exists():
            if package_path.is_dir():
                for file in package_path.rglob("*"):
                    if file.is_file() and not file.name.endswith('.pyc'):
                        arcname = file.relative_to(site_packages)
                        zipf.write(file, arcname)
            else:
                # Single file module
                arcname = package_path.relative_to(site_packages)
                zipf.write(package_path, arcname)

print(f"📦 Package created: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)")

# Create IAM role
print("🔐 Creating IAM role...")
role_name = "triage-lambda-role"
try:
    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    print(f"Created role: {role_name}")
except iam_client.exceptions.EntityAlreadyExistsException:
    print(f"Role {role_name} already exists")

role_arn = f"arn:aws:iam::000000000000:role/{role_name}"

# Lambda functions configuration
functions = [
    {
        "name": "triage-health-check",
        "handler": "lambda.handlers.health_check",
        "timeout": 30,
        "memory": 512,
        "env": {
            "LOG_LEVEL": "DEBUG",
            "REGION": "local",
            "AWS_ENDPOINT_URL": LOCALSTACK_ENDPOINT
        }
    },
    {
        "name": "triage-generate-plan",
        "handler": "lambda.handlers.generate_plan",
        "timeout": 300,
        "memory": 1024,
        "env": {
            "LOG_LEVEL": "DEBUG",
            "REGION": "local",
            "AWS_ENDPOINT_URL": LOCALSTACK_ENDPOINT,
            "JIRA_SECRET_NAME": "triage/jira",
            "DATABASE_URL": os.environ.get("DATABASE_URL", "")
        }
    },
    {
        "name": "triage-get-plan",
        "handler": "lambda.handlers.get_plan",
        "timeout": 30,
        "memory": 512,
        "env": {
            "LOG_LEVEL": "DEBUG",
            "REGION": "local",
            "AWS_ENDPOINT_URL": LOCALSTACK_ENDPOINT,
            "DATABASE_URL": os.environ.get("DATABASE_URL", "")
        }
    },
    {
        "name": "triage-approve-plan",
        "handler": "lambda.handlers.approve_plan",
        "timeout": 60,
        "memory": 512,
        "env": {
            "LOG_LEVEL": "DEBUG",
            "REGION": "local",
            "AWS_ENDPOINT_URL": LOCALSTACK_ENDPOINT,
            "DATABASE_URL": os.environ.get("DATABASE_URL", "")
        }
    },
    {
        "name": "triage-decompose-task",
        "handler": "lambda.handlers.decompose_task",
        "timeout": 300,
        "memory": 1024,
        "env": {
            "LOG_LEVEL": "DEBUG",
            "REGION": "local",
            "AWS_ENDPOINT_URL": LOCALSTACK_ENDPOINT,
            "JIRA_SECRET_NAME": "triage/jira",
            "DATABASE_URL": os.environ.get("DATABASE_URL", "")
        }
    },
    {
        "name": "triage-plugin-handler",
        "handler": "lambda.plugin_handler.handler",
        "timeout": 60,
        "memory": 512,
        "env": {
            "LOG_LEVEL": "DEBUG",
            "REGION": "local",
            "AWS_ENDPOINT_URL": LOCALSTACK_ENDPOINT,
            "JIRA_SECRET_NAME": "triage/jira",
            "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
            "PLUGINS_ENABLED": "slack",
            "PLUGIN_CONFIG_PATH": "/app/config/plugins",
            "SLACK_CLIENT_ID": os.environ.get("SLACK_CLIENT_ID", ""),
            "SLACK_CLIENT_SECRET": os.environ.get("SLACK_CLIENT_SECRET", ""),
            "SLACK_SIGNING_SECRET": os.environ.get("SLACK_SIGNING_SECRET", ""),
            "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN", ""),
            "SLACK_OAUTH_REDIRECT_URI": os.environ.get("SLACK_OAUTH_REDIRECT_URI", "http://localhost:8000/plugins/slack/oauth/callback")
        }
    }
]

# Deploy Lambda functions
print("🔧 Deploying Lambda functions...")
with open(zip_path, 'rb') as f:
    zip_content = f.read()

for func in functions:
    try:
        lambda_client.create_function(
            FunctionName=func["name"],
            Runtime="python3.11",
            Role=role_arn,
            Handler=func["handler"],
            Code={"ZipFile": zip_content},
            Timeout=func["timeout"],
            MemorySize=func["memory"],
            Environment={"Variables": func["env"]}
        )
        print(f"✅ Created function: {func['name']}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName=func["name"],
            ZipFile=zip_content
        )
        print(f"✅ Updated function: {func['name']}")

# Create API Gateway
print("🌐 Creating API Gateway...")
try:
    api_response = apigateway.create_rest_api(
        name="triage-api",
        description="TrIAge API Gateway"
    )
    api_id = api_response["id"]
    print(f"Created API: {api_id}")
except Exception:
    # Get existing API
    apis = apigateway.get_rest_apis()
    api_id = next((api["id"] for api in apis["items"] if api["name"] == "triage-api"), None)
    if not api_id:
        print("ERROR: Could not create or find API Gateway")
        sys.exit(1)
    print(f"Using existing API: {api_id}")

# Get root resource
resources = apigateway.get_resources(restApiId=api_id)
root_id = next(r["id"] for r in resources["items"] if r["path"] == "/")

# Helper function to create API resources and methods
def create_resource(parent_id, path_part):
    try:
        resource = apigateway.create_resource(
            restApiId=api_id,
            parentId=parent_id,
            pathPart=path_part
        )
        return resource["id"]
    except Exception:
        resources = apigateway.get_resources(restApiId=api_id)
        return next((r["id"] for r in resources["items"] if r.get("pathPart") == path_part), None)

def create_method(resource_id, http_method, function_name):
    try:
        apigateway.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod=http_method,
            authorizationType="NONE"
        )
    except Exception:
        pass
    
    try:
        apigateway.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod=http_method,
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=f"arn:aws:apigateway:{AWS_REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:{AWS_REGION}:000000000000:function:{function_name}/invocations"
        )
    except Exception:
        pass

# Create API structure
print("📍 Creating API endpoints...")
api_resource = create_resource(root_id, "api")
v1_resource = create_resource(api_resource, "v1")

# /api/v1/health
health_resource = create_resource(v1_resource, "health")
create_method(health_resource, "GET", "triage-health-check")

# /api/v1/plan
plan_resource = create_resource(v1_resource, "plan")
create_method(plan_resource, "POST", "triage-generate-plan")
create_method(plan_resource, "GET", "triage-get-plan")

# /api/v1/plan/{date}
plan_date_resource = create_resource(plan_resource, "{date}")
create_method(plan_date_resource, "GET", "triage-get-plan")

# /api/v1/plan/{date}/approve
approve_resource = create_resource(plan_date_resource, "approve")
create_method(approve_resource, "POST", "triage-approve-plan")

# /api/v1/task
task_resource = create_resource(v1_resource, "task")

# /api/v1/task/{taskId}
task_id_resource = create_resource(task_resource, "{taskId}")

# /api/v1/task/{taskId}/decompose
decompose_resource = create_resource(task_id_resource, "decompose")
create_method(decompose_resource, "POST", "triage-decompose-task")

# Plugin routes
# /plugins
plugins_resource = create_resource(root_id, "plugins")

# /plugins/slack
slack_resource = create_resource(plugins_resource, "slack")

# /plugins/slack/webhook
webhook_resource = create_resource(slack_resource, "webhook")
create_method(webhook_resource, "POST", "triage-plugin-handler")

# /plugins/slack/oauth
oauth_resource = create_resource(slack_resource, "oauth")

# /plugins/slack/oauth/authorize
authorize_resource = create_resource(oauth_resource, "authorize")
create_method(authorize_resource, "GET", "triage-plugin-handler")

# /plugins/slack/oauth/callback
callback_resource = create_resource(oauth_resource, "callback")
create_method(callback_resource, "GET", "triage-plugin-handler")

# /plugins/health
plugins_health_resource = create_resource(plugins_resource, "health")
create_method(plugins_health_resource, "GET", "triage-plugin-handler")

# Deploy API
print("🚀 Deploying API...")
try:
    apigateway.create_deployment(
        restApiId=api_id,
        stageName="local",
        description="Local development deployment"
    )
except Exception as e:
    print(f"Deployment note: {e}")

# Save API ID
api_id_file = Path("/tmp/api-gateway-id.txt")
api_id_file.write_text(api_id)

print("")
print("✅ Deployment complete!")
print("")
print(f"📍 API Gateway ID: {api_id}")
print(f"📍 API Gateway URL: {LOCALSTACK_ENDPOINT}/restapis/{api_id}/local/_user_request_")
print(f"📍 External URL: http://localhost:4566/restapis/{api_id}/local/_user_request_")
print("")
print("Lambda Functions deployed:")
for func in functions:
    print(f"  - {func['name']}")
print("")
print("API Endpoints:")
print("  GET  /api/v1/health")
print("  POST /api/v1/plan")
print("  GET  /api/v1/plan/{date}")
print("  POST /api/v1/plan/{date}/approve")
print("  POST /api/v1/task/{taskId}/decompose")
print("")
print("Plugin Endpoints:")
print("  POST /plugins/slack/webhook")
print("  GET  /plugins/slack/oauth/authorize")
print("  GET  /plugins/slack/oauth/callback")
print("  GET  /plugins/health")
print("")

# Configure EventBridge
print("⏰ Configuring EventBridge scheduled rule...")
schedule_expression = os.environ.get("SCHEDULE_CRON", "cron(0 7 ? * MON-FRI *)")

try:
    events_client.put_rule(
        Name="triage-daily-plan-generation",
        Description="Triggers daily plan generation at 7 AM on weekdays",
        ScheduleExpression=schedule_expression,
        State="ENABLED"
    )
    print("Created EventBridge rule")
except Exception as e:
    print(f"EventBridge rule note: {e}")

# Add Lambda permission
try:
    lambda_client.add_permission(
        FunctionName="triage-generate-plan",
        StatementId="AllowEventBridgeInvoke",
        Action="lambda:InvokeFunction",
        Principal="events.amazonaws.com",
        SourceArn=f"arn:aws:events:{AWS_REGION}:000000000000:rule/triage-daily-plan-generation"
    )
except Exception:
    pass

# Add target
try:
    events_client.put_targets(
        Rule="triage-daily-plan-generation",
        Targets=[{
            "Id": "1",
            "Arn": f"arn:aws:lambda:{AWS_REGION}:000000000000:function:triage-generate-plan",
            "Input": json.dumps({"date": "today"})
        }]
    )
    print("Configured EventBridge target")
except Exception as e:
    print(f"EventBridge target note: {e}")

print("")
print("✅ EventBridge configured!")
print(f"📅 Schedule: {schedule_expression}")
print("🎯 Target: triage-generate-plan Lambda")
print("")

# Cleanup
shutil.rmtree(deploy_dir)
