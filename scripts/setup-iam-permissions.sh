#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

PROFILE="stratecode"
REGION="eu-south-2"
USERNAME="${1}"

if [ -z "$USERNAME" ]; then
    echo "Usage: ./scripts/setup-iam-permissions.sh <IAM_USERNAME>"
    echo ""
    echo "Example:"
    echo "  ./scripts/setup-iam-permissions.sh juan.perez"
    echo ""
    exit 1
fi

echo "🔐 Configurando permisos IAM para TrIAge"
echo "Usuario: $USERNAME"
echo "Profile: $PROFILE"
echo "Región: $REGION"
echo ""

# Verificar que el usuario existe
echo "1️⃣ Verificando usuario IAM..."
if aws iam get-user --profile $PROFILE --user-name $USERNAME &> /dev/null; then
    echo "✅ Usuario $USERNAME encontrado"
else
    echo "❌ Usuario $USERNAME no encontrado"
    echo "   Verifica el nombre del usuario en IAM Console"
    exit 1
fi
echo ""

# Crear archivo de política temporal
echo "2️⃣ Creando política IAM..."
POLICY_FILE=$(mktemp)
cat > $POLICY_FILE << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationAccess",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:ValidateTemplate",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListStacks"
      ],
      "Resource": [
        "arn:aws:cloudformation:eu-south-2:*:stack/triage-api-*/*",
        "arn:aws:cloudformation:eu-south-2:*:stack/aws-sam-cli-managed-default/*"
      ]
    },
    {
      "Sid": "LambdaAccess",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:ListFunctions",
        "lambda:ListVersionsByFunction",
        "lambda:PublishVersion",
        "lambda:CreateAlias",
        "lambda:DeleteAlias",
        "lambda:GetAlias",
        "lambda:UpdateAlias",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:InvokeFunction",
        "lambda:TagResource",
        "lambda:UntagResource"
      ],
      "Resource": [
        "arn:aws:lambda:eu-south-2:*:function:triage-api-*"
      ]
    },
    {
      "Sid": "APIGatewayAccess",
      "Effect": "Allow",
      "Action": [
        "apigateway:GET",
        "apigateway:POST",
        "apigateway:PUT",
        "apigateway:DELETE",
        "apigateway:PATCH"
      ],
      "Resource": [
        "arn:aws:apigateway:eu-south-2::/restapis",
        "arn:aws:apigateway:eu-south-2::/restapis/*"
      ]
    },
    {
      "Sid": "IAMRoleAccess",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:TagRole",
        "iam:UntagRole"
      ],
      "Resource": [
        "arn:aws:iam::*:role/triage-api-*",
        "arn:aws:iam::*:role/aws-sam-cli-managed-default-*"
      ]
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecret",
        "secretsmanager:DeleteSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:ListSecrets",
        "secretsmanager:TagResource"
      ],
      "Resource": [
        "arn:aws:secretsmanager:eu-south-2:*:secret:/*/triage/*"
      ]
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
        "logs:TagLogGroup",
        "logs:UntagLogGroup",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "logs:FilterLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:eu-south-2:*:log-group:/aws/lambda/triage-api-*"
      ]
    },
    {
      "Sid": "EventBridgeAccess",
      "Effect": "Allow",
      "Action": [
        "events:PutRule",
        "events:DeleteRule",
        "events:DescribeRule",
        "events:EnableRule",
        "events:DisableRule",
        "events:PutTargets",
        "events:RemoveTargets",
        "events:TagResource",
        "events:UntagResource"
      ],
      "Resource": [
        "arn:aws:events:eu-south-2:*:rule/triage-api-*"
      ]
    },
    {
      "Sid": "STSAccess",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
EOF

echo "✅ Política creada en: $POLICY_FILE"
echo ""

# Crear la política en AWS
echo "3️⃣ Creando política en AWS IAM..."
POLICY_NAME="TriageDeploymentPolicy"

# Verificar si la política ya existe
EXISTING_POLICY=$(aws iam list-policies \
    --profile $PROFILE \
    --query "Policies[?PolicyName=='$POLICY_NAME'].Arn" \
    --output text)

if [ -n "$EXISTING_POLICY" ]; then
    echo "ℹ️  Política $POLICY_NAME ya existe"
    POLICY_ARN=$EXISTING_POLICY
else
    POLICY_ARN=$(aws iam create-policy \
        --profile $PROFILE \
        --policy-name $POLICY_NAME \
        --policy-document file://$POLICY_FILE \
        --description "Permisos para desplegar TrIAge en AWS" \
        --query 'Policy.Arn' \
        --output text)
    echo "✅ Política creada: $POLICY_ARN"
fi
echo ""

# Adjuntar la política al usuario
echo "4️⃣ Adjuntando política al usuario..."
if aws iam attach-user-policy \
    --profile $PROFILE \
    --user-name $USERNAME \
    --policy-arn $POLICY_ARN 2>/dev/null; then
    echo "✅ Política adjuntada al usuario $USERNAME"
else
    echo "ℹ️  Política ya estaba adjuntada al usuario"
fi
echo ""

# Limpiar archivo temporal
rm $POLICY_FILE

# Verificar permisos
echo "5️⃣ Verificando permisos..."
echo ""
echo "Políticas adjuntas al usuario:"
aws iam list-attached-user-policies \
    --profile $PROFILE \
    --user-name $USERNAME \
    --query 'AttachedPolicies[*].[PolicyName,PolicyArn]' \
    --output table
echo ""

# Resumen
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Permisos IAM configurados correctamente"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Usuario:  $USERNAME"
echo "Política: $POLICY_NAME"
echo "ARN:      $POLICY_ARN"
echo ""
echo "Permisos otorgados para:"
echo "  ✅ CloudFormation (crear stacks)"
echo "  ✅ Lambda (crear funciones)"
echo "  ✅ API Gateway (crear APIs)"
echo "  ✅ IAM (crear roles)"
echo "  ✅ S3 (almacenar artefactos)"
echo "  ✅ Secrets Manager (gestionar secretos)"
echo "  ✅ CloudWatch Logs (crear log groups)"
echo "  ✅ EventBridge (crear reglas)"
echo ""
echo "Siguiente paso:"
echo "  ./scripts/validate-deployment.sh"
echo "  ./scripts/first-deploy.sh dev"
echo ""
