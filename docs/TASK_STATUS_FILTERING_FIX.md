# Task Status Filtering and Estimation Fix

## Problem

The plan generator had two issues:

1. **Over-restrictive filtering**: It was excluding tasks in "In Progress" status, which should be included for completion tracking
2. **Inflated effort estimates**: Story points were being converted at 1.25 days per point, making even small tasks (2 SP) appear as multi-day efforts (2.5 days)

This resulted in:
- Tasks already in progress being ignored
- Only "To Do" tasks being suggested
- Tasks with reasonable story points (2-3 SP) being excluded as "too large"

## Root Causes

### Issue 1: Status Filtering
The JQL query was excluding "In Progress" tasks:
```jql
status NOT IN ("In Progress", "Done", "Closed", "Resolved", "Complete")
```

This was too restrictive. Tasks in progress should be visible in the plan for completion tracking.

### Issue 2: Story Point Conversion
The classifier used an overly conservative conversion:
```python
STORY_POINTS_TO_DAYS = 1.25  # 1 SP = 1.25 days
```

With additional conservative rounding (`max(1.0, ...)`), this meant:
- 1 SP → 1.25 days → rounded to 1.0 day (minimum)
- 2 SP → 2.5 days → excluded as "long-running"
- 3 SP → 3.75 days → excluded as "long-running"

## Solutions

### Fix 1: Include In-Progress Tasks

Updated JQL to only exclude completed tasks:
```jql
assignee = currentUser() 
AND resolution = Unresolved 
AND status NOT IN ("Done", "Closed", "Resolved", "Complete")
```

Now includes:
- ✓ To Do tasks (new work)
- ✓ In Progress tasks (should be completed)
- ✓ Blocked/Waiting tasks (for visibility)
- ✗ Done/Closed/Resolved tasks (already completed)

### Fix 2: Realistic Story Point Conversion

Updated conversion to match standard Scrum practices:
```python
STORY_POINTS_TO_DAYS = 0.5  # 1 SP = 0.5 days (4 hours)
```

This allows:
- 1 SP → 0.5 days (half day)
- 2 SP → 1.0 day (full day, daily-closable ✓)
- 3 SP → 1.5 days (excluded as long-running ✗)

### Fix 3: Prioritize In-Progress Tasks

Updated task ranking to prioritize tasks already in progress:

```python
def sort_key(classification):
    status_rank = 0 if task.status.lower() == 'in progress' else 1
    priority_rank = priority_order.get(task.priority.lower(), 3)
    effort = classification.estimated_days
    age_proxy = extract_age(task.key)
    
    return (status_rank, priority_rank, effort, age_proxy)
```

Ranking order:
1. **Status** (In Progress first - should be completed)
2. **Priority** (Blocker > High > Medium > Low)
3. **Effort** (smaller first)
4. **Age** (older first)

## Expected Behavior

After these fixes:

### Task Inclusion
- ✓ Tasks in "To Do" are included
- ✓ Tasks in "In Progress" are included and prioritized
- ✓ Tasks in "Blocked" or "Waiting" are included for visibility
- ✗ Tasks in "Done", "Closed", "Resolved" are excluded

### Effort Estimation
- 1 story point = 0.5 days (4 hours)
- 2 story points = 1.0 day (daily-closable)
- 3+ story points = 1.5+ days (long-running, needs decomposition)
- No estimate = 0.5 days (benefit of the doubt)

### Priority Selection
1. Tasks already in progress get highest priority (should be completed)
2. Then by JIRA priority (Blocker > High > Medium > Low)
3. Then by effort (smaller tasks first)
4. Then by age (older tasks first)

## Story Point Guidelines

For tasks to be daily-closable:
- **1 SP**: Small task, ~4 hours (half day)
- **2 SP**: Medium task, ~8 hours (full day) ✓ Daily-closable
- **3 SP**: Large task, ~12 hours (1.5 days) ✗ Needs decomposition
- **5+ SP**: Very large, definitely needs decomposition

## Verification

Run the verification script to check behavior with your JIRA instance:

```bash
python examples/verify_task_filtering.py
```

The script will show:
1. Which tasks are fetched (by status)
2. How tasks are classified
3. Which tasks are selected as priorities
4. Verification that in-progress tasks are prioritized

## Testing

All tests pass with these changes:
- ✓ 66 unit tests
- ✓ 6 integration tests

## Configuration

If your team uses different story point scales, you can adjust the conversion in `triage/task_classifier.py`:

```python
# For teams where 1 SP = 1 day
STORY_POINTS_TO_DAYS = 1.0

# For teams where 1 SP = 2 hours
STORY_POINTS_TO_DAYS = 0.25
```

The key principle: **Tasks with estimated_days <= 1.0 are daily-closable**.

## Related Files

- `triage/jira_client.py` - Updated JQL query
- `triage/task_classifier.py` - Updated story point conversion
- `triage/plan_generator.py` - Updated task ranking
- `tests/unit/test_task_classifier.py` - Updated test expectations
- `examples/verify_task_filtering.py` - Verification script
