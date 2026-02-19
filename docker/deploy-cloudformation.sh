#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

echo "🚀 Deploying CloudFormation stack to LocalStack..."

STACK_NAME="triage-api-local"
REGION="eu-south-2"
ENDPOINT="http://localstack:4566"

# Package Lambda functions
echo "📦 Packaging Lambda functions..."

# Create a clean temporary directory for packaging
rm -rf /tmp/lambda-build
mkdir -p /tmp/lambda-build

# Copy only the Lambda handler files (not dependencies)
cp /app/lambda/handlers.py /tmp/lambda-build/
cp /app/lambda/plugin_handler.py /tmp/lambda-build/
cp /app/lambda/event_processor.py /tmp/lambda-build/
cp /app/lambda/authorizer.py /tmp/lambda-build/

# Copy the triage module
cp -r /app/triage /tmp/lambda-build/

# Install only the required dependencies (excluding boto3/botocore which Lambda provides)
cd /tmp/lambda-build
pip install --target . --no-deps \
  requests \
  urllib3 \
  charset-normalizer \
  pydantic \
  pydantic-core \
  annotated-types \
  typing-extensions \
  python-dotenv \
  httpx \
  httpcore \
  certifi \
  idna \
  anyio \
  sniffio \
  h11 \
  cryptography \
  cffi \
  pycparser \
  -q

# Create the zip package
zip -q -r /tmp/lambda-package.zip . \
  -x "*.pyc" \
  -x "__pycache__/*" \
  -x "*/__pycache__/*"

echo "✅ Lambda package created ($(du -h /tmp/lambda-package.zip | cut -f1))"

# Upload to S3 using boto3
echo "📤 Uploading Lambda package to S3..."
cd /app
python3 << 'PYEOF'
import boto3
from botocore.config import Config

config = Config(region_name='eu-south-2')
s3 = boto3.client('s3', endpoint_url='http://localstack:4566', config=config)

# Create bucket
try:
    s3.create_bucket(
        Bucket='triage-lambda-code',
        CreateBucketConfiguration={'LocationConstraint': 'eu-south-2'}
    )
    print("Created S3 bucket")
except Exception as e:
    print(f"Bucket exists or error: {e}")

# Upload Lambda package
with open('/tmp/lambda-package.zip', 'rb') as f:
    s3.put_object(Bucket='triage-lambda-code', Key='lambda.zip', Body=f)
    print("Uploaded Lambda package")
PYEOF

# Update template to use S3 location
echo "📝 Preparing CloudFormation template..."
cat > /tmp/template-local.yaml << 'EOF'
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

AWSTemplateFormatVersion: '2010-09-09'
Description: TrIAge - AI Secretary API (LocalStack)

Parameters:
  Environment:
    Type: String
    Default: local

Resources:
  # API Gateway
  TriageApi:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: !Sub '${AWS::StackName}-api'
      Description: TrIAge API
      EndpointConfiguration:
        Types:
          - REGIONAL

  # Lambda Execution Role
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: SecretsAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - secretsmanager:GetSecretValue
                  - ssm:GetParameter
                  - ssm:GetParameters
                Resource: '*'

  # JWT Authorizer Lambda
  AuthorizerFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${AWS::StackName}-Authorizer'
      Runtime: python3.11
      Handler: authorizer.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        S3Bucket: triage-lambda-code
        S3Key: lambda.zip
      Environment:
        Variables:
          JWT_SECRET_NAME: /local/triage/jwt-secret
          LOG_LEVEL: INFO

  AuthorizerPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref AuthorizerFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${TriageApi}/*'

  # API Gateway Authorizer
  ApiAuthorizer:
    Type: AWS::ApiGateway::Authorizer
    Properties:
      Name: JWTAuthorizer
      Type: REQUEST
      AuthorizerUri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${AuthorizerFunction.Arn}/invocations'
      AuthorizerResultTtlInSeconds: 300
      IdentitySource: method.request.header.Authorization
      RestApiId: !Ref TriageApi

  # Generate Plan Lambda
  GeneratePlanFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${AWS::StackName}-GeneratePlan'
      Runtime: python3.11
      Handler: handlers.generate_plan
      Role: !GetAtt LambdaExecutionRole.Arn
      Timeout: 60
      MemorySize: 512
      Code:
        S3Bucket: triage-lambda-code
        S3Key: lambda.zip
      Environment:
        Variables:
          LOG_LEVEL: INFO
          JIRA_SECRET_NAME: triage/jira

  GeneratePlanPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref GeneratePlanFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${TriageApi}/*'

  # Health Check Lambda
  HealthCheckFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${AWS::StackName}-HealthCheck'
      Runtime: python3.11
      Handler: handlers.health_check
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        S3Bucket: triage-lambda-code
        S3Key: lambda.zip
      Environment:
        Variables:
          LOG_LEVEL: INFO

  HealthCheckPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref HealthCheckFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${TriageApi}/*'

  # Plugin Handler Lambda
  PluginHandlerFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${AWS::StackName}-PluginHandler'
      Runtime: python3.11
      Handler: plugin_handler.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Timeout: 30
      MemorySize: 512
      Code:
        S3Bucket: triage-lambda-code
        S3Key: lambda.zip
      Environment:
        Variables:
          LOG_LEVEL: INFO
          JIRA_SECRET_NAME: triage/jira
          PLUGINS_ENABLED: slack
          SLACK_SIGNING_SECRET_PARAM: /triage/slack/signing_secret

  PluginHandlerPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref PluginHandlerFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${TriageApi}/*'

  # API Resource (/api)
  ApiResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !GetAtt TriageApi.RootResourceId
      PathPart: api

  # V1 Resource (/api/v1)
  V1Resource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref ApiResource
      PathPart: v1

  # Health Check Resource (/api/v1/health)
  HealthResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref V1Resource
      PathPart: health

  HealthCheckMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref TriageApi
      ResourceId: !Ref HealthResource
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${HealthCheckFunction.Arn}/invocations'

  # Plan Resource (/api/v1/plan)
  PlanResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref V1Resource
      PathPart: plan

  PlanPostMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref TriageApi
      ResourceId: !Ref PlanResource
      HttpMethod: POST
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${GeneratePlanFunction.Arn}/invocations'

  # Plugins Resource
  PluginsResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !GetAtt TriageApi.RootResourceId
      PathPart: plugins

  PluginHealthResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref PluginsResource
      PathPart: health

  PluginHealthMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref TriageApi
      ResourceId: !Ref PluginHealthResource
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${PluginHandlerFunction.Arn}/invocations'

  # Slack Resource
  SlackResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref PluginsResource
      PathPart: slack

  SlackWebhookResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref SlackResource
      PathPart: webhook

  SlackWebhookMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref TriageApi
      ResourceId: !Ref SlackWebhookResource
      HttpMethod: POST
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${PluginHandlerFunction.Arn}/invocations'

  # Slack OAuth
  SlackOAuthResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref SlackResource
      PathPart: oauth

  SlackOAuthAuthorizeResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref SlackOAuthResource
      PathPart: authorize

  SlackOAuthAuthorizeMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref TriageApi
      ResourceId: !Ref SlackOAuthAuthorizeResource
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${PluginHandlerFunction.Arn}/invocations'

  SlackOAuthCallbackResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref TriageApi
      ParentId: !Ref SlackOAuthResource
      PathPart: callback

  SlackOAuthCallbackMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref TriageApi
      ResourceId: !Ref SlackOAuthCallbackResource
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${PluginHandlerFunction.Arn}/invocations'

  # API Gateway Deployment
  ApiDeployment:
    Type: AWS::ApiGateway::Deployment
    DependsOn:
      - HealthCheckMethod
      - PlanPostMethod
      - PluginHealthMethod
      - SlackWebhookMethod
      - SlackOAuthAuthorizeMethod
      - SlackOAuthCallbackMethod
    Properties:
      RestApiId: !Ref TriageApi
      StageName: !Ref Environment

Outputs:
  ApiId:
    Description: API Gateway ID
    Value: !Ref TriageApi
    Export:
      Name: !Sub '${AWS::StackName}-ApiId'

  ApiUrl:
    Description: API Gateway URL
    Value: !Sub 'https://${TriageApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}'
    Export:
      Name: !Sub '${AWS::StackName}-ApiUrl'

  AuthorizerFunctionArn:
    Description: Authorizer Lambda ARN
    Value: !GetAtt AuthorizerFunction.Arn
    Export:
      Name: !Sub '${AWS::StackName}-AuthorizerArn'

  GeneratePlanFunctionArn:
    Description: Generate Plan Lambda ARN
    Value: !GetAtt GeneratePlanFunction.Arn
    Export:
      Name: !Sub '${AWS::StackName}-GeneratePlanArn'

  PluginHandlerFunctionArn:
    Description: Plugin Handler Lambda ARN
    Value: !GetAtt PluginHandlerFunction.Arn
    Export:
      Name: !Sub '${AWS::StackName}-PluginHandlerArn'
EOF

# Deploy stack
echo "🚀 Deploying CloudFormation stack..."
python3 << 'PYEOF'
import boto3
import json
from botocore.config import Config

config = Config(region_name='eu-south-2')
cfn = boto3.client('cloudformation', endpoint_url='http://localstack:4566', config=config)
lambda_client = boto3.client('lambda', endpoint_url='http://localstack:4566', config=config)

with open('/tmp/template-local.yaml', 'r') as f:
    template_body = f.read()

try:
    cfn.create_stack(
        StackName='triage-api-local',
        TemplateBody=template_body,
        Capabilities=['CAPABILITY_IAM'],
        Parameters=[{'ParameterKey': 'Environment', 'ParameterValue': 'local'}]
    )
    print("Stack creation initiated")
    
    # Wait for stack creation
    waiter = cfn.get_waiter('stack_create_complete')
    waiter.wait(StackName='triage-api-local')
    print("Stack created successfully")
except cfn.exceptions.AlreadyExistsException:
    print("Stack already exists, updating Lambda code directly...")
    
    # Update Lambda function code directly
    with open('/tmp/lambda-package.zip', 'rb') as f:
        zip_content = f.read()
    
    for function_name in ['triage-api-local-HealthCheck', 'triage-api-local-PluginHandler', 'triage-api-local-Authorizer', 'triage-api-local-GeneratePlan']:
        try:
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content
            )
            print(f"Updated {function_name} code")
        except Exception as e:
            print(f"Error updating {function_name}: {e}")
    
    print("Lambda functions updated successfully")
except Exception as e:
    print(f"Error: {e}")
    raise
PYEOF

# Get API Gateway ID
echo "✅ Getting API Gateway ID..."
python3 << 'PYEOF'
import boto3
from botocore.config import Config

config = Config(region_name='eu-south-2')
cfn = boto3.client('cloudformation', endpoint_url='http://localstack:4566', config=config)

response = cfn.describe_stacks(StackName='triage-api-local')
outputs = response['Stacks'][0]['Outputs']
api_id = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'ApiId'), None)

if api_id:
    with open('/tmp/api_gateway_id.txt', 'w') as f:
        f.write(api_id)
    print(f"✅ API Gateway ID: {api_id}")
else:
    print("❌ API Gateway ID not found in outputs")
PYEOF

echo "✅ CloudFormation deployment complete!"
