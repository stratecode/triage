# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Repository Files Guide

## What Should Be in Git?

This document explains which files should be tracked in the repository and which should be ignored.

## ✅ Files to Include (Tracked by Git)

### Root Level Configuration

```
.env.example          # Template for environment variables
.gitignore           # Git ignore rules
LICENSE              # AGPLv3 license
Makefile             # Build automation
README.md            # Main documentation
pyproject.toml       # Python project configuration
requirements.txt     # Python dependencies
template.yaml        # AWS SAM template
uv.lock              # Dependency lock file
icon.png             # Project icon
```

### Source Code

```
triage/              # Main Python package
├── __init__.py
├── models.py
├── jira_client.py
├── task_classifier.py
├── plan_generator.py
├── approval_manager.py
├── background_scheduler.py
└── cli.py
```

### Tests

```
tests/               # Complete test suite
├── unit/
├── property/
└── integration/
```

### Lambda Deployment (Essential Files Only)

```
lambda/
├── handlers.py      # Lambda function handlers
├── authorizer.py    # JWT authorizer
└── requirements.txt # Lambda dependencies
```

**Note**: All dependencies installed in `lambda/` are ignored (boto3, pydantic, etc.) as they are regenerated during build.

### Scripts

```
scripts/
├── README.md
├── deploy.sh
├── setup-secrets.sh
├── setup-iam-permissions.sh
├── generate-token.sh
└── test-api.sh
```

### Documentation

```
docs/                # All documentation files
├── README.md
├── AWS_DEPLOYMENT.md
├── POSTMAN_SETUP.md
├── LAMBDA_FOLDER_EXPLANATION.md
├── postman_collection.json
├── postman_environment.json
└── ... (all other .md files)
```

### Examples

```
examples/            # Demo and validation scripts
├── README.md
├── demo_mvp.py
├── demo_decomposition.py
├── validate_mvp.py
└── ... (all demo scripts)
```

### Slack Bot

```
slack_bot/           # Slack integration component
├── __init__.py
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── ... (all source files)
```

### Kiro Configuration

```
.kiro/
├── specs/           # Project specifications
├── steering/        # Project guidance
└── settings/        # Configuration files
```

## ❌ Files to Ignore (Not in Git)

### Environment & Secrets

```
.env                 # Local environment variables (contains secrets!)
.env.local
.env.*.local
env.json
```

**Why**: Contains sensitive data like API tokens and credentials.

### Python Runtime

```
__pycache__/         # Python bytecode cache
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
```

**Why**: Generated automatically by Python, different per environment.

### Virtual Environments

```
.venv/
venv/
ENV/
```

**Why**: Large, environment-specific, easily recreated with `uv venv`.

### Testing Artifacts

```
.pytest_cache/
.coverage
coverage.json
htmlcov/
.hypothesis/
```

**Why**: Generated during test runs, can be recreated anytime.

### AWS SAM Build

```
.aws-sam/            # SAM build artifacts
samconfig.toml       # SAM deployment config (contains account info)
```

**Why**: Generated during `sam build`, contains account-specific data.

### Lambda Dependencies

```
lambda/boto3/
lambda/pydantic/
lambda/requests/
lambda/markdown/
lambda/jwt/
lambda/triage/       # Copy of main package
... (all other dependencies)
```

**Why**: Installed during build with `uv pip install -r lambda/requirements.txt -t lambda/`. Regenerated on each deployment.

### IDE Files

```
.vscode/
.idea/
*.swp
.DS_Store
```

**Why**: IDE-specific, different per developer.

### Logs

```
*.log
logs/
```

**Why**: Runtime artifacts, not source code.

### Temporary Files

```
*.tmp
*.temp
.triage/
prueba/
```

**Why**: Temporary or test directories.

## 📋 Verification Checklist

### Before Committing

Check that you're not committing:

```bash
# Check for secrets
git diff | grep -i "api_token\|password\|secret"

# Check for large files
git diff --stat

# Check for dependencies
git status | grep -E "boto3|pydantic|\.venv"

# Check for build artifacts
git status | grep -E "\.pyc|__pycache__|\.aws-sam"
```

### After Cloning

Files you need to create locally:

```bash
# 1. Create virtual environment
uv venv

# 2. Install dependencies
source .venv/bin/activate
uv pip install -r requirements.txt

# 3. Create .env from template
cp .env.example .env
# Edit .env with your credentials

# 4. Install Lambda dependencies (for deployment)
cd lambda
uv pip install -r requirements.txt -t .
cd ..
```

## 🔍 Common Mistakes

### ❌ Don't Commit

```bash
# Secrets
git add .env                    # NO!

# Dependencies
git add lambda/boto3/           # NO!
git add .venv/                  # NO!

# Build artifacts
git add .aws-sam/               # NO!
git add __pycache__/            # NO!

# IDE files
git add .vscode/                # NO!
git add .idea/                  # NO!

# Test artifacts
git add .coverage               # NO!
git add htmlcov/                # NO!
```

### ✅ Do Commit

```bash
# Source code
git add triage/                 # YES!
git add tests/                  # YES!

# Configuration templates
git add .env.example            # YES!
git add requirements.txt        # YES!

# Documentation
git add docs/                   # YES!
git add README.md               # YES!

# Scripts
git add scripts/                # YES!

# Lambda essentials
git add lambda/handlers.py      # YES!
git add lambda/authorizer.py    # YES!
git add lambda/requirements.txt # YES!
```

## 📊 Repository Size

Expected repository size (without .git):

```
Source code:        ~500 KB
Tests:              ~300 KB
Documentation:      ~200 KB
Scripts:            ~50 KB
Examples:           ~100 KB
Configuration:      ~50 KB
Total:              ~1.2 MB
```

If your repository is much larger, you might be committing build artifacts or dependencies.

## 🔧 Cleaning Up

If you accidentally committed files that should be ignored:

```bash
# Remove from Git but keep locally
git rm --cached -r .aws-sam/
git rm --cached -r lambda/boto3/
git rm --cached -r .venv/
git rm --cached .env

# Commit the removal
git commit -m "Remove build artifacts and dependencies from Git"

# Verify .gitignore is working
git status
```

## 📝 Summary

### Essential Files (Commit These)
- Source code (`triage/`, `tests/`)
- Configuration templates (`.env.example`, `requirements.txt`)
- Documentation (`docs/`, `README.md`)
- Deployment scripts (`scripts/`)
- Lambda handlers (`lambda/handlers.py`, `lambda/authorizer.py`)
- Project configuration (`pyproject.toml`, `template.yaml`)

### Generated Files (Ignore These)
- Dependencies (`lambda/boto3/`, `.venv/`)
- Build artifacts (`.aws-sam/`, `__pycache__/`)
- Secrets (`.env`)
- Test artifacts (`.coverage`, `.pytest_cache/`)
- IDE files (`.vscode/`, `.idea/`)

## 🎯 Quick Reference

| File/Folder | Include? | Why |
|------------|----------|-----|
| `triage/` | ✅ Yes | Source code |
| `tests/` | ✅ Yes | Test suite |
| `docs/` | ✅ Yes | Documentation |
| `scripts/` | ✅ Yes | Deployment scripts |
| `lambda/handlers.py` | ✅ Yes | Lambda code |
| `lambda/boto3/` | ❌ No | Dependency (regenerated) |
| `lambda/triage/` | ❌ No | Copy (regenerated) |
| `.env.example` | ✅ Yes | Template |
| `.env` | ❌ No | Contains secrets |
| `.venv/` | ❌ No | Virtual environment |
| `.aws-sam/` | ❌ No | Build artifacts |
| `__pycache__/` | ❌ No | Python cache |
| `.coverage` | ❌ No | Test artifacts |

---

**Remember**: When in doubt, check if the file can be regenerated. If yes, it probably shouldn't be in Git.
