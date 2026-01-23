# AI Secretary

Execution support system for senior technical professionals working in high-interruption, multi-project environments.

## Overview

The AI Secretary reduces cognitive load by generating focused daily plans with a maximum of 3 real priorities. It treats JIRA as the single source of truth and operates asynchronously to generate actionable daily plans.

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

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your JIRA credentials:
```bash
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token
```

3. Generate a JIRA API token at: https://id.atlassian.com/manage-profile/security/api-tokens

## Usage

### Generate Daily Plan

```bash
# Load environment variables
source .env

# Generate plan to stdout
ai-secretary generate-plan

# Generate plan to file
ai-secretary generate-plan -o daily-plan.md

# Generate plan with previous day's closure rate
ai-secretary generate-plan --closure-rate 0.67
```

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

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=ai_secretary

# Run specific test file
uv run pytest tests/unit/test_models.py -v
```

### Project Structure

```
ai_secretary/           # Main package
├── __init__.py
├── models.py          # Core data models
├── jira_client.py     # JIRA REST API integration (to be implemented)
├── task_classifier.py # Task categorization logic (to be implemented)
├── plan_generator.py  # Daily plan generation (to be implemented)
└── cli.py            # Command-line interface (to be implemented)

tests/                 # Test suite
├── unit/             # Unit tests
├── property/         # Property-based tests (to be implemented)
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
- ✅ CLI Interface with environment-based configuration
- ✅ Property-based tests for core functionality

### In Progress
- 🚧 MVP Phase (Tasks 6-8)

### Planned
- ⏳ Approval Manager
- ⏳ Background Scheduler (Post-MVP)
- ⏳ Long-running task decomposition (Post-MVP)
- ⏳ Re-planning flow (Post-MVP)

## License

TBD
