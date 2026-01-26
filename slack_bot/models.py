# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Slack-specific data models for TrIAge Slack integration.

This module defines Pydantic models for Slack events, messages, user data,
and configuration. All models use Pydantic v2 for validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SlackUser(BaseModel):
    """
    Maps a Slack user to a TrIAge user.
    
    This model maintains the relationship between Slack workspace users
    and their corresponding TrIAge accounts, including JIRA credentials.
    
    Validates: Requirements 8.1
    """
    model_config = ConfigDict(frozen=False)
    
    slack_user_id: str = Field(
        ...,
        description="Slack user ID (e.g., 'U12345')",
        pattern=r"^U[A-Z0-9]{8,11}$"
    )
    slack_team_id: str = Field(
        ...,
        description="Slack workspace/team ID (e.g., 'T12345')",
        pattern=r"^T[A-Z0-9]{8,11}$"
    )
    triage_user_id: str = Field(
        ...,
        description="TrIAge internal user ID"
    )
    jira_email: str = Field(
        ...,
        description="User's JIRA account email"
    )
    display_name: str = Field(
        ...,
        description="User's display name in Slack"
    )
    
    @field_validator('jira_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v


class SlackConfig(BaseModel):
    """
    User-specific Slack configuration and preferences.
    
    Stores notification preferences, delivery settings, and channel
    configuration for each user.
    
    Validates: Requirements 10.2
    """
    model_config = ConfigDict(frozen=False)
    
    user_id: str = Field(
        ...,
        description="TrIAge user ID"
    )
    notification_channel: str = Field(
        ...,
        description="Channel ID (e.g., 'C12345') or 'DM' for direct message"
    )
    delivery_time: str = Field(
        default="09:00",
        description="Daily plan delivery time in HH:MM format",
        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$"
    )
    notifications_enabled: bool = Field(
        default=True,
        description="Whether proactive notifications are enabled"
    )
    timezone: str = Field(
        default="UTC",
        description="User's timezone for delivery scheduling"
    )
    
    @field_validator('notification_channel')
    @classmethod
    def validate_channel(cls, v: str) -> str:
        """Validate channel format."""
        if v != "DM" and not v.startswith('C'):
            raise ValueError('Channel must be "DM" or start with "C"')
        return v


class WebhookEvent(BaseModel):
    """
    Represents an incoming webhook event from Slack.
    
    This model captures all essential information from Slack webhook
    events including commands, interactions, and messages.
    
    Validates: Requirements 7.1, 7.2, 7.3
    """
    model_config = ConfigDict(frozen=False)
    
    event_id: str = Field(
        ...,
        description="Unique event identifier for deduplication"
    )
    event_type: str = Field(
        ...,
        description="Type of event (slash_command, block_action, message, etc.)"
    )
    user_id: str = Field(
        ...,
        description="Slack user ID who triggered the event",
        pattern=r"^U[A-Z0-9]{8,11}$"
    )
    team_id: str = Field(
        ...,
        description="Slack workspace/team ID",
        pattern=r"^T[A-Z0-9]{8,11}$"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw event payload from Slack"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp"
    )
    
    @field_validator('event_type')
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event type is recognized."""
        valid_types = {
            'slash_command',
            'block_action',
            'message',
            'app_mention',
            'view_submission',
            'view_closed'
        }
        if v not in valid_types:
            raise ValueError(f'Unknown event type: {v}')
        return v


class SlackMessage(BaseModel):
    """
    Represents a Slack message to be sent.
    
    This model encapsulates Block Kit blocks, fallback text, and
    threading information for Slack messages.
    
    Validates: Requirements 2.2, 9.1
    """
    model_config = ConfigDict(frozen=False)
    
    blocks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Block Kit blocks for rich message formatting"
    )
    text: str = Field(
        ...,
        description="Fallback text for notifications and accessibility"
    )
    thread_ts: Optional[str] = Field(
        default=None,
        description="Thread timestamp for threaded replies"
    )
    channel: Optional[str] = Field(
        default=None,
        description="Target channel ID or user ID for DM"
    )
    
    @field_validator('text')
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Ensure fallback text is not empty."""
        if not v or not v.strip():
            raise ValueError('Fallback text cannot be empty')
        return v
    
    @field_validator('blocks')
    @classmethod
    def validate_blocks_structure(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate basic block structure."""
        for block in v:
            if 'type' not in block:
                raise ValueError('Each block must have a "type" field')
        return v


class PendingFeedback(BaseModel):
    """
    Tracks feedback collection state for rejected plans.
    
    Manages the conversational feedback collection process when
    users reject a plan.
    
    Validates: Requirements 6.1, 6.2, 6.3
    """
    model_config = ConfigDict(frozen=False)
    
    feedback_id: str = Field(
        ...,
        description="Unique identifier for this feedback session"
    )
    user_id: str = Field(
        ...,
        description="Slack user ID providing feedback"
    )
    plan_id: str = Field(
        ...,
        description="ID of the rejected plan"
    )
    thread_ts: str = Field(
        ...,
        description="Thread timestamp for feedback collection"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When feedback collection started"
    )
    expires_at: datetime = Field(
        ...,
        description="When feedback collection expires (30 minutes)"
    )
    reminder_sent: bool = Field(
        default=False,
        description="Whether 5-minute reminder has been sent"
    )


class WebhookDeduplication(BaseModel):
    """
    Tracks processed webhook events for deduplication.
    
    Prevents duplicate processing of webhook events using Redis
    or in-memory cache with TTL.
    
    Validates: Requirements 7.4
    """
    model_config = ConfigDict(frozen=False)
    
    event_id: str = Field(
        ...,
        description="Unique event identifier"
    )
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When event was processed"
    )
    ttl: int = Field(
        default=300,
        description="Time-to-live in seconds (default 5 minutes)",
        ge=60,
        le=3600
    )


class WorkspaceToken(BaseModel):
    """
    OAuth token for a Slack workspace.
    
    Stores encrypted OAuth tokens and workspace metadata for
    authenticated API calls.
    
    Validates: Requirements 1.2, 12.1
    """
    model_config = ConfigDict(frozen=False)
    
    team_id: str = Field(
        ...,
        description="Slack workspace/team ID",
        pattern=r"^T[A-Z0-9]{8,11}$"
    )
    access_token: str = Field(
        ...,
        description="Encrypted OAuth access token"
    )
    bot_user_id: str = Field(
        ...,
        description="Bot user ID in the workspace",
        pattern=r"^U[A-Z0-9]{8,11}$"
    )
    scope: str = Field(
        ...,
        description="Granted OAuth scopes"
    )
    installed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When workspace installed the bot"
    )


class SlashCommand(BaseModel):
    """
    Represents a slash command invocation.
    
    Captures all information from a slash command event for
    routing and processing.
    
    Validates: Requirements 4.1, 4.2, 4.3
    """
    model_config = ConfigDict(frozen=False)
    
    command: str = Field(
        ...,
        description="Command name (e.g., '/triage')"
    )
    text: str = Field(
        default="",
        description="Command arguments (e.g., 'plan', 'status')"
    )
    user_id: str = Field(
        ...,
        description="Slack user ID who invoked command",
        pattern=r"^U[A-Z0-9]{8,11}$"
    )
    team_id: str = Field(
        ...,
        description="Slack workspace/team ID",
        pattern=r"^T[A-Z0-9]{8,11}$"
    )
    channel_id: str = Field(
        ...,
        description="Channel where command was invoked"
    )
    response_url: str = Field(
        ...,
        description="Webhook URL for delayed responses"
    )
    
    @field_validator('command')
    @classmethod
    def validate_command_format(cls, v: str) -> str:
        """Ensure command starts with /."""
        if not v.startswith('/'):
            raise ValueError('Command must start with /')
        return v


class BlockAction(BaseModel):
    """
    Represents a button click or interactive element action.
    
    Captures information from Block Kit interactive elements
    like buttons and select menus.
    
    Validates: Requirements 3.2, 3.3, 3.4, 3.5
    """
    model_config = ConfigDict(frozen=False)
    
    action_id: str = Field(
        ...,
        description="Action identifier (e.g., 'approve_plan')"
    )
    value: str = Field(
        ...,
        description="Action value (e.g., plan ID)"
    )
    user_id: str = Field(
        ...,
        description="Slack user ID who clicked",
        pattern=r"^U[A-Z0-9]{8,11}$"
    )
    team_id: str = Field(
        ...,
        description="Slack workspace/team ID",
        pattern=r"^T[A-Z0-9]{8,11}$"
    )
    message_ts: str = Field(
        ...,
        description="Timestamp of message containing the action"
    )
    response_url: str = Field(
        ...,
        description="Webhook URL for updating the message"
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Channel ID where action occurred"
    )


class ErrorContext(BaseModel):
    """
    Context information for error handling and logging.
    
    Captures detailed error information for debugging and
    user-friendly error messages.
    
    Validates: Requirements 11.3, 11.5
    """
    model_config = ConfigDict(frozen=False)
    
    error_type: str = Field(
        ...,
        description="Type of error (api_unavailable, invalid_command, etc.)"
    )
    message: str = Field(
        ...,
        description="Error message"
    )
    suggestion: str = Field(
        ...,
        description="User-friendly suggestion for resolution"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID if error is user-specific"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for debugging"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When error occurred"
    )
