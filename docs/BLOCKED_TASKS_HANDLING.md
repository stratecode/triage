# Blocked Tasks Handling

## Problem

Tasks in "Blocked", "Waiting", "On Hold", or "Pending" status were being suggested as priorities even though they cannot be worked on. This resulted in unproductive daily plans.

## Solution

The system now:
1. **Excludes blocked/waiting tasks** from priority selection
2. **Shows them in a dedicated section** for visibility
3. **Identifies them automatically** by status

## Changes Made

### 1. Priority Filtering (`plan_generator.py`)

Added status-based filtering to exclude non-actionable tasks:

```python
blocked_statuses = {'blocked', 'waiting', 'on hold', 'pending'}

# Exclude blocked or waiting tasks (not actionable)
task_status_lower = classification.task.status.lower()
if task_status_lower in blocked_statuses:
    continue
```

### 2. New Plan Section (`models.py`)

Added a dedicated section in the daily plan for blocked tasks:

```python
@dataclass
class DailyPlan:
    # ... existing fields ...
    blocked_tasks: List[TaskClassification] = field(default_factory=list)
```

### 3. Markdown Output

Plans now include a "🚫 Blocked/Waiting Tasks" section:

```markdown
## 🚫 Blocked/Waiting Tasks

These tasks cannot be worked on until unblocked:

- **[PROJ-123] Waiting for API approval**
  - Status: Waiting
  - Reason: Blocked by dependencies
  - Priority: High
```

## Blocked Status Detection

The system recognizes these statuses as "blocked":
- **Blocked** - Explicitly blocked
- **Waiting** - Waiting for something
- **On Hold** - Temporarily paused
- **Pending** - Pending action from others

## Example Plan

```markdown
# Daily Plan - 2026-01-25

## Today's Priorities

1. **[PROJ-101] Fix login bug**
   - Effort: 4.0 hours
   - Status: In Progress
   - Priority: High

2. **[PROJ-102] Update documentation**
   - Effort: 2.0 hours
   - Status: To Do
   - Priority: Medium

## 🚫 Blocked/Waiting Tasks

These tasks cannot be worked on until unblocked:

- **[PROJ-200] Implement payment gateway**
  - Status: Waiting
  - Reason: Blocked by dependencies
  - Priority: High

- **[PROJ-201] Database migration**
  - Status: Blocked
  - Priority: Medium

## ⚠️ Tasks Requiring Decomposition

- **[PROJ-300] Refactor authentication**
  - Current estimate: 3.0 days
  - Story points: 6 SP
  - Suggestion: Break into 4 daily-closable subtasks
  - Command: `triage decompose PROJ-300`

## Administrative Block (14:00-15:30)

- [ ] [PROJ-150] Review pull requests
- [ ] [PROJ-151] Update sprint board
```

## Benefits

1. **No wasted priorities**: Only actionable tasks are suggested
2. **Visibility**: Blocked tasks are still shown for awareness
3. **Better planning**: Focus on work that can actually be completed
4. **Status tracking**: Easy to see what's blocked and why

## Future Enhancements

### Unblocking Check (Planned)

In future versions, the system will:
1. **Track blocked tasks** over time
2. **Prompt for status updates**: "Has PROJ-200 been unblocked?"
3. **Suggest re-evaluation**: "Check if dependencies are resolved"
4. **Auto-detect unblocking**: Monitor linked tasks for completion

Example future interaction:
```
🔔 Blocked Task Update

PROJ-200 has been blocked for 3 days.
Status: Waiting for API approval

Has this task been unblocked? [y/n]
> y

Great! PROJ-200 will be considered for tomorrow's priorities.
```

## Configuration

If your JIRA instance uses custom status names, update the blocked statuses list in `plan_generator.py`:

```python
blocked_statuses = {
    'blocked', 
    'waiting', 
    'on hold', 
    'pending',
    'paused',        # Add custom status
    'external wait'  # Add custom status
}
```

## Testing

All tests pass with these changes:
- ✅ 133 tests passed
- ✅ Property-based tests validate blocked task handling
- ✅ Integration tests confirm end-to-end behavior

## Related Changes

This feature works together with:
- **Task Status Filtering** (`docs/TASK_STATUS_FILTERING_FIX.md`)
- **Decomposition Suggestions** (automatic identification of large tasks)
- **Priority Ranking** (In Progress tasks prioritized over To Do)

## Verification

Run the verification script to see blocked tasks in action:

```bash
python examples/verify_task_filtering.py
```

The script will show:
- Which tasks are blocked/waiting
- Why they're excluded from priorities
- Where they appear in the plan
