# TrIAge Logging Guide

## Overview

TrIAge includes comprehensive logging throughout the system to help with debugging, monitoring, and understanding system behavior. All components use Python's standard `logging` module with consistent formatting and log levels.

## Log Levels

TrIAge uses standard Python logging levels:

- **DEBUG**: Detailed information for diagnosing problems. Includes request/response details, task classification details, and internal state.
- **INFO**: Confirmation that things are working as expected. Includes high-level operations like "Fetching tasks", "Generating plan", etc.
- **WARNING**: Indication that something unexpected happened, but the system can continue. Examples: API fallbacks, rate limiting.
- **ERROR**: A serious problem that prevented a specific operation from completing. Examples: authentication failures, connection errors.
- **CRITICAL**: A very serious error that may prevent the system from continuing.

## Configuring Logging

### From Python Code

Use the `configure_logging()` function from the `triage` package:

```python
from triage import configure_logging
import logging

# Basic configuration (INFO level, output to stderr)
configure_logging()

# Debug level logging
configure_logging(level=logging.DEBUG)

# Log to a file
configure_logging(level=logging.INFO, log_file='triage.log')

# Debug logging to both console and file
configure_logging(level=logging.DEBUG, log_file='triage_debug.log')
```

### From CLI

The `triage` CLI supports a `--debug` flag for debug-level logging:

```bash
# Normal logging (INFO level)
triage generate-plan

# Debug logging
triage generate-plan --debug

# Debug logging with output to file
triage generate-plan --debug -o plan.md 2> triage.log
```

## Log Format

All logs use a consistent format:

```
YYYY-MM-DD HH:MM:SS - module_name - LEVEL - message
```

Example:
```
2026-01-23 14:30:15 - triage.jira_client - INFO - Fetching active tasks from JIRA
2026-01-23 14:30:15 - triage.jira_client - DEBUG - JQL query: assignee = currentUser() AND resolution = Unresolved
2026-01-23 14:30:16 - triage.jira_client - INFO - Successfully fetched 15 active tasks
```

## What Gets Logged

### JIRA Client (`triage.jira_client`)

**INFO level:**
- Client initialization with base URL and project filter
- Task fetching operations (active tasks, blocking tasks)
- Number of tasks fetched
- Subtask creation
- API version fallbacks

**DEBUG level:**
- JQL queries being executed
- API endpoints being called
- Request/response details
- Individual task parsing
- Story points and time estimates
- Issue links and labels

**WARNING level:**
- Rate limiting with retry information
- API version fallbacks (v3 → v2)
- Server errors with retry attempts

**ERROR level:**
- Authentication failures
- Connection errors
- Invalid JQL queries
- Rate limit exhaustion
- Server errors after all retries

### Task Classifier (`triage.task_classifier`)

**DEBUG level:**
- Task classification start (key and summary)
- Dependency detection
- Effort estimation
- Administrative task detection
- Category assignment
- Priority eligibility determination

**WARNING level:**
- Invalid story points values

### Plan Generator (`triage.plan_generator`)

**INFO level:**
- Plan generation start
- Number of tasks fetched and classified
- Number of priority-eligible tasks
- Selected priorities (with keys and summaries)
- Administrative task grouping
- Closure rate information
- Plan generation completion

**DEBUG level:**
- Task filtering details
- Task ranking
- Closure tracking directory
- Decomposition proposals

### Approval Manager (`triage.approval_manager`)

**INFO level:**
- Approval manager initialization with timeout
- Plan presentation
- User approval/rejection
- User modifications

**WARNING level:**
- Approval timeouts

### Background Scheduler (`triage.background_scheduler`)

**INFO level:**
- Scheduler start/stop
- Daily plan scheduling
- Operation queuing
- Operation processing

**DEBUG level:**
- Polling loop activity
- Queue operations

**ERROR level:**
- Polling errors
- Queue processing errors

### CLI (`triage.cli`)

**INFO level:**
- CLI command execution
- Configuration loading
- Plan generation workflow
- Output file writing

**ERROR level:**
- Configuration validation failures
- Authentication errors
- Connection errors

**CRITICAL level:**
- Unexpected errors

## Example Logging Sessions

### Normal Plan Generation (INFO level)

```
2026-01-23 14:30:15 - triage.cli - INFO - Starting TrIAge plan generation
2026-01-23 14:30:15 - triage.jira_client - INFO - Initializing JIRA client for https://company.atlassian.net
2026-01-23 14:30:15 - triage.jira_client - INFO - Project filter: PROJ
2026-01-23 14:30:15 - triage.plan_generator - INFO - Plan generator initialized with closure tracking at: .triage/closure
2026-01-23 14:30:15 - triage.plan_generator - INFO - Generating daily plan
2026-01-23 14:30:15 - triage.jira_client - INFO - Fetching active tasks from JIRA
2026-01-23 14:30:16 - triage.jira_client - INFO - Successfully fetched 15 active tasks
2026-01-23 14:30:16 - triage.plan_generator - INFO - Fetched 15 active tasks
2026-01-23 14:30:16 - triage.plan_generator - INFO - Classified 15 tasks
2026-01-23 14:30:16 - triage.plan_generator - INFO - Found 8 priority-eligible tasks
2026-01-23 14:30:16 - triage.plan_generator - INFO - Selected 3 priority tasks
2026-01-23 14:30:16 - triage.plan_generator - INFO -   Priority 1: PROJ-123 - Implement user authentication
2026-01-23 14:30:16 - triage.plan_generator - INFO -   Priority 2: PROJ-125 - Fix login bug
2026-01-23 14:30:16 - triage.plan_generator - INFO -   Priority 3: PROJ-127 - Update API documentation
2026-01-23 14:30:16 - triage.plan_generator - INFO - Grouped 3 administrative tasks (60 minutes)
2026-01-23 14:30:16 - triage.plan_generator - INFO - Identified 9 other tasks for reference
2026-01-23 14:30:16 - triage.plan_generator - INFO - Previous closure rate: 66.67%
2026-01-23 14:30:16 - triage.plan_generator - INFO - Daily plan generated successfully for 2026-01-23
2026-01-23 14:30:16 - triage.cli - INFO - Plan generation completed successfully
```

### Debug Plan Generation (DEBUG level)

```
2026-01-23 14:35:20 - triage.cli - INFO - Starting TrIAge plan generation
2026-01-23 14:35:20 - triage.jira_client - INFO - Initializing JIRA client for https://company.atlassian.net
2026-01-23 14:35:20 - triage.jira_client - INFO - Project filter: PROJ
2026-01-23 14:35:20 - triage.jira_client - DEBUG - Max retries: 3, Initial backoff: 1.0s
2026-01-23 14:35:20 - triage.jira_client - DEBUG - JIRA client initialized successfully
2026-01-23 14:35:20 - triage.plan_generator - INFO - Plan generator initialized with closure tracking at: .triage/closure
2026-01-23 14:35:20 - triage.plan_generator - INFO - Generating daily plan
2026-01-23 14:35:20 - triage.plan_generator - DEBUG - Fetching active tasks from JIRA
2026-01-23 14:35:20 - triage.jira_client - INFO - Fetching active tasks from JIRA
2026-01-23 14:35:20 - triage.jira_client - DEBUG - JQL query: assignee = currentUser() AND resolution = Unresolved AND project = PROJ
2026-01-23 14:35:20 - triage.jira_client - DEBUG - Fetching tasks using API v3
2026-01-23 14:35:20 - triage.jira_client - DEBUG - Endpoint: https://company.atlassian.net/rest/api/3/search/jql
2026-01-23 14:35:20 - triage.jira_client - DEBUG - Making GET request to https://company.atlassian.net/rest/api/3/search/jql
2026-01-23 14:35:21 - triage.jira_client - DEBUG - Request successful: GET https://company.atlassian.net/rest/api/3/search/jql -> 200
2026-01-23 14:35:21 - triage.jira_client - DEBUG - Parsing issue: PROJ-123
2026-01-23 14:35:21 - triage.jira_client - DEBUG -   Story points: 3
2026-01-23 14:35:21 - triage.jira_client - DEBUG -   Labels: backend, security
2026-01-23 14:35:21 - triage.jira_client - DEBUG - Parsing issue: PROJ-125
2026-01-23 14:35:21 - triage.jira_client - DEBUG -   Story points: 2
2026-01-23 14:35:21 - triage.jira_client - DEBUG - Parsed 15 issues from response
2026-01-23 14:35:21 - triage.jira_client - INFO - Successfully fetched 15 active tasks
2026-01-23 14:35:21 - triage.plan_generator - INFO - Fetched 15 active tasks
2026-01-23 14:35:21 - triage.plan_generator - DEBUG - Classifying tasks
2026-01-23 14:35:21 - triage.task_classifier - DEBUG - Classifying task: PROJ-123 - Implement user authentication
2026-01-23 14:35:21 - triage.task_classifier - DEBUG -   Task PROJ-123 estimated effort: 1.0 days
2026-01-23 14:35:21 - triage.task_classifier - DEBUG -   Task PROJ-123 category: priority_eligible
2026-01-23 14:35:21 - triage.task_classifier - DEBUG -   Task PROJ-123 is PRIORITY ELIGIBLE
...
```

### Error Scenarios

**Authentication Error:**
```
2026-01-23 14:40:10 - triage.jira_client - ERROR - Authentication failed: 401 - Unauthorized. Please verify your JIRA credentials (email and API token).
```

**Connection Error with Retries:**
```
2026-01-23 14:45:15 - triage.jira_client - ERROR - Connection error: Failed to connect to JIRA
2026-01-23 14:45:15 - triage.jira_client - INFO - Retrying after connection error in 1.0s...
2026-01-23 14:45:16 - triage.jira_client - INFO - Retry attempt 1/3 for GET https://company.atlassian.net/rest/api/3/search/jql
2026-01-23 14:45:16 - triage.jira_client - ERROR - Connection error: Failed to connect to JIRA
2026-01-23 14:45:16 - triage.jira_client - INFO - Retrying after connection error in 2.0s...
...
```

**Rate Limiting:**
```
2026-01-23 14:50:20 - triage.jira_client - WARNING - Rate limited. Retry-After header: 60.0s
2026-01-23 14:50:20 - triage.jira_client - INFO - Waiting 60.00s before retry...
```

## Troubleshooting with Logs

### Problem: Tasks not being fetched

Enable debug logging and check for:
- JQL query correctness
- API endpoint responses
- Authentication errors
- Network connectivity issues

```bash
triage generate-plan --debug 2> debug.log
grep -i "jql\|error\|failed" debug.log
```

### Problem: Tasks classified incorrectly

Enable debug logging and examine:
- Task classification details
- Dependency detection
- Effort estimation
- Category assignment

```bash
triage generate-plan --debug 2> debug.log
grep "Classifying task\|category\|eligible" debug.log
```

### Problem: Plan generation issues

Check logs for:
- Number of tasks fetched vs classified
- Priority selection logic
- Admin task grouping
- Filtering criteria

```bash
triage generate-plan --debug 2> debug.log
grep "priority\|admin\|eligible" debug.log
```

## Best Practices

1. **Use INFO level for production**: Provides enough information without overwhelming output
2. **Use DEBUG level for troubleshooting**: Detailed information for diagnosing issues
3. **Log to files for long-running operations**: Easier to analyze and share
4. **Monitor ERROR and WARNING logs**: Indicates issues that need attention
5. **Include logs when reporting issues**: Helps maintainers diagnose problems

## Log File Management

When logging to files:

```python
from triage import configure_logging
import logging
from datetime import datetime

# Create timestamped log file
log_file = f"triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
configure_logging(level=logging.DEBUG, log_file=log_file)
```

Consider:
- Rotating log files daily or by size
- Archiving old logs
- Setting appropriate file permissions
- Excluding logs from version control (add `*.log` to `.gitignore`)

## Integration with External Tools

### Syslog

```python
import logging
import logging.handlers

# Configure syslog handler
syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
syslog_handler.setLevel(logging.INFO)

logger = logging.getLogger('triage')
logger.addHandler(syslog_handler)
```

### JSON Logging

For structured logging (useful for log aggregation tools):

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_data)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger('triage').addHandler(handler)
```

## See Also

- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [TrIAge Error Handling](./JIRA_API_MIGRATION.md)
