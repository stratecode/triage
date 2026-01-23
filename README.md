# TrIAge

Execution support system for senior technical professionals working in high-interruption, multi-project environments.

## Overview

TrIAge reduces cognitive load by generating focused daily plans with a maximum of 3 real priorities. It treats JIRA as the single source of truth and operates asynchronously to generate actionable daily plans.

## Core Principles

- **JIRA as Single Source of Truth**: No persistent local state; all task data lives in JIRA
- **Human Control**: Every plan and action requires explicit user approval
- **Cognitive Load Minimization**: Maximum 3 priorities per day, grouped administrative tasks
- **Daily Closure Focus**: All priority tasks must be closable within one working day
- **Asynchronous Operation**: Background polling and plan generation without blocking the user

## Setup

This project uses `uv` for package management.

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- JIRA account with API token

### Installation

```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Install in development mode
uv pip install -e .
```

### Configuration

The application automatically loads environment variables from a `.env` file in the project root.

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your JIRA credentials:
```bash
# Required
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token

# Optional: Filter by project
JIRA_PROJECT=PROJ  # Only show tasks from this project (e.g., PROJ-123)

# Optional: Admin block scheduling
ADMIN_TIME_START=14:00
ADMIN_TIME_END=15:30
```

3. Generate a JIRA API token at: https://id.atlassian.com/manage-profile/security/api-tokens

**Note**: The `.env` file is automatically loaded when you run any `triage` command. You don't need to manually source it or export variables.

#### Project Filtering

If you set `JIRA_PROJECT`, only tasks from that specific project will be included in your daily plans. This is useful if you work on multiple projects but want to focus on one at a time.

Example:
- `JIRA_PROJECT=IAOW` - Only shows tasks like IAOW-123, IAOW-456, etc.
- Leave empty or unset to see tasks from all projects

## Usage

### Generate Daily Plan

```bash
# Generate plan to stdout (automatically loads .env)
triage generate-plan

# Generate plan to file
triage generate-plan -o daily-plan.md

# Generate plan with previous day's closure rate
triage generate-plan --closure-rate 0.67
```

**Note**: The application automatically loads your configuration from the `.env` file. No need to manually export environment variables.

### Example Output

```markdown
# Daily Plan - 2026-01-23

## Today's Priorities

1. **[PROJ-123] Implement user authentication**
   - Effort: 8.0 hours
   - Type: Story
   - Priority: High

2. **[PROJ-124] Fix login bug**
   - Effort: 4.0 hours
   - Type: Bug

## Administrative Block (14:00-15:30)

- [ ] [PROJ-126] Email responses
- [ ] [PROJ-127] Weekly report

## Other Active Tasks (For Reference)

- [PROJ-129] Waiting on external team (blocked by dependencies)
- [PROJ-130] Multi-day feature (decomposition needed)
```

## Troubleshooting

### JIRA Connection Issues

If you encounter connection errors:

1. **Run the diagnostic tool**:
   ```bash
   python examples/diagnose-jira-connection.py
   ```

2. **HTTP 410 Error**: This has been fixed in the latest version. The application now uses the new JIRA API endpoint (`/rest/api/3/search/jql`). See [docs/JIRA_API_MIGRATION.md](docs/JIRA_API_MIGRATION.md) for details.

3. **Authentication Errors**: 
   - Verify your JIRA_EMAIL is correct
   - Ensure your JIRA_API_TOKEN is valid
   - Generate a new token at: https://id.atlassian.com/manage-profile/security/api-tokens

4. **Connection Timeout**:
   - Check your internet connection
   - Verify JIRA_BASE_URL is correct
   - Ensure JIRA service is available

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=triage

# Run specific test file
uv run pytest tests/unit/test_models.py -v
```

### Project Structure

```
triage/                # Main package
├── __init__.py
├── models.py          # Core data models
├── jira_client.py     # JIRA REST API integration
├── task_classifier.py # Task categorization logic
├── plan_generator.py  # Daily plan generation
├── approval_manager.py # User approval workflows
└── cli.py            # Command-line interface

tests/                 # Test suite
├── unit/             # Unit tests
├── property/         # Property-based tests
└── integration/      # Integration tests (to be implemented)
```

## Implementation Status

### Completed
- ✅ Project setup with uv
- ✅ Core data models (JiraIssue, TaskClassification, DailyPlan, etc.)
- ✅ DailyPlan.to_markdown() implementation
- ✅ JIRA Client integration with authentication
- ✅ Task Classifier with dependency detection
- ✅ Plan Generator with priority selection
- ✅ CLI Interface with automatic .env loading
- ✅ Approval Manager (MVP)
- ✅ Property-based tests for core functionality

### In Progress
- 🚧 MVP Phase (Task 8: End-to-End Validation)

### Planned
- ⏳ Background Scheduler (Post-MVP)
- ⏳ Long-running task decomposition (Post-MVP)
- ⏳ Re-planning flow (Post-MVP)

## License

TrIAge is licensed under the GNU Affero General Public License v3 (AGPLv3).

Commercial licensing options may be available in the future.