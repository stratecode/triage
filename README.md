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

### Installation

```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Or install in development mode
uv pip install -e .
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
- ✅ Basic unit tests

### In Progress
- 🚧 MVP Phase (Tasks 1-8)

### Planned
- ⏳ JIRA Client integration
- ⏳ Task Classifier
- ⏳ Plan Generator
- ⏳ CLI Interface
- ⏳ Property-based tests

## License

TBD
