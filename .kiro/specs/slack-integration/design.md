# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Design Document: Slack Integration

## Overview

The Slack Integration extends TrIAge's user interaction capabilities by providing a conversational, notification-driven interface through Slack. This design maintains the API-first architecture where the Slack bot acts as a thin client over the existing TrIAge HTTP API, with no business logic in the Slack handlers.

The integration supports both proactive notifications (daily plans, blocking task alerts) and reactive interactions (slash commands, button clicks, conversational feedback). All user interactions flow through the Slack bot to the TrIAge API, which handles authentication, authorization, and business logic.

### Key Design Principles

1. **Slack as Thin Client**: All business logic remains in the TrIAge API; Slack handlers only translate between Slack's format and API calls
2. **Event-Driven Architecture**: Webhook-based interaction model with asynchronous processing
3. **Stateless Handlers**: No persistent state in Slack bot; all state managed by TrIAge API
4. **Multi-User Isolation**: Each user's data and interactions are completely isolated
5. **Graceful Degradation**: Errors in Slack delivery don't block core TrIAge functionality

## Architecture

### System Components

```
┌─────────────────┐
│  Slack Client   │
│   (User's UI)   │
└────────┬────────┘
         │
         │ User Actions (buttons, commands)
         ▼
┌─────────────────┐
│   Slack API     │
│  (Slack Cloud)  │
└────────┬────────┘
         │
         │ Webhooks & Events
         ▼
┌─────────────────────────────────────┐
│     Slack Bot Service               │
│  ┌──────────────────────────────┐  │
│  │  Webhook Handler             │  │
│  │  - Event validation          │  │
│  │  - Deduplication             │  │
│  │  - Async dispatch            │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Message Formatter           │  │
│  │  - Block Kit generation      │  │
│  │  - Template rendering        │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Command Handler             │  │
│  │  - Slash command routing     │  │
│  │  - Response formatting       │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  OAuth Manager               │  │
│  │  - Installation flow         │  │
│  │  - Token management          │  │
│  └──────────────────────────────┘  │
└────────┬────────────────────────────┘
         │
         │ HTTP API Calls
         ▼
┌─────────────────────────────────────┐
│      TrIAge API (Existing)          │
│  - Plan generation                  │
│  - Approval workflow                │
│  - Task classification              │
│  - JIRA integration                 │
└─────────────────────────────────────┘
```

### Communication Flow

**Daily Plan Delivery:**
1. TrIAge API generates daily plan
2. TrIAge API calls Slack Bot Service notification endpoint
3. Slack Bot formats plan using Block Kit
4. Slack Bot sends message to user's configured channel
5. User sees interactive message with approval buttons

**User Approval:**
1. User clicks "Approve" button in Slack
2. Slack sends interaction webhook to Slack Bot
3. Slack Bot validates signature and extracts payload
4. Slack Bot calls TrIAge API approval endpoint
5. TrIAge API processes approval
6. Slack Bot updates message to show approval status

**Slash Command:**
1. User types `/triage plan` in Slack
2. Slack sends command webhook to Slack Bot
3. Slack Bot acknowledges immediately (< 3s)
4. Slack Bot calls TrIAge API plan generation endpoint
5. TrIAge API generates plan asynchronously
6. Slack Bot receives plan and sends formatted message

## Components and Interfaces

### 1. Slack Bot Service

A new Python service that handles all Slack-specific logic. This service is deployed independently and communicates with the TrIAge API.

**Technology Stack:**
- Python 3.11+
- `slack-sdk` (official Slack SDK for Python)
- `slack-bolt` (framework for Slack apps)
- `httpx` (async HTTP client for TrIAge API calls)
- `pydantic` (data validation)

**Key Responsibilities:**
- Receive and validate Slack webhooks
- Format messages using Block Kit
- Handle OAuth installation flow
- Route slash commands
- Process interactive button clicks
- Manage webhook deduplication

### 2. Webhook Handler

Receives all incoming events from Slack and routes them to appropriate handlers.

**Interface:**
```python
@dataclass
class WebhookEvent:
    event_id: str
    event_type: str  # "slash_command", "block_action", "message", etc.
    user_id: str
    team_id: str
    payload: dict
    timestamp: datetime

class WebhookHandler:
    async def handle_event(self, event: WebhookEvent) -> WebhookResponse:
        """
        Process incoming webhook event.
        Returns immediate response for Slack (< 3s requirement).
        """
        pass
    
    async def validate_signature(self, headers: dict, body: bytes) -> bool:
        """Verify webhook came from Slack using signing secret."""
        pass
    
    async def deduplicate_event(self, event_id: str) -> bool:
        """Check if event was already processed."""
        pass
```

**Deduplication Strategy:**
- Use Redis or in-memory cache with TTL (5 minutes)
- Store event IDs as keys
- Return early if event ID exists

### 3. Message Formatter

Converts TrIAge data structures into Slack Block Kit format.

**Interface:**
```python
@dataclass
class SlackMessage:
    blocks: list[dict]
    text: str  # Fallback text for notifications
    thread_ts: Optional[str] = None
    
class MessageFormatter:
    def format_daily_plan(self, plan: DailyPlan) -> SlackMessage:
        """Convert DailyPlan to Block Kit message with approval buttons."""
        pass
    
    def format_blocking_task_alert(self, task: JiraIssue) -> SlackMessage:
        """Format blocking task notification."""
        pass
    
    def format_approval_confirmation(self, approved: bool) -> SlackMessage:
        """Format approval status update."""
        pass
    
    def format_error_message(self, error: str, suggestion: str) -> SlackMessage:
        """Format user-friendly error message."""
        pass
```

**Block Kit Structure for Daily Plan:**
```json
{
  "blocks": [
    {
      "type": "header",
      "text": {"type": "plain_text", "text": "📋 Your Daily Plan - Jan 15, 2026"}
    },
    {
      "type": "section",
      "text": {"type": "mrkdwn", "text": "*Priority Tasks (Max 3)*"}
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Task:* <https://jira.example.com/browse/PROJ-123|PROJ-123>"},
        {"type": "mrkdwn", "text": "*Urgency:* 🔴 High"},
        {"type": "mrkdwn", "text": "*Summary:* Fix critical authentication bug"},
        {"type": "mrkdwn", "text": "*Effort:* 0.5 days"}
      ]
    },
    {
      "type": "divider"
    },
    {
      "type": "section",
      "text": {"type": "mrkdwn", "text": "*Administrative Block (90 min)*\n• PROJ-456: Update documentation\n• PROJ-789: Review PR"}
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": {"type": "plain_text", "text": "✅ Approve"},
          "style": "primary",
          "action_id": "approve_plan",
          "value": "plan_id_12345"
        },
        {
          "type": "button",
          "text": {"type": "plain_text", "text": "❌ Reject"},
          "style": "danger",
          "action_id": "reject_plan",
          "value": "plan_id_12345"
        },
        {
          "type": "button",
          "text": {"type": "plain_text", "text": "✏️ Modify"},
          "action_id": "modify_plan",
          "value": "plan_id_12345"
        }
      ]
    }
  ]
}
```

### 4. Command Handler

Processes slash commands and routes them to TrIAge API.

**Interface:**
```python
@dataclass
class SlashCommand:
    command: str  # "/triage"
    text: str     # "plan", "status", "help"
    user_id: str
    team_id: str
    channel_id: str
    response_url: str  # For delayed responses

class CommandHandler:
    async def handle_command(self, cmd: SlashCommand) -> SlackMessage:
        """Route command to appropriate handler."""
        pass
    
    async def handle_plan_command(self, cmd: SlashCommand) -> SlackMessage:
        """Trigger plan generation via API."""
        pass
    
    async def handle_status_command(self, cmd: SlashCommand) -> SlackMessage:
        """Fetch and display current plan status."""
        pass
    
    async def handle_help_command(self, cmd: SlashCommand) -> SlackMessage:
        """Display available commands."""
        pass
```

**Supported Commands:**
- `/triage plan [date]` - Generate plan for today or specified date
- `/triage status` - Show current plan and approval status
- `/triage config` - Display/modify configuration
- `/triage help` - Show command documentation

### 5. OAuth Manager

Handles workspace installation and token management.

**Interface:**
```python
@dataclass
class WorkspaceToken:
    team_id: str
    access_token: str
    bot_user_id: str
    scope: str
    installed_at: datetime
    
class OAuthManager:
    async def initiate_install(self) -> str:
        """Generate OAuth URL for installation."""
        pass
    
    async def handle_callback(self, code: str) -> WorkspaceToken:
        """Exchange OAuth code for access token."""
        pass
    
    async def store_token(self, token: WorkspaceToken) -> None:
        """Securely store workspace token (encrypted)."""
        pass
    
    async def get_token(self, team_id: str) -> Optional[WorkspaceToken]:
        """Retrieve token for workspace."""
        pass
    
    async def revoke_token(self, team_id: str) -> None:
        """Delete token when workspace uninstalls."""
        pass
```

**Required OAuth Scopes:**
- `chat:write` - Send messages to users
- `commands` - Register and handle slash commands
- `users:read` - Get user information
- `channels:read` - List channels for configuration
- `im:write` - Send direct messages

### 6. TrIAge API Extensions

New endpoints added to existing TrIAge API to support Slack integration.

**New Endpoints:**

```python
# Notification delivery
POST /api/v1/notifications/slack/plan
{
  "user_id": "U12345",
  "team_id": "T12345",
  "plan": { /* DailyPlan object */ }
}

# Notification delivery for blocking tasks
POST /api/v1/notifications/slack/blocking-task
{
  "user_id": "U12345",
  "team_id": "T12345",
  "task": { /* JiraIssue object */ }
}

# User configuration
GET /api/v1/users/{user_id}/slack-config
PUT /api/v1/users/{user_id}/slack-config
{
  "notification_channel": "C12345" | "DM",
  "delivery_time": "09:00",
  "notifications_enabled": true
}

# User mapping (Slack ID to TrIAge user)
POST /api/v1/users/slack-mapping
{
  "slack_user_id": "U12345",
  "slack_team_id": "T12345",
  "jira_email": "user@example.com"
}
```

### 7. Interaction Handler

Processes button clicks and interactive elements.

**Interface:**
```python
@dataclass
class BlockAction:
    action_id: str  # "approve_plan", "reject_plan", etc.
    value: str      # Plan ID or other context
    user_id: str
    team_id: str
    message_ts: str  # For updating the message
    response_url: str

class InteractionHandler:
    async def handle_action(self, action: BlockAction) -> None:
        """Process button click or interactive element."""
        pass
    
    async def handle_approve(self, action: BlockAction) -> None:
        """Process plan approval."""
        pass
    
    async def handle_reject(self, action: BlockAction) -> None:
        """Start feedback collection thread."""
        pass
    
    async def handle_modify(self, action: BlockAction) -> None:
        """Provide modification instructions."""
        pass
    
    async def update_message(self, message_ts: str, new_blocks: list[dict]) -> None:
        """Update existing message (e.g., disable buttons after approval)."""
        pass
```

## Data Models

### Slack-Specific Models

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal

@dataclass
class SlackUser:
    """Maps Slack user to TrIAge user."""
    slack_user_id: str
    slack_team_id: str
    triage_user_id: str
    jira_email: str
    display_name: str
    
@dataclass
class SlackConfig:
    """User-specific Slack configuration."""
    user_id: str
    notification_channel: str  # Channel ID or "DM"
    delivery_time: str  # HH:MM format
    notifications_enabled: bool
    timezone: str
    
@dataclass
class PendingFeedback:
    """Tracks feedback collection state."""
    feedback_id: str
    user_id: str
    plan_id: str
    thread_ts: str
    created_at: datetime
    expires_at: datetime
    reminder_sent: bool
    
@dataclass
class WebhookDeduplication:
    """Tracks processed events."""
    event_id: str
    processed_at: datetime
    ttl: int  # Seconds until expiry
```

### Message Templates

```python
from typing import Protocol

class MessageTemplate(Protocol):
    """Interface for message templates."""
    def render(self, **kwargs) -> SlackMessage:
        """Render template with provided data."""
        pass

class DailyPlanTemplate:
    def render(self, plan: DailyPlan, plan_id: str) -> SlackMessage:
        """Render daily plan with approval buttons."""
        # Implementation uses Block Kit structure shown above
        pass

class BlockingTaskTemplate:
    def render(self, task: JiraIssue, blocker_reason: str) -> SlackMessage:
        """Render blocking task alert."""
        pass

class ApprovalConfirmationTemplate:
    def render(self, approved: bool, plan: DailyPlan) -> SlackMessage:
        """Render approval confirmation."""
        pass

class ErrorTemplate:
    def render(self, error_type: str, message: str, suggestion: str) -> SlackMessage:
        """Render user-friendly error."""
        pass
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: OAuth Token Storage Security
*For any* OAuth authorization response, storing the workspace token should result in the token being encrypted at rest and retrievable only through authenticated requests.
**Validates: Requirements 1.2**

### Property 2: Plan Delivery Routing
*For any* generated daily plan and user configuration, the plan should be delivered to the user's configured Slack channel or DM, never to an incorrect destination.
**Validates: Requirements 2.1**

### Property 3: Complete Plan Formatting
*For any* daily plan with priority tasks and administrative tasks, the formatted Block Kit message should contain all required sections (header, priority tasks with key/summary/urgency/effort, administrative block with time estimate, and approval buttons).
**Validates: Requirements 2.2, 2.3, 2.4, 2.5**

### Property 4: Approval State Transition
*For any* plan approval action (approve/reject/modify), executing the action should update the plan state in the TrIAge API and disable the action buttons in the Slack message.
**Validates: Requirements 3.2, 3.5**

### Property 5: Rejection Feedback Collection
*For any* plan rejection, the system should create a feedback thread and capture any user replies as feedback text sent to the TrIAge API.
**Validates: Requirements 3.3, 6.1, 6.2, 6.3**

### Property 6: Slash Command Response Timing
*For any* slash command invocation, the Slack bot should respond within 3 seconds with either results or an acknowledgment message.
**Validates: Requirements 4.4**

### Property 7: Command Error Handling
*For any* slash command that fails due to API errors or invalid input, the system should display a user-friendly error message with troubleshooting guidance.
**Validates: Requirements 4.5**

### Property 8: Complete Blocking Task Notifications
*For any* blocking task detection, the notification should include task key, summary, blocker reason, urgency level, and a re-planning action button.
**Validates: Requirements 5.1, 5.2, 5.3**

### Property 9: Blocking Task Grouping
*For any* set of multiple blocking tasks detected simultaneously, they should be grouped into a single notification message rather than sent as separate messages.
**Validates: Requirements 5.4**

### Property 10: Blocking Task Resolution Notifications
*For any* blocking task that transitions to resolved state, a follow-up notification should be sent to inform the user of the resolution.
**Validates: Requirements 5.5**

### Property 11: Webhook Response Timing
*For any* incoming webhook event from Slack, the system should respond with HTTP 200 within 3 seconds, processing long-running operations asynchronously.
**Validates: Requirements 7.1, 7.2**

### Property 12: Webhook Signature Validation
*For any* incoming webhook request, if the signature is invalid, the system should reject it with HTTP 401 without processing the payload.
**Validates: Requirements 7.3**

### Property 13: Webhook Deduplication
*For any* webhook event ID, if the same event ID is received multiple times, only the first occurrence should be processed.
**Validates: Requirements 7.4**

### Property 14: Webhook Processing Error Handling
*For any* webhook event that fails during processing, the system should log detailed error information and notify the user of the failure.
**Validates: Requirements 7.5**

### Property 15: User Identification Consistency
*For any* user interaction (command, button click, message), the system should correctly identify the user by their Slack user ID and use it for all subsequent API calls.
**Validates: Requirements 8.1**

### Property 16: Multi-User Data Isolation
*For any* two different users in the same workspace, one user's plans, tasks, and configuration should never be visible to or modifiable by the other user.
**Validates: Requirements 8.2, 8.5**

### Property 17: User-Specific JIRA Account Usage
*For any* plan generation request, the system should use the requesting user's JIRA credentials, not another user's credentials.
**Validates: Requirements 8.4**

### Property 18: Effort Estimate Formatting
*For any* task with an effort estimate, the displayed format should use human-readable time units (hours or days) rather than raw numbers.
**Validates: Requirements 9.2**

### Property 19: JIRA Link Formatting
*For any* JIRA task key displayed in a message, it should be formatted as a clickable link to the corresponding JIRA issue.
**Validates: Requirements 9.3**

### Property 20: Long Description Truncation
*For any* task description exceeding 200 characters, the displayed text should be truncated with an ellipsis and provide an option to expand.
**Validates: Requirements 9.4**

### Property 21: Urgency Emoji Mapping
*For any* task with an urgency level, the displayed message should include the correct emoji indicator (🔴 for High, 🟡 for Medium, 🟢 for Low).
**Validates: Requirements 9.5**

### Property 22: Configuration Persistence
*For any* user configuration change (notification channel, delivery time, enabled status), the new settings should be stored and retrieved correctly for that user.
**Validates: Requirements 10.2**

### Property 23: Notification Disable Behavior
*For any* user with notifications disabled, slash commands should still function normally, but proactive notifications (daily plans, blocking tasks) should not be sent.
**Validates: Requirements 10.5**

### Property 24: Slack API Retry Behavior
*For any* Slack API call that fails with a retryable error, the system should retry with exponential backoff up to 3 attempts before giving up.
**Validates: Requirements 11.2**

### Property 25: Action Failure Explanation
*For any* user action that cannot be completed, the error message should explain the reason and suggest corrective actions.
**Validates: Requirements 11.3**

### Property 26: Error Logging Completeness
*For any* unexpected error during processing, detailed error information (stack trace, context, timestamp) should be logged for debugging.
**Validates: Requirements 11.5**

### Property 27: OAuth Token Encryption
*For any* stored OAuth token, reading it from storage should return the decrypted token, and inspecting the storage directly should show only encrypted data.
**Validates: Requirements 12.1**

### Property 28: HTTPS Enforcement
*For any* API call to the TrIAge backend, the request should use HTTPS protocol, never HTTP.
**Validates: Requirements 12.2**

### Property 29: Credential Redaction
*For any* JIRA credential (password, API token) handled by the system, it should never appear in log files or Slack messages.
**Validates: Requirements 12.3**

### Property 30: Webhook Signature Verification
*For any* incoming webhook request, the system should validate the signature using Slack's signing secret before processing.
**Validates: Requirements 12.4**

### Property 31: Uninstall Data Deletion
*For any* workspace that uninstalls the bot, all associated OAuth tokens and user data should be deleted from storage.
**Validates: Requirements 12.5**

## Error Handling

### Error Categories

**1. Slack API Errors**
- Rate limiting (429 responses)
- Invalid tokens (401 responses)
- Network timeouts
- Malformed requests

**Strategy:**
- Implement exponential backoff with jitter
- Maximum 3 retry attempts
- Queue messages during rate limits
- Log all API errors with context

**2. TrIAge API Errors**
- API unavailable (503)
- Authentication failures (401)
- Invalid requests (400)
- Timeout errors

**Strategy:**
- Display user-friendly error messages
- Suggest retry or configuration check
- Don't expose internal error details
- Provide support contact information

**3. Webhook Validation Errors**
- Invalid signatures
- Expired timestamps
- Malformed payloads

**Strategy:**
- Reject immediately with 401
- Log security events
- Don't process invalid requests
- Monitor for attack patterns

**4. User Input Errors**
- Invalid command syntax
- Missing configuration
- Unauthorized actions

**Strategy:**
- Provide clear error messages
- Show command help
- Guide user to correct configuration
- Validate input before API calls

### Error Message Templates

```python
ERROR_TEMPLATES = {
    "api_unavailable": {
        "text": "⚠️ TrIAge is temporarily unavailable. Please try again in a few minutes.",
        "suggestion": "If the problem persists, contact support."
    },
    "invalid_command": {
        "text": "❌ Invalid command syntax.",
        "suggestion": "Type `/triage help` to see available commands."
    },
    "not_configured": {
        "text": "⚙️ Your JIRA credentials are not configured.",
        "suggestion": "Please configure your account using `/triage config`."
    },
    "rate_limited": {
        "text": "⏱️ Too many requests. Your message will be delivered shortly.",
        "suggestion": "No action needed - we'll retry automatically."
    },
    "unauthorized": {
        "text": "🔒 You don't have permission to perform this action.",
        "suggestion": "Contact your workspace administrator."
    }
}
```

### Graceful Degradation

**Principle:** Slack integration failures should not block core TrIAge functionality.

**Implementation:**
- TrIAge API calls to Slack bot are non-blocking
- Failed notifications are logged but don't fail plan generation
- Users can always fall back to CLI
- Retry queue for failed Slack deliveries (up to 24 hours)

## Testing Strategy

### Unit Tests

Unit tests focus on specific examples, edge cases, and error conditions:

**Message Formatting:**
- Test daily plan with 0, 1, 2, 3 priority tasks
- Test plan with no administrative tasks
- Test plan with empty task descriptions
- Test truncation of long descriptions at boundary (200 chars)
- Test emoji mapping for each urgency level

**Command Handling:**
- Test each slash command with valid input
- Test commands with invalid syntax
- Test commands when user not configured
- Test help command output completeness

**OAuth Flow:**
- Test successful installation flow
- Test authorization denial
- Test token storage and retrieval
- Test token revocation

**Webhook Validation:**
- Test valid signature acceptance
- Test invalid signature rejection
- Test expired timestamp handling
- Test malformed payload handling

**Error Handling:**
- Test each error template renders correctly
- Test retry logic with mock failures
- Test rate limit queue behavior
- Test graceful degradation scenarios

### Property-Based Tests

Property tests verify universal properties across all inputs using Hypothesis:

**Configuration:** Minimum 100 iterations per property test

**Test Tags:** Each test must include a comment:
```python
# Feature: slack-integration, Property {N}: {property_text}
```

**Custom Generators:**

```python
from hypothesis import strategies as st
from hypothesis import given

# Generator for Slack user IDs
slack_user_id = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=9,
    max_size=11
).map(lambda s: f"U{s}")

# Generator for daily plans
@st.composite
def daily_plan(draw):
    num_priority = draw(st.integers(min_value=0, max_value=3))
    num_admin = draw(st.integers(min_value=0, max_value=10))
    return DailyPlan(
        priority_tasks=[draw(jira_issue()) for _ in range(num_priority)],
        admin_tasks=[draw(jira_issue()) for _ in range(num_admin)],
        date=draw(st.dates())
    )

# Generator for JIRA issues
@st.composite
def jira_issue(draw):
    return JiraIssue(
        key=f"PROJ-{draw(st.integers(min_value=1, max_value=9999))}",
        summary=draw(st.text(min_size=10, max_size=200)),
        urgency=draw(st.sampled_from(["High", "Medium", "Low"])),
        effort_days=draw(st.floats(min_value=0.1, max_value=5.0))
    )

# Generator for webhook events
@st.composite
def webhook_event(draw):
    return WebhookEvent(
        event_id=draw(st.uuids()).hex,
        event_type=draw(st.sampled_from([
            "slash_command", "block_action", "message"
        ])),
        user_id=draw(slack_user_id),
        team_id=draw(st.text(min_size=9, max_size=11).map(lambda s: f"T{s}")),
        payload=draw(st.dictionaries(st.text(), st.text())),
        timestamp=draw(st.datetimes())
    )
```

**Property Test Examples:**

```python
# Feature: slack-integration, Property 3: Complete Plan Formatting
@given(plan=daily_plan())
def test_plan_formatting_completeness(plan):
    """For any daily plan, formatted message contains all required sections."""
    formatter = MessageFormatter()
    message = formatter.format_daily_plan(plan)
    
    blocks = message.blocks
    
    # Must have header
    assert any(b["type"] == "header" for b in blocks)
    
    # Must have approval buttons
    action_block = next((b for b in blocks if b["type"] == "actions"), None)
    assert action_block is not None
    assert len(action_block["elements"]) == 3  # Approve, Reject, Modify
    
    # If priority tasks exist, must display them
    if plan.priority_tasks:
        # Check for task fields
        task_sections = [b for b in blocks if b["type"] == "section" and "fields" in b]
        assert len(task_sections) >= len(plan.priority_tasks)

# Feature: slack-integration, Property 13: Webhook Deduplication
@given(event=webhook_event())
def test_webhook_deduplication(event):
    """For any webhook event, duplicate event IDs are processed only once."""
    handler = WebhookHandler()
    
    # Process event first time
    result1 = await handler.handle_event(event)
    assert result1.processed
    
    # Process same event again
    result2 = await handler.handle_event(event)
    assert result2.duplicate
    assert not result2.processed

# Feature: slack-integration, Property 16: Multi-User Data Isolation
@given(user1=slack_user_id, user2=slack_user_id, plan=daily_plan())
def test_multi_user_isolation(user1, user2, plan):
    """For any two users, one user's data is never visible to the other."""
    assume(user1 != user2)
    
    # Store plan for user1
    store_plan(user1, plan)
    
    # Try to retrieve as user2
    user2_plans = get_plans(user2)
    
    # User2 should not see user1's plan
    assert plan not in user2_plans

# Feature: slack-integration, Property 21: Urgency Emoji Mapping
@given(task=jira_issue())
def test_urgency_emoji_mapping(task):
    """For any task, urgency level maps to correct emoji."""
    formatter = MessageFormatter()
    message = formatter.format_daily_plan(DailyPlan(
        priority_tasks=[task],
        admin_tasks=[],
        date=date.today()
    ))
    
    message_text = str(message.blocks)
    
    if task.urgency == "High":
        assert "🔴" in message_text
    elif task.urgency == "Medium":
        assert "🟡" in message_text
    elif task.urgency == "Low":
        assert "🟢" in message_text
```

### Integration Tests

Integration tests verify end-to-end workflows:

**Test Environment:**
- Mock Slack API server
- Test TrIAge API instance
- In-memory Redis for deduplication
- Test database for token storage

**Test Scenarios:**
1. Complete OAuth installation flow
2. Daily plan delivery and approval workflow
3. Slash command execution end-to-end
4. Blocking task notification and re-planning
5. Multi-user workspace with concurrent interactions
6. Error recovery and retry scenarios
7. Webhook signature validation
8. Token expiration and re-authorization

**Example Integration Test:**

```python
async def test_complete_approval_workflow():
    """Test full plan delivery and approval flow."""
    # Setup
    user_id = "U12345"
    team_id = "T12345"
    
    # Generate and deliver plan
    plan = generate_test_plan()
    response = await slack_bot.deliver_plan(user_id, team_id, plan)
    assert response.ok
    
    # Simulate user clicking approve button
    approval_event = create_approval_event(user_id, plan.id)
    webhook_response = await slack_bot.handle_webhook(approval_event)
    assert webhook_response.status_code == 200
    
    # Verify plan marked as approved in API
    plan_status = await triage_api.get_plan_status(plan.id)
    assert plan_status.approved
    
    # Verify message updated in Slack
    message = await slack_api.get_message(response.message_ts)
    assert "✅ Approved" in message.text
    assert all(button["disabled"] for button in message.action_buttons)
```

### Test Coverage Goals

- Unit test coverage: > 90% of code
- Property test coverage: All 31 properties implemented
- Integration test coverage: All critical user workflows
- Error path coverage: All error templates and retry logic



## Deployment Architecture

### Service Deployment

**Slack Bot Service:**
- Containerized Python application
- Deployed as serverless function (AWS Lambda, GCP Cloud Run) or container service
- Horizontal scaling based on webhook volume
- Stateless design for easy scaling

**Infrastructure Requirements:**
- HTTPS endpoint for webhook reception
- Secret storage for OAuth tokens and signing secrets
- Redis or equivalent for webhook deduplication cache
- Database for user configuration and token storage

### Configuration Management

**Environment Variables:**
```bash
# Slack Configuration
SLACK_CLIENT_ID=<slack_app_client_id>
SLACK_CLIENT_SECRET=<slack_app_client_secret>
SLACK_SIGNING_SECRET=<webhook_signing_secret>
SLACK_OAUTH_REDIRECT_URL=https://triage.example.com/slack/oauth/callback

# TrIAge API Configuration
TRIAGE_API_URL=https://api.triage.example.com
TRIAGE_API_KEY=<api_authentication_key>

# Storage Configuration
DATABASE_URL=postgresql://user:pass@host:5432/triage
REDIS_URL=redis://host:6379/0

# Encryption
TOKEN_ENCRYPTION_KEY=<32_byte_key_for_token_encryption>

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=<optional_error_tracking>
```

### Security Considerations

**Token Storage:**
- OAuth tokens encrypted using AES-256
- Encryption key stored in secure secret manager (AWS Secrets Manager, GCP Secret Manager)
- Tokens never logged or exposed in error messages

**Webhook Security:**
- All webhooks validated using Slack signing secret
- Timestamp validation to prevent replay attacks (5-minute window)
- HTTPS required for all endpoints

**API Communication:**
- TrIAge API calls use bearer token authentication
- All communication over HTTPS
- API keys rotated regularly

**User Data:**
- JIRA credentials never stored in Slack bot
- User data isolated by workspace and user ID
- Data deleted on workspace uninstall

## Monitoring and Observability

### Metrics

**Key Performance Indicators:**
- Webhook response time (p50, p95, p99)
- Slack API call success rate
- TrIAge API call success rate
- Message delivery success rate
- Command execution time
- Deduplication cache hit rate

**Business Metrics:**
- Daily active users
- Plans delivered per day
- Approval rate
- Command usage by type
- Error rate by category

### Logging

**Structured Logging Format:**
```json
{
  "timestamp": "2026-01-15T09:00:00Z",
  "level": "INFO",
  "event": "plan_delivered",
  "user_id": "U12345",
  "team_id": "T12345",
  "plan_id": "plan_abc123",
  "duration_ms": 245,
  "success": true
}
```

**Log Levels:**
- DEBUG: Detailed flow information
- INFO: Normal operations (plan delivered, command executed)
- WARNING: Retryable errors, rate limits
- ERROR: Failed operations, invalid requests
- CRITICAL: System failures, security events

### Alerting

**Alert Conditions:**
- Webhook response time > 2 seconds (p95)
- Error rate > 5% over 5 minutes
- Slack API failure rate > 10%
- TrIAge API unavailable
- Token decryption failures
- Invalid webhook signatures (potential attack)

## Migration and Rollout

### Phase 1: MVP (Weeks 1-2)
- OAuth installation flow
- Daily plan delivery
- Basic approval workflow (approve/reject)
- Slash commands: plan, status, help
- Error handling and logging

### Phase 2: Enhanced Features (Weeks 3-4)
- Blocking task notifications
- Conversational feedback collection
- Configuration management
- Multi-user support refinements
- Retry and queue mechanisms

### Phase 3: Production Hardening (Week 5)
- Comprehensive error handling
- Security audit and penetration testing
- Performance optimization
- Monitoring and alerting setup
- Documentation and runbooks

### Rollout Strategy

**Beta Testing:**
- Internal team testing (1 week)
- Selected external users (1 week)
- Gather feedback and iterate

**Production Release:**
- Gradual rollout to workspaces
- Monitor error rates and performance
- Quick rollback capability if issues arise

**User Communication:**
- Installation guide and documentation
- Video tutorials for common workflows
- Support channel for questions
- Release notes for updates

## Future Enhancements

### Post-MVP Features

**1. Rich Interactions:**
- Modal dialogs for plan modification
- Interactive task selection
- Inline task creation

**2. Advanced Notifications:**
- Customizable notification rules
- Digest mode (batch notifications)
- Smart notification timing (respect focus time)

**3. Team Features:**
- Shared team channels for plan visibility
- Manager view of team plans
- Team capacity planning

**4. Analytics:**
- Personal productivity insights
- Task completion trends
- Time allocation analysis

**5. Integrations:**
- Calendar integration for time blocking
- GitHub integration for PR tracking
- Email integration for task creation

## Appendix

### Slack API Endpoints Used

**OAuth:**
- `POST /oauth.v2.access` - Exchange code for token
- `POST /oauth.v2.revoke` - Revoke token

**Messaging:**
- `POST /chat.postMessage` - Send message
- `POST /chat.update` - Update message
- `POST /chat.postEphemeral` - Send ephemeral message

**Users:**
- `GET /users.info` - Get user information
- `GET /users.list` - List workspace users

**Conversations:**
- `GET /conversations.list` - List channels
- `GET /conversations.info` - Get channel information

### Block Kit Reference

**Block Types Used:**
- `header` - Section headers
- `section` - Text and fields
- `divider` - Visual separator
- `actions` - Interactive buttons
- `context` - Metadata and timestamps

**Element Types Used:**
- `button` - Action buttons
- `static_select` - Dropdown menus
- `plain_text_input` - Text input fields

### Error Codes

**Slack API Errors:**
- `invalid_auth` - Token invalid or expired
- `not_authed` - No authentication provided
- `account_inactive` - Workspace deactivated
- `token_revoked` - Token explicitly revoked
- `rate_limited` - Too many requests

**TrIAge API Errors:**
- `401` - Authentication failed
- `403` - Insufficient permissions
- `404` - Resource not found
- `429` - Rate limit exceeded
- `503` - Service unavailable

### Glossary

- **Block Kit**: Slack's UI framework for rich messages
- **Ephemeral Message**: Message visible only to specific user
- **Slash Command**: Command starting with "/" in Slack
- **Thread**: Conversation context within a message
- **Workspace**: Slack organization instance
- **OAuth Scope**: Permission granted to bot
- **Signing Secret**: Key for webhook signature validation
- **Response URL**: Webhook URL for delayed responses
