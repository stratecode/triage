# Planning Behavior Update - Summary

## What Changed

Fixed two critical issues affecting daily plan generation:

1. **Task filtering was too restrictive** - Excluded tasks in progress
2. **Story point estimates were inflated** - Made small tasks appear too large

## Impact on Your Workflow

### Before
- ❌ Tasks in "In Progress" were ignored
- ❌ 2 story point tasks were estimated at 2.5 days (excluded as "too large")
- ❌ Only "To Do" tasks were suggested
- ❌ Work you'd already started wasn't tracked

### After
- ✅ Tasks in "In Progress" are included and **prioritized for completion**
- ✅ 2 story point tasks are estimated at 1.0 day (daily-closable)
- ✅ All active work is visible (To Do, In Progress, Blocked, Waiting)
- ✅ Work in progress gets top priority

## New Story Point Conversion

| Story Points | Estimated Days | Daily-Closable? |
|--------------|----------------|-----------------|
| 1 SP         | 0.5 days       | ✅ Yes          |
| 2 SP         | 1.0 day        | ✅ Yes          |
| 3 SP         | 1.5 days       | ❌ No (needs decomposition) |
| 5+ SP        | 2.5+ days      | ❌ No (needs decomposition) |

**Conversion rate**: 1 story point = 0.5 days (4 hours)

This matches standard Scrum practices where 1 SP represents ~half a day of work for a senior developer.

## New Priority Ranking

Tasks are now ranked in this order:

1. **Status**: In Progress first (should be completed)
2. **Priority**: Blocker > High > Medium > Low
3. **Effort**: Smaller tasks first
4. **Age**: Older tasks first

This ensures you complete work you've started before taking on new tasks.

## What Gets Included in Plans

### ✅ Included
- To Do (new work)
- In Progress (work to complete)
- Blocked (for visibility)
- Waiting (for visibility)

### ❌ Excluded
- Done
- Closed
- Resolved
- Complete

## Verify the Changes

Run this command to see how it works with your JIRA tasks:

```bash
python examples/verify_task_filtering.py
```

You should see:
- Tasks grouped by status
- Effort estimates based on story points
- Priority ranking with in-progress tasks first
- A generated daily plan

## If You Have Issues

### Issue: Tasks with 2-3 SP are still excluded

**Check**: Are they marked as "In Progress" or have dependencies?
- In Progress tasks are included but may not be priority-eligible if they have dependencies
- Tasks with dependencies are shown separately

### Issue: Wrong effort estimates

**Check**: Your team's story point scale
- If your team uses 1 SP = 1 day, adjust `STORY_POINTS_TO_DAYS` in `triage/task_classifier.py`
- Default is 1 SP = 0.5 days (4 hours)

### Issue: Tasks in custom statuses aren't showing

**Check**: Your JIRA status names
- If you use custom statuses like "Working" or "Finished", update the exclusion list in `triage/jira_client.py`
- Add your custom "done" statuses to the NOT IN clause

## Questions?

See the detailed documentation:
- `docs/TASK_STATUS_FILTERING_FIX.md` - Complete technical details
- `examples/verify_task_filtering.py` - Verification script
- `triage/task_classifier.py` - Story point conversion logic
- `triage/plan_generator.py` - Priority ranking logic
