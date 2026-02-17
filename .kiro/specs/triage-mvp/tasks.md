# Implementation Plan: AI Secretary (MVP-Driven)

## Version
v1.0-mvp

## Objective

Deliver a **usable MVP** of the AI Secretary as early as possible, validating:
- Daily plan usefulness
- Cognitive load reduction
- Task closure focus

All non-essential automation and background complexity is deferred until value is proven.

## Scope Definitions

### MVP Scope (Mandatory)
The MVP must support:
- Manual daily plan generation
- Task classification
- Priority selection (≤ 3)
- Administrative task grouping
- Structured markdown output
- Manual approval (approve / reject)
- CLI-based interaction

### Post-MVP Scope (Deferred)
- Automatic background polling
- Blocking task auto-detection
- Operation queues and prioritization
- Advanced approval behaviors (timeouts, feedback loops)
- Metrics refinement and optimization

## Tasks

### MVP Phase (Tasks 1-8)

- [x] 1. Project Setup and Core Models (MVP)
  - Create Python project with virtual environment
  - Set up dependencies: `requests` (JIRA API), `pytest`, `hypothesis`, `python-markdown`
  - Define core data models: `JiraIssue`, `IssueLink`, `TaskClassification`, `TaskCategory`, `DailyPlan`, `AdminBlock`, `SubtaskSpec`, `ApprovalResult`
  - Implement `DailyPlan.to_markdown()` method
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 2. Markdown Output Validation (MVP)
  - [x] 2.1 Write property test for markdown validity
    - **Property 22: Markdown Validity**
    - **Validates: Requirements 9.1, 9.5**
    - Generate random `DailyPlan` objects and verify markdown output is parseable

  - [x] 2.2 Write property test for task information completeness
    - **Property 23: Task Information Completeness**
    - **Validates: Requirements 9.2**
    - Verify all tasks in markdown output contain ID, title, effort, and dependencies

- [x] 3. JIRA Client — Read-Only Core (MVP)
  - [x] 3.1 Create `JiraClient` class with authentication
    - Implement `__init__` with base URL, email, and API token
    - Set up HTTP session with authentication headers
    - _Requirements: 6.1_

  - [x] 3.2 Implement task fetching
    - Implement `fetch_active_tasks()` using JQL: `assignee = currentUser() AND resolution = Unresolved`
    - Parse JIRA API responses into `JiraIssue` objects
    - ❗ No scheduler ❗ No auto-updates ❗ No background threads
    - _Requirements: 1.1_

- [x] 4. Task Classifier (MVP)
  - [x] 4.1 Create `TaskClassifier` class with classification logic
    - Implement `classify_task()` to categorize tasks
    - Implement `has_third_party_dependencies()` to check issue links
    - Implement `estimate_effort_days()` using story points or time estimates (conservative default ≥ 1 day)
    - Implement `is_administrative()` to identify admin tasks by labels/type
    - _Requirements: 1.2, 2.1, 2.3, 2.4, 2.5, 10.1_

  - [x] 4.2 Write property test for classification completeness
    - **Property 3: Task Classification Completeness**
    - **Validates: Requirements 1.2, 2.1**
    - Generate random `JiraIssue` objects and verify all classifications contain required fields

  - [x] 4.3 Write property test for classification idempotence
    - **Property 4: Classification Idempotence**
    - **Validates: Requirements 2.2**
    - Verify classifying the same task multiple times produces equivalent results

  - [x] 4.4 Write property test for dependency detection
    - **Property 27: Dependency Detection Completeness**
    - **Validates: Requirements 10.1**
    - Generate tasks with various dependency structures and verify all are detected

  - [x] 4.5 Write property test for administrative task marking
    - **Property 5: Administrative Task Grouping** (partial - marking aspect)
    - **Validates: Requirements 2.3**
    - Verify tasks with admin labels/types are marked correctly

- [x] 5. Plan Generator — Daily Plan Only (MVP)
  - [x] 5.1 Create `PlanGenerator` class with task selection algorithm
    - Implement task filtering: exclude dependencies, exclude >1 day effort, exclude admin
    - Implement task ranking: by priority, then effort, then age
    - Implement priority selection: top 3 eligible tasks
    - Implement admin task grouping with 90-minute limit
    - ❗ No re-planning yet ❗ No blocking logic yet
    - _Requirements: 1.3, 1.4, 1.5, 5.1, 5.2, 5.4, 5.5_

  - [x] 5.2 Implement `generate_daily_plan()` method
    - Fetch tasks via JIRA Client
    - Classify all tasks via Task Classifier
    - Apply selection algorithm
    - Create `DailyPlan` object with priorities and admin block
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 5.3 Write property test for priority count constraint
    - **Property 1: Priority Count Constraint**
    - **Validates: Requirements 1.5, 11.1**
    - Generate random task sets and verify plans have at most 3 priorities

  - [x] 5.4 Write property test for priority task eligibility
    - **Property 2: Priority Task Eligibility**
    - **Validates: Requirements 1.3, 1.4, 2.4, 5.1, 10.2, 10.3**
    - Verify all priority tasks have no dependencies, ≤1 day effort, and are not admin

  - [x] 5.5 Write property test for administrative task grouping
    - **Property 5: Administrative Task Grouping**
    - **Validates: Requirements 2.3, 5.1, 5.2, 5.4**
    - Verify all admin tasks are in admin block, not in priorities, and block ≤90 minutes

  - [x] 5.6 Write property test for admin overflow handling
    - **Property 7: Administrative Overflow Handling**
    - **Validates: Requirements 5.5**
    - Generate task sets with >90 minutes of admin work and verify overflow is deferred

- [x] 6. Minimal CLI Interface (MVP)
  - Create CLI entry point with `generate-plan` command
  - Output markdown plan to stdout or file
  - Add configuration support via environment variables or config file for:
    - JIRA credentials (base URL, email, API token)
    - Low-energy window configuration
  - **Purpose: Make the system usable immediately**
  - _Requirements: 1.1, 6.1, 9.1_

- [x] 7. Minimal Approval Manager (MVP)
  - [x] 7.1 Create `ApprovalManager` class (simplified)
    - Implement `present_plan()` to display plan and collect approval
    - Support approve / reject only
    - ❗ No expirations ❗ No modifications ❗ No feedback loops
    - _Requirements: 1.7, 7.1_

  - [x] 7.2 Write property test for plan approval requirement
    - **Property 13: Plan Approval Requirement**
    - **Validates: Requirements 1.7, 7.1**
    - Verify plans are not finalized without explicit approval

- [x] 8. MVP End-to-End Validation
  - Manual run: fetch tasks → generate plan → approve or reject
  - Verify:
    - Plan usefulness
    - Cognitive load reduction
    - Correct exclusions (dependencies, long tasks, admin tasks)
  - 📌 **At this point, MVP is complete and usable**
  - _Requirements: All MVP requirements_

### Post-MVP Phase (Tasks 9-14)

- [x] 9. Long-Running Task Decomposition
  - [x] 9.1 Implement `propose_decomposition()` method
    - Identify long-running tasks (>1 day)
    - Generate subtask proposals with daily-closable estimates
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 9.2 Implement subtask creation in JIRA Client
    - Implement `create_subtask()` to create subtasks with parent linking
    - _Requirements: 4.5_

  - [x] 9.3 Add decomposition approval to Approval Manager
    - Implement `present_decomposition()` to display subtask proposals
    - Approval-gated subtask creation
    - _Requirements: 4.4, 7.2_

  - [x] 9.4 Write property test for long-running task identification
    - **Property 11: Long-Running Task Identification**
    - **Validates: Requirements 1.4, 4.1**
    - Verify tasks >1 day are identified for decomposition

  - [x] 9.5 Write property test for decomposition subtask constraints
    - **Property 12: Decomposition Subtask Constraints**
    - **Validates: Requirements 4.2, 4.3**
    - Verify all proposed subtasks have ≤1 day effort

  - [x] 9.6 Write property test for decomposition approval requirement
    - **Property 14: Decomposition Approval Requirement**
    - **Validates: Requirements 4.4, 7.2**
    - Verify subtasks are not created without approval

- [x] 10. Task Closure Tracking
  - [x] 10.1 Add closure tracking to Plan Generator
    - Implement completion recording for priority tasks
    - Implement closure rate calculation
    - Implement incomplete task prompting
    - Include previous day's closure rate in daily plans
    - _Requirements: 12.1, 12.2, 12.3, 12.5_

  - [x] 10.2 Write property test for closure rate calculation
    - **Property 30: Closure Rate Calculation**
    - **Validates: Requirements 12.2**
    - Generate random completion sets and verify closure rate formula

  - [x] 10.3 Write property test for closure rate display
    - **Property 31: Closure Rate Display**
    - **Validates: Requirements 12.3**
    - Verify plans after day 1 include previous closure rate

- [x] 11. Background Scheduler
  - [x] 11.1 Create `BackgroundScheduler` class with polling logic
    - Implement `start()` to begin background polling in separate thread
    - Implement `stop()` to gracefully stop polling
    - Implement polling loop to check for blocking tasks at configurable intervals
    - Implement `schedule_daily_plan()` for automatic plan generation
    - _Requirements: 8.1, 8.3_

  - [x] 11.2 Implement operation queue with priority ordering
    - Create operation queue that prioritizes blocking task operations
    - Implement queue processing logic
    - _Requirements: 8.5_

  - [x] 11.3 Implement notification system
    - Implement notifications for plan completion
    - Implement status updates for long-running operations
    - _Requirements: 8.2, 8.4_

  - [x] 11.4 Implement blocking task fetching in JIRA Client
    - Implement `fetch_blocking_tasks()` using JQL: `assignee = currentUser() AND priority = Blocker AND resolution = Unresolved`
    - _Requirements: 3.1_

  - [x] 11.5 Write property test for blocking task detection
    - **Property 8: Blocking Task Detection**
    - **Validates: Requirements 3.1**
    - Verify blocking tasks are detected during polling

  - [x] 11.6 Write property test for operation priority ordering
    - **Property 20: Operation Priority Ordering**
    - **Validates: Requirements 8.5**
    - Verify blocking operations are processed before regular operations

- [x] 12. Re-planning Flow
  - [x] 12.1 Implement `generate_replan()` method
    - Accept blocking task and current plan
    - Mark current plan as interrupted
    - Generate new plan with blocking task as priority
    - _Requirements: 3.2, 3.3, 3.4_

  - [x] 12.2 Add blocking task notification to Approval Manager
    - Implement `notify_blocking_task()` to notify of interruptions
    - Approval-gated plan replacement
    - _Requirements: 3.5, 7.3_

  - [x] 12.3 Write property test for re-planning trigger
    - **Property 9: Re-planning Trigger**
    - **Validates: Requirements 3.2, 3.3**
    - Verify blocking tasks trigger plan interruption and re-planning

  - [x] 12.4 Write property test for blocking task inclusion
    - **Property 10: Blocking Task Inclusion**
    - **Validates: Requirements 3.4**
    - Verify re-plans include the blocking task in priorities

- [x] 13. Advanced Approval Behaviors
  - [x] 13.1 Add approval timeouts
    - Implement configurable timeout for approval requests
    - Mark proposals as expired after timeout
    - _Requirements: 7.1, 7.3_

  - [x] 13.2 Add feedback collection on rejection
    - Request feedback when user rejects a proposal
    - Generate alternative based on feedback
    - _Requirements: 7.4_

  - [x] 13.3 Add user modification support
    - Accept user modifications to proposals
    - Validate modifications against constraints
    - _Requirements: 7.5_

  - [x] 13.4 Write property test for user modification preservation
    - **Property 16: User Modification Preservation**
    - **Validates: Requirements 7.5**
    - Verify user modifications are preserved and not reverted

- [-] 14. Integration, Hardening, and Refinement
  - [x] 14.1 Add comprehensive error handling for JIRA API
    - Handle connection errors (network timeouts, connection failures)
    - Handle authentication errors (401/403 responses)
    - Handle rate limiting (429 responses with exponential backoff)
    - Handle invalid JQL queries (400 responses)
    - _Requirements: 6.4_

  - [x] 14.2 Write unit tests for JIRA Client error handling
    - Test connection failure handling
    - Test authentication error handling
    - Test rate limiting with retry logic
    - _Requirements: 6.4_

  - [x] 14.3 Add JIRA synchronization and state reflection
    - Implement detection of task status changes
    - Implement detection of metadata changes
    - Implement dependency re-evaluation
    - _Requirements: 6.3, 6.5, 10.4_

  - [x] 14.4 Write property test for JIRA state reflection
    - **Property 17: JIRA State Reflection**
    - **Validates: Requirements 6.3, 6.5, 10.4**
    - Verify changes in JIRA are reflected in subsequent plans

  - [x] 14.5 Write property test for dependency re-evaluation
    - **Property 18: Dependency Re-evaluation**
    - **Validates: Requirements 10.4**
    - Verify tasks with resolved dependencies become priority-eligible

  - [x] 14.6 Write integration tests
    - Test complete daily plan generation workflow
    - Test blocking task interruption and re-planning workflow
    - Test long-running task decomposition workflow
    - _Requirements: All_

  - [x] 14.7 Add logging and debugging support
    - Add comprehensive logging throughout the system
    - Ensure all error cases are logged
    - _Requirements: 6.4_

## Exit Criteria

### MVP Exit Criteria
The MVP is considered successful when:
- The user uses it daily without friction
- Daily planning time is reduced
- Priorities feel realistic and achievable
- No automation feels intrusive

### Full System Exit Criteria
The project is considered complete when:
- All property tests pass (minimum 100 iterations each)
- All integration tests pass
- Background automation works reliably
- Error handling is comprehensive
- User relies on the system without manual intervention

## Notes

- Each property test should run minimum 100 iterations
- Property tests use Hypothesis for random input generation
- All property tests are tagged with: `Feature: ai-secretary, Property {N}: {property_text}`
- JIRA Client should use API token authentication for simplicity
- Background Scheduler uses threading for asynchronous operations (Post-MVP only)
- Approval Manager uses CLI prompts for MVP
- **MVP-First Approach**: Tasks 1-8 deliver a usable system before any automation
- **No Background Threads in MVP**: All automation is deferred to Post-MVP phase
- **Focus on Value**: Every MVP task must contribute to immediate usability
