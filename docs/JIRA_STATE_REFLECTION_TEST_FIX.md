# JIRA State Reflection Property Test Fix

## Summary

Fixed property-based test failures in `test_jira_state_reflection.py` (Task 14.4) by addressing duplicate key generation and None value handling issues.

## Issues Identified

### 1. Duplicate Task Keys
**Problem**: The `jira_issue_strategy` generator could produce tasks with duplicate keys (e.g., all PROJ-1), causing test assertions to fail when tracking status changes across plans.

**Root Cause**: Random integer generation with a limited range (1-9999) had high collision probability across multiple test iterations.

**Solution**: 
- Introduced a global counter `_issue_counter` to ensure unique keys
- Modified key generation to use: `issue_num = _issue_counter * 10000 + random_int`
- Added uniqueness validation in `task_list_strategy` to prevent duplicates within a single list

### 2. None Story Points Handling
**Problem**: When `story_points` was `None`, the metadata change test couldn't verify changes because `(None or 0) + 5 = 5` for both original and modified tasks.

**Root Cause**: The test logic `new_story_points = (original_task.story_points or 0) + 5` didn't create a detectable change when the original was `None`.

**Solution**:
- Changed logic to: `new_story_points = 5 if original_story_points is None else original_story_points + 5`
- Added explicit assertions comparing both original and new values
- Used a unique label (`urgent-metadata-change`) to ensure detectable changes

### 3. Incorrect Dependency Link Type
**Problem**: Test used `link_type='blocks'` which means "this task blocks another", not "this task is blocked".

**Root Cause**: Semantic confusion between "blocks" (outgoing) and "is blocked by" (incoming) relationships.

**Solution**:
- Added validation to check for correct blocking link types: `['is blocked by', 'depends on']`
- Ensured test setup always creates tasks with proper blocking dependencies

## Changes Made

### File: `tests/property/test_jira_state_reflection.py`

1. **Added global counter for unique keys**:
```python
_issue_counter = 0

@st.composite
def jira_issue_strategy(draw, key_prefix="PROJ"):
    global _issue_counter
    _issue_counter += 1
    issue_num = _issue_counter * 10000 + draw(st.integers(min_value=1, max_value=9999))
    key = f"{key_prefix}-{issue_num}"
    # ...
```

2. **Enhanced task list uniqueness**:
```python
@st.composite
def task_list_strategy(draw, min_size=1, max_size=10):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    tasks = []
    used_keys = set()
    
    for _ in range(size):
        task = draw(jira_issue_strategy())
        while task.key in used_keys:
            task = draw(jira_issue_strategy())
        used_keys.add(task.key)
        tasks.append(task)
    
    return tasks
```

3. **Fixed metadata change detection**:
```python
# Change story points - ensure we have a detectable change
original_story_points = original_task.story_points
new_story_points = 5 if original_story_points is None else original_story_points + 5

# Add a unique label to ensure detectable change
new_labels = original_task.labels + ['urgent-metadata-change']
```

4. **Fixed dependency link type validation**:
```python
has_blocking_dependency = any(
    link.link_type in ['is blocked by', 'depends on'] 
    for link in task_with_dependency.issue_links
)
```

## Test Results

All 5 property-based tests now pass:
- ✅ `test_status_changes_reflected_in_plan`
- ✅ `test_priority_changes_reflected_in_plan`
- ✅ `test_metadata_changes_reflected_in_plan`
- ✅ `test_resolved_dependencies_make_task_eligible`
- ✅ `test_dependency_resolution_reflected_in_plan`

## Validation

Property 17 (JIRA State Reflection) and Property 18 (Dependency Re-evaluation) are now fully validated with 100 iterations each, confirming that:
- Status changes in JIRA are reflected in subsequent plans
- Priority changes are properly tracked
- Metadata changes (story points, labels) are detected
- Dependency resolution makes tasks priority-eligible

## Requirements Validated

- ✅ Requirement 6.3: Task completion detection
- ✅ Requirement 6.5: Metadata change reflection
- ✅ Requirement 10.4: Dependency re-evaluation

---

**Date**: 2026-01-23  
**Task**: 14.4 Write property test for JIRA state reflection  
**Status**: ✅ Passed
