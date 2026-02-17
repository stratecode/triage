# Project Structure

## Directory Organization

```
.kiro/
├── specs/
│   └── ai-secretary/
│       ├── requirements.md    # User stories and acceptance criteria
│       ├── design.md          # Architecture and component design
│       └── tasks.md           # Implementation task list (MVP-driven)
├── steering/                  # Project guidance documents
└── settings/                  # Configuration files

ai_secretary/                  # Main package (to be created)
├── __init__.py
├── models.py                  # Core data models (JiraIssue, DailyPlan, etc.)
├── jira_client.py            # JIRA REST API integration
├── task_classifier.py        # Task categorization logic
├── plan_generator.py         # Daily plan generation
├── approval_manager.py       # User approval workflows
├── background_scheduler.py   # Async polling (Post-MVP)
└── cli.py                    # Command-line interface

tests/                        # Test suite (to be created)
├── unit/                     # Unit tests
├── property/                 # Property-based tests
└── integration/              # Integration tests
```

## Implementation Phases

### MVP Phase (Tasks 1-8)
Focus on immediate usability:
- Manual daily plan generation
- Task classification and priority selection
- CLI-based interaction
- Basic approval workflow
- No background automation

### Post-MVP Phase (Tasks 9-14)
Add automation and advanced features:
- Background polling for blocking tasks
- Long-running task decomposition
- Task closure tracking
- Re-planning flows
- Advanced approval behaviors

## Key Components

### Core Models (`models.py`)
- `JiraIssue`: Raw JIRA task data
- `TaskClassification`: Categorized task with metadata
- `DailyPlan`: Generated plan with priorities and admin block
- `AdminBlock`: Grouped administrative tasks
- `SubtaskSpec`: Subtask creation specification
- `ApprovalResult`: User approval response

### JIRA Client (`jira_client.py`)
- Authenticate with JIRA REST API
- Fetch active and blocking tasks
- Create subtasks with parent linking
- Handle API errors and rate limiting

### Task Classifier (`task_classifier.py`)
- Categorize tasks by urgency, effort, dependencies
- Identify third-party dependencies
- Estimate effort in days
- Mark administrative tasks

### Plan Generator (`plan_generator.py`)
- Select up to 3 priority tasks
- Group administrative tasks into 90-minute blocks
- Generate structured markdown output
- Handle re-planning for blocking tasks

### Approval Manager (`approval_manager.py`)
- Present plans for user approval
- Collect feedback on rejections
- Handle user modifications
- Manage approval timeouts

## Coding Conventions

- Use dataclasses for data models
- Type hints for all function signatures
- Docstrings 