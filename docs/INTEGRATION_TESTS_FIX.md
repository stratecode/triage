# Integration Tests Fix - Memory and Blocking Issues

## Problem

The integration tests were experiencing severe issues:
1. **Blocking indefinitely** - Tests would hang waiting for user input
2. **Massive memory consumption** - Background threads were accumulating and not being cleaned up
3. **Never completing** - Tests had to be manually killed

## Root Causes

### 1. Blocking User Input
The `ApprovalManager` class uses `input()` calls that block indefinitely waiting for user input. In automated tests, this caused tests to hang forever.

### 2. Background Threads Not Cleaned Up
The `BackgroundScheduler` starts daemon threads for:
- Polling loop (checking for blocking tasks)
- Queue processing loop

These threads were:
- Not being stopped properly after tests
- Accumulating with each test run
- Consuming memory continuously
- Running infinite loops

### 3. Missing Timeout Configuration
The `ApprovalManager` had a default 24-hour timeout, which is appropriate for production but not for tests.

## Solutions Implemented

### 1. Non-Blocking Approval Manager for Tests
```python
# Create approval manager with no timeout for tests
approval_manager = ApprovalManager(timeout_seconds=0)

# Mock user input to avoid blocking
with patch('builtins.input', return_value='yes'):
    result = approval_manager.present_plan(plan)
```

### 2. Proper Thread Cleanup in Scheduler Tests
```python
try:
    # Start scheduler
    scheduler.start()
    
    # Wait very briefly for one polling cycle
    time.sleep(0.2)  # 200ms
    
    # Verify behavior
    assert mock_fetch_blocking.called
    
finally:
    # Always stop scheduler to clean up threads
    scheduler.stop()
    
    # Give threads time to clean up
    time.sleep(0.1)
```

### 3. Very Short Poll Intervals for Tests
```python
# Create scheduler with very short poll interval for testing
scheduler = BackgroundScheduler(
    jira_client=jira_client,
    plan_generator=plan_generator,
    poll_interval_minutes=0.001  # 0.06 seconds instead of 15 minutes
)
```

### 4. Temporary Directories for Closure Tracking
```python
@pytest.fixture
def temp_closure_dir():
    """Create a temporary directory for closure tracking."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
```

This prevents tests from polluting the workspace with closure tracking files.

### 5. Flexible Markdown Assertions
```python
# Admin block only appears if there are admin tasks
if plan.admin_block.tasks:
    assert 'Administrative Block' in markdown
```

This makes tests more robust to different plan configurations.

## Test Coverage

The integration tests now cover:

### 1. Daily Plan Generation Workflow
- ✅ Complete plan generation (fetch → classify → select → format)
- ✅ Plan approval workflow with mocked user input

### 2. Blocking Task Interruption Workflow
- ✅ Blocking task detection and re-planning
- ✅ Background scheduler detecting blocking tasks (with proper cleanup)

### 3. Long-Running Task Decomposition Workflow
- ✅ Complete decomposition workflow (identify → propose → approve → create)

### 4. End-to-End Workflow
- ✅ Full day workflow (morning plan → blocking task → re-plan → closure tracking)

## Test Execution Results

```bash
$ python -m pytest tests/integration/test_workflows.py -v

tests/integration/test_workflows.py::TestDailyPlanGenerationWorkflow::test_complete_plan_generation_workflow PASSED
tests/integration/test_workflows.py::TestDailyPlanGenerationWorkflow::test_plan_with_approval_workflow PASSED
tests/integration/test_workflows.py::TestBlockingTaskInterruptionWorkflow::test_blocking_task_detection_and_replanning PASSED
tests/integration/test_workflows.py::TestBlockingTaskInterruptionWorkflow::test_background_scheduler_blocking_detection PASSED
tests/integration/test_workflows.py::TestLongRunningTaskDecompositionWorkflow::test_complete_decomposition_workflow PASSED
tests/integration/test_workflows.py::TestEndToEndWorkflow::test_full_day_workflow PASSED

========================================= 6 passed in 5.45s =========================================
```

All tests pass in **5.45 seconds** with no blocking or memory issues.

## Key Lessons

1. **Always mock blocking I/O in tests** - User input, network calls, file operations
2. **Clean up threads explicitly** - Use try/finally blocks to ensure cleanup
3. **Use short timeouts in tests** - Don't use production timeouts in test environments
4. **Isolate test state** - Use temporary directories and clean up after tests
5. **Make assertions flexible** - Don't assume specific output when it can vary

## Future Improvements

1. Consider using `pytest-timeout` plugin to automatically kill hanging tests
2. Add memory profiling to detect leaks early
3. Consider using `asyncio` instead of threads for better control
4. Add integration tests for error scenarios (JIRA unavailable, auth failures, etc.)
