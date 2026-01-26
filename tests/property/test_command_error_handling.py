# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for slash command error handling.

Feature: slack-integration, Property 7: Command Error Handling
Validates: Requirements 4.5

For any slash command that fails due to API errors or invalid input, the system
should display a user-friendly error message with troubleshooting guidance.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
import httpx
from hypothesis import given, strategies as st, settings, assume

from slack_bot.command_handler import CommandHandler
from slack_bot.models import SlashCommand
from slack_bot.message_formatter import MessageFormatter


# Custom strategies for generating test data

@st.composite
def slack_user_id(draw):
    """Generate valid Slack user ID."""
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=8,
        max_size=11
    ))
    return f"U{suffix}"


@st.composite
def slack_team_id(draw):
    """Generate valid Slack team ID."""
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=8,
        max_size=11
    ))
    return f"T{suffix}"


@st.composite
def slack_channel_id(draw):
    """Generate valid Slack channel ID."""
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=8,
        max_size=11
    ))
    return f"C{suffix}"


@st.composite
def slash_command(draw):
    """Generate valid SlashCommand."""
    subcommands = st.sampled_from(["plan", "status", "config"])
    
    return SlashCommand(
        command="/triage",
        text=draw(subcommands),
        user_id=draw(slack_user_id()),
        team_id=draw(slack_team_id()),
        channel_id=draw(slack_channel_id()),
        response_url=f"https://hooks.slack.com/commands/{draw(st.text(min_size=20, max_size=40))}"
    )


# Feature: slack-integration, Property 7: Command Error Handling
@settings(max_examples=100, deadline=5000)
@given(
    cmd=slash_command(),
    error_status=st.sampled_from([400, 401, 403, 404, 500, 503])
)
@pytest.mark.asyncio
async def test_command_error_handling_api_errors(cmd, error_status):
    """
    Property 7: Command Error Handling (API Errors)
    
    For any slash command that fails due to API errors, the system should
    display a user-friendly error message with troubleshooting guidance.
    
    Validates: Requirements 4.5
    """
    # Setup mock HTTP client that returns error status
    mock_response = MagicMock()
    mock_response.status_code = error_status
    mock_response.json.return_value = {"error": "API error"}
    
    # Create handler
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client
    handler.http_client = AsyncMock()
    handler.http_client.post = AsyncMock(return_value=mock_response)
    handler.http_client.get = AsyncMock(return_value=mock_response)
    
    try:
        response = await handler.handle_command(cmd)
        
        # Property: Response must be a valid SlackMessage
        assert response is not None
        assert hasattr(response, 'blocks')
        assert hasattr(response, 'text')
        
        # Property: Error message must be user-friendly (not expose internal details)
        assert response.text is not None
        assert len(response.text) > 0
        
        # Property: Should not contain technical error details
        response_text = response.text.lower()
        assert "exception" not in response_text
        assert "traceback" not in response_text
        assert "stack" not in response_text
        
        # Property: Should contain helpful guidance
        # Check that blocks contain some form of guidance or suggestion
        blocks_text = str(response.blocks).lower()
        
        # For 404 on status command, it's a valid "no plan" response, not an error
        # For other cases, should have guidance
        if error_status == 404 and "status" in cmd.text.lower():
            # This is actually a valid response (no active plan)
            assert "no active plan" in blocks_text or "don't have" in blocks_text
        else:
            # Other errors should have guidance
            has_guidance = any(word in blocks_text for word in [
                "try", "contact", "please", "check", "verify", "again", "moment"
            ])
            assert has_guidance, f"Error message should contain troubleshooting guidance for status {error_status}"
        
    finally:
        await handler.close()


# Feature: slack-integration, Property 7: Command Error Handling (Invalid Input)
@settings(max_examples=100, deadline=5000)
@given(
    user_id=slack_user_id(),
    team_id=slack_team_id(),
    channel_id=slack_channel_id(),
    invalid_date=st.text(
        alphabet=st.characters(blacklist_characters="-0123456789"),
        min_size=1,
        max_size=20
    )
)
@pytest.mark.asyncio
async def test_command_error_handling_invalid_input(user_id, team_id, channel_id, invalid_date):
    """
    Property 7: Command Error Handling (Invalid Input)
    
    For any slash command with invalid input, the system should display
    a user-friendly error message explaining the issue.
    
    Validates: Requirements 4.5
    """
    # Skip if the invalid date happens to be a valid keyword
    assume(invalid_date.lower() not in ["today", "tomorrow"])
    
    cmd = SlashCommand(
        command="/triage",
        text=f"plan {invalid_date}",
        user_id=user_id,
        team_id=team_id,
        channel_id=channel_id,
        response_url="https://hooks.slack.com/test"
    )
    
    # Create handler
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client (shouldn't be called for invalid input)
    handler.http_client = AsyncMock()
    
    try:
        response = await handler.handle_command(cmd)
        
        # Property: Response must be valid
        assert response is not None
        assert hasattr(response, 'text')
        assert len(response.text) > 0
        
        # Property: Error message should mention the invalid input
        response_text = str(response.blocks).lower()
        assert "invalid" in response_text or "format" in response_text
        
        # Property: Should provide guidance on correct format
        assert "yyyy-mm-dd" in response_text or "today" in response_text or "tomorrow" in response_text
        
    finally:
        await handler.close()


# Feature: slack-integration, Property 7: Command Error Handling (Network Errors)
@settings(max_examples=50, deadline=5000)
@given(cmd=slash_command())
@pytest.mark.asyncio
async def test_command_error_handling_network_errors(cmd):
    """
    Property 7: Command Error Handling (Network Errors)
    
    For any slash command that fails due to network errors, the system
    should display a user-friendly error message.
    
    Validates: Requirements 4.5
    """
    # Create handler
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client to raise network error
    handler.http_client = AsyncMock()
    handler.http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
    handler.http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
    
    try:
        response = await handler.handle_command(cmd)
        
        # Property: Response must be valid even on network error
        assert response is not None
        assert hasattr(response, 'text')
        assert len(response.text) > 0
        
        # Property: Error message should be user-friendly
        response_text = str(response.blocks).lower()
        assert "unavailable" in response_text or "connect" in response_text or "try again" in response_text
        
        # Property: Should not expose technical details
        assert "connecterror" not in response_text
        assert "exception" not in response_text
        
    finally:
        await handler.close()


# Feature: slack-integration, Property 7: Command Error Handling (Unknown Commands)
@settings(max_examples=100, deadline=5000)
@given(
    user_id=slack_user_id(),
    team_id=slack_team_id(),
    channel_id=slack_channel_id(),
    unknown_command=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
        min_size=1,
        max_size=20
    )
)
@pytest.mark.asyncio
async def test_command_error_handling_unknown_commands(user_id, team_id, channel_id, unknown_command):
    """
    Property 7: Command Error Handling (Unknown Commands)
    
    For any unknown subcommand, the system should display a helpful
    error message directing users to help.
    
    Validates: Requirements 4.5
    """
    # Skip known commands
    assume(unknown_command.lower() not in ["plan", "status", "help", "config", ""])
    
    cmd = SlashCommand(
        command="/triage",
        text=unknown_command,
        user_id=user_id,
        team_id=team_id,
        channel_id=channel_id,
        response_url="https://hooks.slack.com/test"
    )
    
    # Create handler
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client (shouldn't be called for unknown commands)
    handler.http_client = AsyncMock()
    
    try:
        response = await handler.handle_command(cmd)
        
        # Property: Response must be valid
        assert response is not None
        assert len(response.text) > 0
        
        # Property: Should indicate unknown command
        response_text = str(response.blocks).lower()
        assert "unknown" in response_text or "invalid" in response_text
        
        # Property: Should direct user to help
        assert "help" in response_text
        assert "/triage help" in response_text or "`/triage help`" in response_text
        
    finally:
        await handler.close()


# Feature: slack-integration, Property 7: Command Error Handling (Timeout)
@settings(max_examples=50, deadline=10000)
@given(cmd=slash_command())
@pytest.mark.asyncio
async def test_command_error_handling_timeout(cmd):
    """
    Property 7: Command Error Handling (Timeout)
    
    For any slash command that times out, the system should display
    a user-friendly error message.
    
    Validates: Requirements 4.5
    """
    # Create handler
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client to raise timeout
    handler.http_client = AsyncMock()
    handler.http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
    handler.http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
    
    try:
        response = await handler.handle_command(cmd)
        
        # Property: Response must be valid even on timeout
        assert response is not None
        assert len(response.text) > 0
        
        # Property: Error message should mention timeout or busy service
        response_text = str(response.blocks).lower()
        assert any(word in response_text for word in ["timeout", "timed out", "busy", "try again"])
        
        # Property: Should not expose technical details
        assert "timeoutexception" not in response_text
        
    finally:
        await handler.close()
