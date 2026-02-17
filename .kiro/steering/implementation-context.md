---
inclusion: auto
---

# TrIAge Implementation Context

## Project Overview

TrIAge is an AI-powered execution support system for senior technical professionals. It generates focused daily plans with maximum 3 priorities, reducing cognitive load in high-interruption environments.

## Current Implementation Status

### ✅ Completed Features (MVP Complete)

1. **Core Planning Engine**
   - Daily plan generation with up to 3 priority tasks
   - Intelligent task classification (urgency, effort, dependencies)
   - Administrative task grouping (90-minute blocks)
   - Closure rate tracking for continuous improvement

2. **JIRA Integration**
   - Full JIRA REST API v3 integration
   - Automatic task fetching and classification
   - Subtask creation for decomposition
   - Robust error handling and retry logic

3. **Task Management**
   - Long-running task decomposition into daily-closable units
   - Blocking task detection and re-planning
   - Dependency tracking (third-party blockers)
   - Effort estimation (story points → hours)

4. **User Interaction**
   - CLI interface with automatic .env loading
   - Approval workflow with timeout handling
   - Markdown output for easy sharing
   - Debug logging for troubleshooting

5. **Background Operations**
   - Asynchronous scheduler for polling
   - Operation queue management
   - Scheduled plan generation (7 AM weekdays)

6. **Testing**
   - 66 unit tests (100% passing)
   - 32 property-based tests (Hypothesis)
   - 3 integration tests
   - >85% code coverage

### 🏗️ Architecture

**Deployment Options:**
1. **Local**: Python CLI with direct JIRA access
2. **AWS Serverless**: Lambda + API Gateway + EventBridge

**Key Components:**
- `triage/models.py` - Data models (JiraIssue, DailyPlan, TaskClassification)
- `triage/jira_client.py` - JIRA API client with retry logic
- `triage/task_classifier.py` - Task categorization engine
- `triage/plan_generator.py` - Daily plan generation logic
- `triage/approval_manager.py` - User approval workflows
- `triage/background_scheduler.py` - Async operations
- `triage/cli.py` - Command-line interface

**AWS Lambda Deployment:**
- `lambda/handlers.py` - API Gateway handlers
- `lambda/authorizer.py` - JWT authentication
- `template.yaml` - SAM infrastructure definition

### 📊 API Endpoints (AWS Deployment)

```
GET  /api/v1/health                    # Health check (no auth)
POST /api/v1/plan                      # Generate daily plan
GET  /api/v1/plan/{date}               # Get plan by date
POST /api/v1/plan/{date}/approve       # Approve/reject plan
POST /api/v1/task/{taskId}/decompose   # Decompose long task
```

### 🔑 Key Design Decisions

1. **JIRA as Single Source of Truth**
   - No local database or persistent state
   - All task data lives in JIRA
   - Plans are generated on-demand from current JIRA state

2. **Human Control**
   - Every plan requires explicit approval
   - User can modify or reject plans
   - Feedback loop for continuous improvement

3. **Daily Closure Focus**
   - Maximum 3 priorities per day
   - All priorities must be closable within one working day
   - Long tasks automatically decomposed into subtasks

4. **Cognitive Load Minimization**
   - Administrative tasks grouped into 90-minute blocks
   - Low-energy time slots (default: 14:00-15:30)
   - Clear priority ordering

### 🔧 Technical Implementation Details

**JIRA API Migration (v3):**
- Migrated from deprecated v2 API to v3
- New endpoint: `/rest/api/3/search/jql`
- Handles HTTP 410 errors gracefully
- Automatic retry with exponential backoff

**Task Classification Logic:**
- Priority: High/Medium/Low based on issue priority + due date
- Effort: Story points → hours (1 SP = 2 hours, max 8 hours/day)
- Dependencies: Detects "blocked by" links and external dependencies
- Administrative: Identifies low-effort tasks (<2 hours)

**Plan Generation Algorithm:**
1. Fetch all active issues from JIRA
2. Classify each task (priority, effort, dependencies)
3. Filter out blocked tasks and tasks >1 day
4. Select top 3 priorities by score
5. Group remaining admin tasks into 90-min block
6. Generate markdown output

**Closure Tracking:**
- Tracks daily completion rate (tasks closed / tasks planned)
- Uses previous day's rate to adjust next day's planning
- Low closure rate (<0.5) → reduce priorities or decompose tasks

**Re-planning Flow:**
1. Detect blocking task during execution
2. Generate new plan excluding blocked tasks
3. Present to user for approval
4. Update JIRA with new priorities

### 📦 Deployment Structure

**Lambda Folder (`lambda/`):**
- Contains AWS Lambda deployment package
- `handlers.py` and `authorizer.py` are source files (in Git)
- Dependencies (boto3, pydantic, etc.) are installed during build (ignored in Git)
- `lambda/triage/` is a copy of main package (regenerated on each build)

**Important**: Always edit code in `triage/` at root, never in `lambda/triage/`

### 🔐 Configuration

**Environment Variables:**
```bash
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT=PROJ  # Optional: filter by project
ADMIN_TIME_START=14:00
ADMIN_TIME_END=15:30
```

**AWS Secrets Manager (Production):**
- `/{env}/triage/jira-credentials` - JIRA credentials
- `/{env}/triage/jwt-secret` - JWT authentication secret

### 🧪 Testing Strategy

**Unit Tests:**
- Test individual components in isolation
- Mock external dependencies (JIRA API)
- Focus on business logic correctness

**Property-Based Tests:**
- Use Hypothesis for invariant validation
- Minimum 100 iterations per property
- Custom generators for JiraIssue, TaskClassification, DailyPlan
- Naming: "Feature: triage, Property {N}: {description}"

**Integration Tests:**
- Test full workflows end-to-end
- Use real JIRA test instance or mock server
- Verify API contracts and data flow

### 🚀 Deployment Workflow

**Local Development:**
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials
triage generate-plan
```

**AWS Deployment:**
```bash
./scripts/setup-iam-permissions.sh <username>
./scripts/deploy.sh dev
./scripts/setup-secrets.sh dev
./scripts/generate-token.sh dev
./scripts/test-api.sh <api-url> <token>
```

### 📚 Key Documentation

**Essential Docs (Keep):**
- `docs/AWS_DEPLOYMENT.md` - Complete AWS setup guide
- `docs/POSTMAN_SETUP.md` - API testing with Postman
- `docs/LAMBDA_FOLDER_EXPLANATION.md` - Lambda deployment package
- `docs/REPOSITORY_FILES_GUIDE.md` - Git best practices
- `docs/LOGGING_GUIDE.md` - Logging system usage
- `docs/SLACK_BOT_SETUP.md` - Slack integration

**Postman Collection:**
- `docs/postman_collection.json` - Complete API collection
- `docs/postman_environment.json` - Environment variables

### 🔮 Future Enhancements (Post-MVP)

**Planned Features:**
1. **REST API Expansion**
   - OpenAPI 3.1 specification
   - Webhook support for JIRA events
   - Real-time plan updates

2. **Advanced Analytics**
   - Work pattern analysis
   - Productivity metrics
   - Burnout detection

3. **Multi-User Support**
   - Team coordination
   - Shared priorities
   - Workload balancing

4. **Integrations**
   - Calendar sync (Google, Outlook)
   - Notifications (Email, Slack)
   - Time tracking tools

5. **Web Interface**
   - Visual dashboard
   - Drag-and-drop planning
   - Real-time collaboration

### 🐛 Known Limitations

1. **No Persistent State**
   - Plans are not stored; regenerated from JIRA each time
   - Historical data only available through JIRA

2. **Single User Focus**
   - Designed for individual contributors
   - No team coordination features yet

3. **JIRA Dependency**
   - Requires JIRA for all task data
   - No offline mode

4. **Manual Approval**
   - Every plan requires user approval
   - No auto-approval based on confidence

### 🔍 Troubleshooting Common Issues

**JIRA Connection Errors:**
- Verify credentials in .env
- Check JIRA_BASE_URL (no trailing slash)
- Ensure API token has required permissions
- Use `examples/diagnose-jira-connection.py` for diagnostics

**No Priority Tasks Found:**
- All tasks have dependencies or are >1 day
- Use `--debug` flag to see classification details
- Consider decomposing large tasks

**Lambda Deployment Issues:**
- Ensure IAM permissions are correct
- Check CloudWatch logs for errors
- Verify secrets are configured in Secrets Manager

### 📖 Code Conventions

- Use dataclasses for data models
- Type hints on all function signatures
- Docstrings in Google format
- Logging at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Property-based tests for system invariants
- Integration tests for external dependencies

### 🏷️ Version Information

- **Current Version**: 0.1.0 (MVP Complete)
- **Python**: 3.11+
- **JIRA API**: v3
- **AWS SAM**: Latest
- **License**: AGPLv3

### 📝 Important Notes

1. **Lambda Dependencies**: Never commit installed dependencies in `lambda/`. Only commit `handlers.py`, `authorizer.py`, and `requirements.txt`.

2. **Environment Variables**: Never commit `.env` files. Always use `.env.example` as template.

3. **JIRA API**: Always use v3 endpoints. v2 is deprecated and returns HTTP 410.

4. **Testing**: Run full test suite before deployment: `uv run pytest`

5. **Logging**: Use appropriate log levels. DEBUG for development, INFO for production.

### 🎯 Development Guidelines

**When Adding New Features:**
1. Update specifications in `.kiro/specs/`
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Run full test suite
6. Update this steering file if architecture changes

**When Fixing Bugs:**
1. Write failing test that reproduces bug
2. Fix the bug
3. Verify test passes
4. Add regression test if needed

**When Refactoring:**
1. Ensure all tests pass before starting
2. Make small, incremental changes
3. Run tests after each change
4. Update documentation if interfaces change

---

This steering file provides essential context for future development phases. It captures the current state, key decisions, and important implementation details without the noise of historical fixes and process documentation.
