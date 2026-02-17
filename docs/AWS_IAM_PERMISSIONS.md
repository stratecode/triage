# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# AWS IAM Permissions Required

## Overview

Para desplegar TrIAge en AWS, el usuario IAM necesita permisos para crear y gestionar los siguientes servicios:

- **CloudFormation** - Crear y gestionar stacks
- **Lambda** - Crear y configurar funciones
- **API Gateway** - Crear y configurar APIs REST
- **IAM** - Crear roles y políticas para Lambda
- **S3** - Almacenar artefactos de deployment
- **Secrets Manager** - Gestionar secretos
- **CloudWatch Logs** - Crear log groups
- **EventBridge** - Crear reglas programadas

## Política IAM Recomendada

### Opción 1: Política Mínima (Recomendada para Producción)

Crea una política IAM personalizada con estos permisos:

```json
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
        "arn:aws:iam::*:role/triage-api-*"
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
```

### Opción 2: Políticas AWS Gestionadas (Más Simple, Menos Seguro)

Para desarrollo rápido, puedes usar estas políticas gestionadas por AWS:

1. **AWSCloudFormationFullAccess** - Para CloudFormation
2. **AWSLambda_FullAccess** - Para Lambda
3. **AmazonAPIGatewayAdministrator** - Para API Gateway
4. **IAMFullAccess** - Para crear roles (⚠️ muy permisivo)
5. **SecretsManagerReadWrite** - Para Secrets Manager
6. **CloudWatchLogsFullAccess** - Para logs
7. **AmazonEventBridgeFullAccess** - Para EventBridge

⚠️ **Advertencia**: Esta opción da más permisos de los necesarios. Úsala solo para desarrollo.

### Opción 3: PowerUser (Desarrollo Rápido)

Para desarrollo, puedes usar la política gestionada:

- **PowerUserAccess** - Acceso completo excepto gestión de usuarios IAM

Luego añade esta política inline para IAM:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
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
        "iam:GetRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/triage-api-*"
    }
  ]
}
```

## Cómo Aplicar los Permisos

### Método 1: AWS Console (Interfaz Web)

1. **Ir a IAM Console**
   - https://console.aws.amazon.com/iam/

2. **Seleccionar el usuario**
   - Ir a "Users"
   - Buscar y seleccionar tu usuario

3. **Añadir política personalizada**
   - Click en "Add permissions" → "Create inline policy"
   - Click en "JSON"
   - Pegar la política de la Opción 1
   - Nombrarla: `TriageDeploymentPolicy`
   - Click en "Create policy"

### Método 2: AWS CLI

#### Crear la política

1. **Guardar la política en un archivo**
   ```bash
   cat > triage-deployment-policy.json << 'EOF'
   {
     "Version": "2012-10-17",
     "Statement": [
       ... (copiar la política completa de arriba)
     ]
   }
   EOF
   ```

2. **Crear la política**
   ```bash
   aws iam create-policy \
     --profile stratecode \
     --policy-name TriageDeploymentPolicy \
     --policy-document file://triage-deployment-policy.json \
     --description "Permisos para desplegar TrIAge en AWS"
   ```

3. **Obtener el ARN de la política**
   ```bash
   POLICY_ARN=$(aws iam list-policies \
     --profile stratecode \
     --query 'Policies[?PolicyName==`TriageDeploymentPolicy`].Arn' \
     --output text)
   
   echo $POLICY_ARN
   ```

4. **Adjuntar la política al usuario**
   ```bash
   aws iam attach-user-policy \
     --profile stratecode \
     --user-name TU_USUARIO \
     --policy-arn $POLICY_ARN
   ```

### Método 3: Script Automatizado

He creado un script para facilitar esto:

```bash
./scripts/setup-iam-permissions.sh TU_USUARIO
```

## Verificar Permisos

### Verificar que el usuario tiene los permisos

```bash
# Ver políticas adjuntas
aws iam list-attached-user-policies \
  --profile stratecode \
  --user-name TU_USUARIO

# Ver políticas inline
aws iam list-user-policies \
  --profile stratecode \
  --user-name TU_USUARIO
```

### Probar acceso

```bash
# Verificar identidad
aws sts get-caller-identity --profile stratecode --region eu-south-2

# Probar acceso a CloudFormation
aws cloudformation list-stacks --profile stratecode --region eu-south-2

# Probar acceso a Secrets Manager
aws secretsmanager list-secrets --profile stratecode --region eu-south-2
```

## Permisos por Servicio

### CloudFormation
- Crear, actualizar y eliminar stacks
- Describir stacks y eventos
- Crear y ejecutar changesets

### Lambda
- Crear y eliminar funciones
- Actualizar código y configuración
- Invocar funciones
- Gestionar permisos

### API Gateway
- Crear y configurar APIs REST
- Gestionar recursos, métodos y deployments
- Configurar autorizadores

### IAM
- Crear roles para Lambda
- Adjuntar políticas a roles
- PassRole para que Lambda pueda asumir roles

### S3
- Crear buckets para artefactos SAM
- Subir y descargar objetos
- Gestionar políticas de bucket

### Secrets Manager
- Crear y actualizar secretos
- Leer valores de secretos
- Eliminar secretos

### CloudWatch Logs
- Crear log groups
- Configurar retención
- Leer logs

### EventBridge
- Crear reglas programadas
- Configurar targets (Lambda)
- Habilitar/deshabilitar reglas

## Troubleshooting

### Error: "User is not authorized to perform: cloudformation:CreateStack"

**Solución**: El usuario no tiene permisos de CloudFormation. Aplica la política de la Opción 1.

### Error: "User is not authorized to perform: iam:PassRole"

**Solución**: El usuario necesita permiso `iam:PassRole` para que Lambda pueda asumir roles.

### Error: "Access Denied" al crear secretos

**Solución**: El usuario necesita permisos de Secrets Manager. Verifica la sección `SecretsManagerAccess`.

### Error: "Cannot create S3 bucket"

**Solución**: SAM necesita crear un bucket para artefactos. Verifica permisos de S3.

## Recomendaciones de Seguridad

1. **Usa la Opción 1 (Política Mínima)** para producción
2. **Limita por recursos** usando ARNs específicos
3. **Usa MFA** para operaciones sensibles
4. **Audita regularmente** con AWS CloudTrail
5. **Rota credenciales** periódicamente
6. **Usa roles IAM** en lugar de usuarios cuando sea posible

## Política para CI/CD

Si vas a usar CI/CD (GitHub Actions, GitLab CI, etc.), usa esta política más restrictiva:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DescribeStacks",
        "cloudformation:CreateChangeSet",
        "cloudformation:ExecuteChangeSet"
      ],
      "Resource": "arn:aws:cloudformation:eu-south-2:*:stack/triage-api-prod/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction"
      ],
      "Resource": "arn:aws:lambda:eu-south-2:*:function:triage-api-prod-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
    }
  ]
}
```

## Resumen

Para desplegar TrIAge necesitas permisos en:
- ✅ CloudFormation (crear stacks)
- ✅ Lambda (crear funciones)
- ✅ API Gateway (crear APIs)
- ✅ IAM (crear roles)
- ✅ S3 (almacenar artefactos)
- ✅ Secrets Manager (gestionar secretos)
- ✅ CloudWatch Logs (crear log groups)
- ✅ EventBridge (crear reglas)

**Recomendación**: Usa la Opción 1 (Política Mínima) para máxima seguridad.

## Siguiente Paso

Después de aplicar los permisos:

```bash
# Verificar acceso
aws sts get-caller-identity --profile stratecode --region eu-south-2

# Validar deployment
./scripts/validate-deployment.sh

# Desplegar
./scripts/first-deploy.sh dev
```
