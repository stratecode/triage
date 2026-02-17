# TrIAge

Execution support system for senior technical professionals working in high-interruption, multi-project environments.

## Overview

TrIAge reduces cognitive load by generating focused daily plans with a maximum of 3 real priorities. It treats JIRA as the single source of truth and operates asynchronously to generate daily action plans.

## Core Principles

- **JIRA as Single Source of Truth**: No persistent local state; all task data lives in JIRA
- **Human Control**: Every plan and action requires explicit user approval
- **Cognitive Load Minimization**: Maximum 3 priorities per day, grouped administrative tasks
- **Daily Closure Focus**: All priority tasks must be closable within one working day
- **Asynchronous Operation**: Background polling and plan generation without blocking the user

## Key Features

### ✅ Implemented (Complete MVP)

- **Daily Plan Generation**: Up to 3 priority tasks automatically selected
- **Intelligent Task Classification**: Detects dependencies, estimates effort, identifies administrative tasks
- **Administrative Block**: Groups low cognitive load tasks (maximum 90 minutes)
- **Closure Tracking**: Tracks daily completion rate
- **Long-Running Task Decomposition**: Proposes one-day subtasks for multi-day tasks
- **Re-planning**: Handles blocking tasks that interrupt the current plan
- **Background Scheduler**: Automatic polling and scheduled plan generation
- **Approval System**: Full user control over plans and decompositions
- **Complete Logging**: Configurable logging system for debugging and monitoring
- **JIRA Integration**: Robust client with error handling, retries, and rate limiting

### 🎯 Use Cases

1. **Morning Planning**: Generate your daily plan in seconds
2. **Interruption Management**: Automatically re-plan when blockers appear
3. **Large Tasks**: Decompose multi-day projects into manageable units
4. **Overhead Reduction**: Group administrative tasks into dedicated blocks
5. **Progress Tracking**: Monitor your daily closure rate

## Deployment Options

TrIAge can be deployed in two ways:

### 1. Docker Local (Recommended for Development)

Run a complete replica of the AWS stack locally for debugging and testing.

**Quick Start:**
```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your JIRA credentials

# 2. Start the stack
make docker-up

# 3. Test the API
make docker-test

# 4. View logs
make docker-logs
# Or in browser: http://localhost:8080
```

**Features:**
- Complete AWS stack replica (API Gateway + Lambda + EventBridge)
- Hot-reload for code changes
- Real-time log viewing
- No cold starts
- JWT token generation for testing

**Documentation:** [Docker Local Setup Guide](docs/DOCKER_LOCAL_SETUP.md)

### 2. AWS Serverless (Recommended for Production)

Deploy as a serverless API on AWS Lambda + API Gateway.

**Quick Start:**
```bash
# 1. Setup IAM permissions (first time only)
./scripts/setup-iam-permissions.sh YOUR_IAM_USERNAME

# 2. Configure JIRA credentials
cp .env.example .env
# Edit .env with your JIRA credentials

# 3. Deploy
./scripts/deploy.sh dev

# 4. Setup secrets
./scripts/setup-secrets.sh dev

# 5. Generate authentication token
./scripts/generate-token.sh dev

# 6. Test the API
./scripts/test-api.sh <API_URL> <TOKEN>
```

See [scripts/README.md](scripts/README.md) for detailed script documentation, or [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md) for complete deployment guide.

### 2. Local Installation

Run TrIAge locally on your machine.

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- JIRA account with API token
- (For AWS deployment) AWS CLI configured with profile `stratecode`

### Quick Install

```bash
# Clone the repository
git clone https://github.com/your-org/triage.git
cd triage

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate  # On Windows

# Install dependencies
uv pip install -r requirements.txt

# Install in development mode
uv pip install -e .
```

### Configuration

The application automatically loads environment variables from a `.env` file in the project root.

1. **Copy the example file**:
```bash
cp .env.example .env
```

2. **Edit `.env` with your JIRA credentials**:
```bash
# ============================================================================
# REQUIRED CONFIGURATION
# ============================================================================

# Your JIRA instance URL (without trailing slash)
JIRA_BASE_URL=https://your-company.atlassian.net

# Your JIRA email
JIRA_EMAIL=your-email@company.com

# JIRA API token (generate at: https://id.atlassian.com/manage-profile/security/api-tokens)
JIRA_API_TOKEN=your-token-here

# ============================================================================
# OPTIONAL CONFIGURATION
# ============================================================================

# Filter by specific project (e.g., PROJ to see only PROJ-123, PROJ-456, etc.)
# Leave empty to see tasks from all projects
JIRA_PROJECT=

# Administrative block schedule (HH:MM format)
ADMIN_TIME_START=14:00
ADMIN_TIME_END=15:30
```

3. **Generate a JIRA API token**:
   - Visit: https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token"
   - Copy the token and paste it into `JIRA_API_TOKEN`

**Note**: The `.env` file is automatically loaded when running any `triage` command. You don't need to export variables manually.

#### Project Filtering

If you configure `JIRA_PROJECT`, only tasks from that specific project will be included in your daily plans. Useful if you work on multiple projects but want to focus on one at a time.

Examples:
- `JIRA_PROJECT=IAOW` - Only shows tasks like IAOW-123, IAOW-456, etc.
- Leave empty or unconfigured to see tasks from all projects

## Usage

### Main Command: `triage`

Once installed, you can use the `triage` command from anywhere:

```bash
triage --help
```

### Available Commands

#### 1. Generate Daily Plan

Generates a daily plan with up to 3 priorities and grouped administrative tasks.

```bash
# Basic usage - displays plan in console
triage generate-plan

# Save plan to file
triage generate-plan -o daily-plan.md
triage generate-plan --output plan-2026-01-23.md

# Include previous day's closure rate
triage generate-plan --closure-rate 0.67

# Debug mode with detailed logging
triage generate-plan --debug

# Combination of options
triage generate-plan --debug -o plan.md --closure-rate 0.75
```

**Options**:
- `-o, --output PATH`: Save plan to file (default: stdout)
- `--closure-rate FLOAT`: Previous day's closure rate (0.0-1.0)
- `--debug`: Enable detailed logging for debugging

**Examples**:

```bash
# Simple plan to console
$ triage generate-plan
Connecting to JIRA...
Fetching and classifying tasks...

# Daily Plan - 2026-01-23

## Today's Priorities
1. **[PROJ-123] Implement user authentication**
   - Effort: 8.0 hours
   - Type: Story
...

# Plan with debug for troubleshooting
$ triage generate-plan --debug 2> debug.log
# Detailed logs saved to debug.log

# Daily plan with progress tracking
$ triage generate-plan --closure-rate 0.67 -o today.md
✓ Generated plan for 2026-01-23
  Priorities: 3
  Admin tasks: 2
  Other tasks: 8
```

### Example Output

```markdown
# Daily Plan - 2026-01-23

## Previous Day
- Closure Rate: 2/3 tasks completed (67%)

## Today's Priorities

1. **[PROJ-123] Implement user authentication**
   - Effort: 8.0 hours
   - Type: Story
   - Priority: High

2. **[PROJ-124] Fix login bug**
   - Effort: 4.0 hours
   - Type: Bug
   - Priority: High

3. **[PROJ-125] Update API documentation**
   - Effort: 6.0 hours
   - Type: Task
   - Priority: Medium

## Administrative Block (14:00-15:30)

- [ ] [PROJ-126] Email responses
- [ ] [PROJ-127] Weekly report
- [ ] [PROJ-128] Code review approvals

## Other Active Tasks (For Reference)

- [PROJ-129] Waiting on external team (blocked by dependencies)
- [PROJ-130] Multi-day feature (decomposition needed)
- [PROJ-131] Database migration (long-running)
```

### Typical Workflow

```bash
# 1. Morning: Generate daily plan
triage generate-plan -o today.md

# 2. Review and approve the plan
cat today.md

# 3. During the day: If a blocker appears, regenerate
triage generate-plan -o today-updated.md

# 4. End of day: Calculate closure rate
# (2 out of 3 tasks completed = 0.67)

# 5. Next day: Use previous closure rate
triage generate-plan --closure-rate 0.67 -o tomorrow.md
```

### Example Scripts

The project includes several demonstration scripts in `examples/`:

```bash
# Complete MVP demo
python examples/demo_mvp.py

# Task decomposition demo
python examples/demo_decomposition.py

# Re-planning demo
python examples/demo_replanning.py

# Closure tracking demo
python examples/demo_closure_tracking.py

# Logging demo
python examples/demo_logging.py

# MVP validation
python examples/validate_mvp.py

# JIRA connection diagnostics
python examples/diagnose-jira-connection.py
```

## Troubleshooting

### JIRA Connection Issues

If you encounter connection errors:

1. **Run the diagnostic tool**:
   ```bash
   python examples/diagnose-jira-connection.py
   ```
   
   This tool verifies:
   - Network connectivity
   - Authentication
   - API version
   - User permissions

2. **HTTP 410 Error**: Fixed in the latest version. The application now uses the new JIRA API endpoint (`/rest/api/3/search/jql`). See [docs/JIRA_API_MIGRATION.md](docs/JIRA_API_MIGRATION.md) for details.

3. **Authentication Errors (401/403)**: 
   - Verify that `JIRA_EMAIL` is correct
   - Ensure `JIRA_API_TOKEN` is valid
   - Generate a new token at: https://id.atlassian.com/manage-profile/security/api-tokens
   - Verify the token has necessary permissions

4. **Connection Timeout**:
   - Check your internet connection
   - Confirm `JIRA_BASE_URL` is correct (without trailing slash)
   - Ensure JIRA service is available
   - Verify no firewall is blocking the connection

5. **Rate Limiting (429)**:
   - The application automatically retries with exponential backoff
   - If it persists, wait a few minutes before retrying
   - Consider reducing polling frequency

6. **Tasks Not Appearing**:
   - Check the `JIRA_PROJECT` filter in `.env`
   - Confirm tasks are assigned to you
   - Verify tasks are not resolved
   - Use `--debug` to see the exact JQL query

### Logging and Debugging

To get detailed information about operation:

```bash
# Enable debug logging
triage generate-plan --debug

# Save logs to file
triage generate-plan --debug 2> triage.log

# View logs in real-time
triage generate-plan --debug 2>&1 | tee triage.log
```

See [docs/LOGGING_GUIDE.md](docs/LOGGING_GUIDE.md) for complete logging guide.

### Common Issues

**"No priority-eligible tasks found"**:
- All your tasks have dependencies or are >1 day
- Use `--debug` to see why tasks are not eligible
- Consider decomposing large tasks

**"JIRA_BASE_URL environment variable is required"**:
- Ensure you have a `.env` file in the project root
- Verify the file contains `JIRA_BASE_URL=...`
- The `.env` file must be in the same directory where you run `triage`

**"Invalid closure rate"**:
- Value must be between 0.0 and 1.0
- Example: `--closure-rate 0.67` (67% of tasks completed)

### Getting Help

```bash
# View general help
triage --help

# View command-specific help
triage generate-plan --help

# View version
triage --version
```

For more information, see documentation in `docs/`:
- [LOGGING_GUIDE.md](docs/LOGGING_GUIDE.md) - Logging guide
- [JIRA_API_MIGRATION.md](docs/JIRA_API_MIGRATION.md) - API migration
- [MVP_VALIDATION_GUIDE.md](docs/MVP_VALIDATION_GUIDE.md) - Validation guide

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=triage --cov-report=html

# Unit tests
uv run pytest tests/unit/ -v

# Property-based tests
uv run pytest tests/property/ -v

# Integration tests
uv run pytest tests/integration/ -v

# Specific test
uv run pytest tests/unit/test_models.py::test_daily_plan_to_markdown_basic -v

# With detailed logging
uv run pytest -v --log-cli-level=DEBUG
```

### Project Structure

```
triage/                     # Main package
├── __init__.py            # Logging configuration
├── models.py              # Data models (JiraIssue, DailyPlan, etc.)
├── jira_client.py         # JIRA REST API client
├── task_classifier.py     # Task classification logic
├── plan_generator.py      # Daily plan generation
├── approval_manager.py    # User approval workflows
├── background_scheduler.py # Asynchronous scheduler
└── cli.py                 # Command-line interface

tests/                      # Test suite
├── unit/                  # Unit tests
│   ├── test_models.py
│   ├── test_jira_client.py
│   ├── test_task_classifier.py
│   ├── test_plan_generator.py
│   ├── test_approval_manager.py
│   └── test_cli.py
├── property/              # Property-based tests (Hypothesis)
│   ├── test_plan_generation.py
│   ├── test_task_classification.py
│   ├── test_task_decomposition.py
│   ├── test_approval_workflow.py
│   ├── test_replanning.py
│   ├── test_closure_tracking.py
│   ├── test_jira_state_reflection.py
│   ├── test_background_scheduler.py
│   └── test_markdown_output.py
└── integration/           # Integration tests
    └── test_workflows.py

examples/                   # Demonstration scripts
├── demo_mvp.py            # Complete MVP demo
├── demo_decomposition.py  # Decomposition demo
├── demo_replanning.py     # Re-planning demo
├── demo_closure_tracking.py # Tracking demo
├── demo_logging.py        # Logging demo
├── validate_mvp.py        # MVP validation
└── diagnose-jira-connection.py # JIRA diagnostics

docs/                       # Documentation
├── LOGGING_GUIDE.md       # Logging guide
├── LOGGING_IMPLEMENTATION.md # Logging implementation
├── JIRA_API_MIGRATION.md  # JIRA API migration
├── MVP_VALIDATION_GUIDE.md # MVP validation guide
├── MVP_VALIDATION_RESULTS.md # Validation results
├── CLOSURE_TRACKING_IMPLEMENTATION.md # Closure tracking
├── REPLANNING_IMPLEMENTATION.md # Re-planning
└── ...

.kiro/                      # Project specifications
├── specs/
│   └── triage-mvp/
│       ├── requirements.md # Requirements
│       ├── design.md      # Design
│       └── tasks.md       # Implementation plan
└── steering/              # Project guides
```

### Adding New Features

1. **Update specifications** in `.kiro/specs/triage-mvp/`
2. **Write tests first** (TDD)
3. **Implement the feature**
4. **Update documentation**
5. **Run complete test suite**

### Code Conventions

- **Type hints** on all functions
- **Docstrings** in Google format
- **Appropriate logging** in all components
- **Tests** for all new functionality
- **Property-based tests** for system invariants

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Implementation Status

### ✅ Completed (MVP)

- ✅ **Project Setup** with uv
- ✅ **Data Models** (JiraIssue, TaskClassification, DailyPlan, etc.)
- ✅ **JIRA Client** with authentication, error handling, and retries
- ✅ **Task Classifier** with dependency detection
- ✅ **Plan Generator** with priority selection
- ✅ **CLI Interface** with automatic `.env` loading
- ✅ **Approval Manager** with timeouts and modifications
- ✅ **Property-Based Tests** for core functionality
- ✅ **Long-Running Task Decomposition** into one-day subtasks
- ✅ **Closure Tracking** with completion rates
- ✅ **Re-planning** for blocking tasks
- ✅ **Background Scheduler** with polling and operation queue
- ✅ **Complete Logging System** configurable
- ✅ **JIRA Synchronization** and state reflection
- ✅ **End-to-End MVP Validation**

### 📊 Test Coverage

- **Unit Tests**: 66/66 passing (100%)
- **Property Tests**: 32/32 passing (100%)
- **Integration Tests**: 3/3 passing (100%)
- **Code Coverage**: >85%

### 🎯 System Features

| Feature | Status | Description |
|---------|--------|-------------|
| Plan Generation | ✅ | Up to 3 daily priorities |
| Task Classification | ✅ | Automatic with AI |
| Administrative Block | ✅ | Maximum 90 minutes |
| Dependency Detection | ✅ | Blocks dependent tasks |
| Effort Estimation | ✅ | Story points and time |
| Decomposition | ✅ | Tasks >1 day into subtasks |
| Re-planning | ✅ | Blocker handling |
| Closure Tracking | ✅ | Daily completion rate |
| Asynchronous Scheduler | ✅ | Polling and auto-generation |
| Approval System | ✅ | Full user control |
| Logging | ✅ | DEBUG, INFO, WARNING, ERROR |
| Error Handling | ✅ | Retries and rate limiting |

### 🚀 Future Improvements (Post-MVP)

- ⏳ **REST API**: Expose functionality via HTTP API
- ⏳ **Webhooks**: Integration with JIRA events
- ⏳ **Advanced Metrics**: Work pattern analysis
- ⏳ **Web Interface**: Visualization dashboard
- ⏳ **Notifications**: Email, Slack, etc.
- ⏳ **Multi-user**: Team support
- ⏳ **Plan Templates**: Customizable plans
- ⏳ **Calendar Integration**: Google Calendar, Outlook

## Documentation

Complete documentation is available in the [docs/](docs/) directory:

- **[Documentation Index](docs/README.md)** - Complete documentation catalog
- **[AWS Deployment](docs/AWS_DEPLOYMENT.md)** - AWS deployment guide
- **[Postman Setup](docs/POSTMAN_SETUP.md)** - API testing guide
- **[Lambda Folder](docs/LAMBDA_FOLDER_EXPLANATION.md)** - Understanding the deployment package
- **[Repository Files](docs/REPOSITORY_FILES_GUIDE.md)** - Git best practices
- **[Logging Guide](docs/LOGGING_GUIDE.md)** - Logging system usage

### Quick Links

| Category | Documents |
|----------|-----------|
| **Getting Started** | [Main README](README.md), [Installation](#installation) |
| **Deployment** | [AWS Guide](docs/AWS_DEPLOYMENT.md), [Scripts](scripts/README.md), [IAM Setup](docs/AWS_IAM_PERMISSIONS.md) |
| **API** | [Postman Setup](docs/POSTMAN_SETUP.md), [API Collection](docs/postman_collection.json) |
| **Development** | [Implementation Context](.kiro/steering/implementation-context.md), [Running Tests](#running-tests) |
| **Troubleshooting** | [JIRA Issues](docs/JIRA_API_MIGRATION.md), [Logging](docs/LOGGING_GUIDE.md) |

### For Developers

- **[Implementation Context](.kiro/steering/implementation-context.md)** - Complete technical context for future development phases
- [Requirements](.kiro/specs/triage-mvp/requirements.md) - User stories and criteria
- [Design](.kiro/specs/triage-mvp/design.md) - Architecture and components
- [Tasks](.kiro/specs/triage-mvp/tasks.md) - Implementation plan

## License

TrIAge is licensed under the GNU Affero General Public License v3 (AGPLv3).

Copyright (C) 2026 StrateCode

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

Commercial licensing options may be available in the future.

## Support

To report bugs or request features:
- Open an issue on GitHub
- Include logs with `--debug` if it's a bug
- Describe expected vs actual behavior

## Acknowledgments

Built with:
- [Python](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) - Fast package manager
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Hypothesis](https://hypothesis.readthedocs.io/) - Property-based testing
- [pytest](https://pytest.org/) - Testing framework
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management

---

**TrIAge** - Reduce cognitive load, increase productivity. 🎯

**TrIAge** - Reduce la carga cognitiva, aumenta la productividad. 🎯