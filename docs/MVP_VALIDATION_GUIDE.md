# TrIAge MVP End-to-End Validation Guide

## Overview

This guide provides instructions for validating the TrIAge MVP implementation against all requirements. The MVP is considered complete when all validation steps pass.

## Prerequisites

1. **JIRA Configuration**: Ensure `.env` file is configured with valid JIRA credentials
2. **Active Tasks**: Have at least a few active tasks assigned to you in JIRA
3. **Python Environment**: Virtual environment activated with all dependencies installed

## Validation Methods

### Method 1: Automated Validation Script (Recommended)

Run the comprehensive validation script:

```bash
python validate_mvp.py
```

This script will:
1. ✓ Validate configuration
2. ✓ Test JIRA connection and fetch tasks
3. ✓ Validate task classification
4. ✓ Generate and validate daily plan
5. ✓ Verify cognitive load reduction
6. ✓ Verify correct exclusions
7. ✓ Test approval workflow

**Expected Output**: All checks should pass (✓ PASS) with a final message "MVP is complete and usable!"

### Method 2: Manual CLI Testing

Test the CLI interface directly:

```bash
# Generate plan to stdout
triage generate-plan

# Generate plan to file
triage generate-plan -o daily-plan.md

# Generate plan with previous closure rate
triage generate-plan --closure-rate 0.67
```

### Method 3: Interactive Python Testing

Test components interactively:

```python
from ai_secretary.jira_client import JiraClient
from ai_secretary.task_classifier import TaskClassifier
from ai_secretary.plan_generator import PlanGenerator
from ai_secretary.approval_manager import ApprovalManager
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize components
jira = JiraClient(
    base_url=os.environ['JIRA_BASE_URL'],
    email=os.environ['JIRA_EMAIL'],
    api_token=os.environ['JIRA_API_TOKEN']
)

classifier = TaskClassifier()
generator = PlanGenerator(jira, classifier)
approval = ApprovalManager()

# Generate plan
plan = generator.generate_daily_plan()

# View plan
print(plan.to_markdown())

# Test approval
result = approval.present_plan(plan)
print(f"Approved: {result.approved}")
```

## Validation Checklist

### ✓ Requirement 1: Daily Plan Generation

- [ ] System fetches all active tasks from JIRA
- [ ] Tasks are classified by urgency, effort, and dependencies
- [ ] Tasks with dependencies are excluded from priorities
- [ ] Tasks >1 day are excluded from priorities
- [ ] Up to 3 priority tasks are selected
- [ ] Plan is output as structured markdown
- [ ] Plan requires explicit user approval

### ✓ Requirement 2: Task Classification

- [ ] All tasks are categorized (priority-eligible, admin, long-running, etc.)
- [ ] Tasks are not automatically added to current plan
- [ ] Administrative tasks are marked for grouping
- [ ] Tasks with dependencies are marked as ineligible
- [ ] Tasks >1 day are flagged

### ✓ Requirement 5: Administrative Task Management

- [ ] Admin tasks are excluded from priority selection
- [ ] Admin tasks are grouped into dedicated time block
- [ ] Admin block is limited to 90 minutes
- [ ] Admin block is scheduled during low-energy period (configurable)
- [ ] Overflow admin tasks are deferred

### ✓ Requirement 6: JIRA Integration

- [ ] System queries JIRA using REST API
- [ ] No persistent local copy beyond current session
- [ ] JIRA unavailability is handled gracefully

### ✓ Requirement 7: Human Control

- [ ] Daily plan requires explicit approval
- [ ] User can approve or reject plans

### ✓ Requirement 9: Structured Output

- [ ] Output is valid markdown
- [ ] Task information includes ID, title, effort, dependencies
- [ ] Priorities use numbered lists
- [ ] Admin block has dedicated section
- [ ] Markdown is parseable by standard processors

### ✓ Requirement 10: Dependency Tracking

- [ ] System identifies third-party dependencies
- [ ] Tasks with dependencies are marked ineligible
- [ ] Tasks with dependencies are excluded from priorities
- [ ] Dependencies are clearly indicated in output

### ✓ Requirement 11: Cognitive Load Optimization

- [ ] Priority list limited to max 3 tasks
- [ ] Output is concise and clear
- [ ] Structured sections for easy scanning

## Expected Outcomes

### Plan Usefulness
- Priorities should be actionable tasks you can complete today
- No tasks should be blocked by external dependencies
- Task estimates should be realistic (≤1 day)

### Cognitive Load Reduction
- Maximum 3 priorities keeps focus manageable
- Admin tasks grouped separately reduces context switching
- Clear markdown structure enables quick scanning

### Correct Exclusions
- Tasks with dependencies should appear in "Other Active Tasks" section
- Long-running tasks (>1 day) should not be in priorities
- Administrative tasks should be in dedicated admin block

## Troubleshooting

### No Active Tasks Found

If you have no active tasks in JIRA:
1. Create a few test tasks in JIRA
2. Assign them to yourself
3. Vary the task types (some with dependencies, some admin, some long-running)
4. Re-run validation

### JIRA Connection Errors

If JIRA connection fails:
1. Verify `JIRA_BASE_URL` is correct (e.g., `https://company.atlassian.net`)
2. Verify `JIRA_EMAIL` matches your JIRA account
3. Verify `JIRA_API_TOKEN` is valid (generate new one if needed)
4. Check network connectivity

### Authentication Errors

If authentication fails:
1. Generate a new API token at: https://id.atlassian.com/manage-profile/security/api-tokens
2. Update `JIRA_API_TOKEN` in `.env` file
3. Ensure email matches the account that generated the token

## Success Criteria

The MVP is considered **complete and usable** when:

1. ✓ All automated validation checks pass
2. ✓ User can generate daily plans without friction
3. ✓ Plans contain realistic, actionable priorities
4. ✓ Cognitive load is reduced (≤3 priorities, clear structure)
5. ✓ Exclusions work correctly (dependencies, long tasks, admin)
6. ✓ Approval workflow functions properly

## Next Steps

Once MVP validation passes:
1. Use the system daily for real work
2. Gather feedback on plan usefulness
3. Identify areas for improvement
4. Consider implementing Post-MVP features (Tasks 9-14)

## MVP Completion

📌 **At this point, MVP is complete and usable!**

The system provides:
- Manual daily plan generation
- Task classification and priority selection
- Administrative task grouping
- Structured markdown output
- CLI-based interaction
- Manual approval workflow

All core functionality is working without background automation or advanced features.
