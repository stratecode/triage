# Re-planning Flow Implementation

## Overview

This document describes the implementation of Task 12: Re-planning Flow, which enables the AI Secretary to handle blocking tasks by interrupting the current plan and generating a new one that prioritizes the blocking task.

## Implementation Date

January 23, 2026

## Components Implemented

### 1. PlanGenerator.generate_replan() Method

**Location:** `triage/plan_generator.py`

**Purpose:** Generate a new daily plan when a blocking task is detected, incorporating the blocking task as the first priority.

**Key Features:**
- Accepts a blocking task and the current plan as inputs
- Fetches all active tasks from JIRA
- Classifies all tasks including the blocking task
- Places the blocking task as the first priority
- Fills remaining priority slots (up to 3 total) with eligible tasks
- Preserves the previous closure rate from the current plan
- Respects all plan generation constraints (max 3 priorities, admin block limits, etc.)

**Algorithm:**
1. Fetch all active tasks from JIRA
2. Classify all tasks
3. Ensure blocking task is included in classifications
4. Filter and rank eligible tasks (excluding the blocking task temporarily)
5. Start new priorities list with blocking task as first priority
6. Add up to 2 more priorities from ranked eligible tasks
7. Group administrative tasks into admin block
8. Collect other tasks for reference
9. Return new DailyPlan with blocking task prioritized

### 2. ApprovalManager.notify_blocking_task() Method

**Location:** `triage/approval_manager.py`

**Purpose:** Notify the user of a blocking task detection and present the new plan for approval.

**Key Features:**
- Displays a clear warning about plan interruption
- Shows details of the blocking task (key, summary, type, priority, description preview)
- Explains that the current plan will be replaced
- Presents the new plan in markdown format
- Collects user approval (yes/no)
- Collects feedback if user rejects the re-plan
- Returns ApprovalResult with approval status and optional feedback

**User Experience:**
- Clear visual separation with warning emoji (⚠️)
- Contextual information about the interruption
- Full transparency about what's changing
- Approval-gated plan replacement (no automatic changes)

### 3. Property Tests

**Location:** `tests/property/test_replanning.py`

Two property-based tests were implemented to validate the re-planning flow:

#### Property 9: Re-planning Trigger
**Validates:** Requirements 3.2, 3.3

**Test:** `test_property_9_replanning_trigger`

**Verifies:**
- The `generate_replan()` method exists and can be called
- A new plan is generated when a blocking task is detected
- The new plan is different from the current plan
- The system properly handles the re-planning flow

#### Property 10: Blocking Task Inclusion
**Validates:** Requirements 3.4

**Test:** `test_property_10_blocking_task_inclusion`

**Verifies:**
- The blocking task is included in the new plan's priorities
- The blocking task is the first priority (highest priority)
- The plan still respects the max 3 priorities constraint

Both tests use Hypothesis for property-based testing with randomized inputs to ensure correctness across many scenarios.

## Requirements Validated

### Requirement 3.2: Plan Interruption
✅ When a blocking task is detected, the system marks the current plan as interrupted and initiates re-planning.

### Requirement 3.3: Re-planning Flow Initiation
✅ The re-planning flow is triggered when a blocking task is detected.

### Requirement 3.4: Blocking Task Inclusion
✅ The new plan includes the blocking task as a priority (specifically as the first priority).

### Requirement 3.5: User Approval
✅ The new plan is presented to the user for approval before replacing the current plan.

### Requirement 7.3: Approval-Gated Replacement
✅ Plan replacement requires explicit user approval through the ApprovalManager.

## Testing Results

All tests pass successfully:

```
tests/property/test_replanning.py::test_property_9_replanning_trigger PASSED
tests/property/test_replanning.py::test_property_10_blocking_task_inclusion PASSED
```

Property tests run with Hypothesis default settings (minimum 100 iterations).

## Demo

A demonstration script is available at `examples/demo_replanning.py` that shows:
1. Initial daily plan generation
2. Blocking task detection
3. Re-planning flow execution
4. Plan comparison (before/after)
5. Approval workflow

Run with: `python examples/demo_replanning.py`

## Integration with Existing System

The re-planning flow integrates seamlessly with existing components:

- **JiraClient:** Uses existing `fetch_active_tasks()` method
- **TaskClassifier:** Uses existing `classify_task()` method
- **PlanGenerator:** Reuses existing filtering, ranking, and grouping logic
- **ApprovalManager:** Follows existing approval patterns
- **DailyPlan:** Uses existing data model and markdown formatting

## Future Enhancements

The following enhancements are planned for future iterations:

1. **Automatic Blocking Task Detection:** Background scheduler integration (Task 11) will enable automatic detection of blocking tasks without manual triggering.

2. **Plan History:** Track interrupted plans to allow users to review what was changed.

3. **Smart Priority Preservation:** Consider preserving some current priorities if they're related to the blocking task.

4. **Notification System:** Integrate with notification system (Task 11.3) for proactive alerts.

## Code Quality

- ✅ All code follows project conventions
- ✅ Type hints on all function signatures
- ✅ Comprehensive docstrings
- ✅ No linting or diagnostic issues
- ✅ Property-based tests with 100+ iterations
- ✅ Integration with existing codebase

## Conclusion

Task 12: Re-planning Flow has been successfully implemented with all subtasks completed:

- ✅ 12.1: Implement `generate_replan()` method
- ✅ 12.2: Add blocking task notification to Approval Manager
- ✅ 12.3: Write property test for re-planning trigger
- ✅ 12.4: Write property test for blocking task inclusion

The implementation provides a robust foundation for handling blocking tasks and ensures that critical issues can interrupt the current plan with proper user approval and transparency.
