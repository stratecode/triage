# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for InteractionHandler.

Tests button interactions including approve, reject, and modify actions.

Validates: Requirements 3.2, 3.3, 3.4, 3.5
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from slack_bot.models import BlockAction
from slack_bot.interaction_handler import InteractionHandler
from slack_bot.message_formatter import MessageFormatter


@pytest.fixture
def message_formatter():
    """Create MessageFormatter instance."""
    return MessageFormatter(jira_base_url="https://jira.example.com")


@pytest.fixture
def interaction_handler(message_formatter):
    """Create InteractionHandler instance with mocked clients."""
    handler = InteractionHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=message_formatter
    )
    
    # Mock HTTP clients
    handler.triage_client = AsyncMock()
    handler.slack_client = AsyncMock()
    
    return handler


@pytest.fixture
def approve_action():
    """Create sample approve action."""
    return BlockAction(
        action_id="approve_plan",
        value="plan_abc123",
        user_id="U12345ABC",
        team_id="T12345ABC",
        message_ts="1234567890.123456",
        response_url="https://hooks.slack.com/actions/T12345/B12345/abc123",
        channel_id="C12345ABC"
    )


@pytest.fixture
def reject_action():
    """Create sample reject action."""
    return BlockAction(
        action_id="reject_plan",
        value="plan_abc123",
        user_id="U12345ABC",
        team_id="T12345ABC",
        message_ts="1234567890.123456",
        response_url="https://hooks.slack.com/actions/T12345/B12345/abc123",
        channel_id="C12345ABC"
    )


@pytest.fixture
def modify_action():
    """Create sample modify action."""
    return BlockAction(
        action_id="modify_plan",
        value="plan_abc123",
        user_id="U12345ABC",
        team_id="T12345ABC",
        message_ts="1234567890.123456",
        response_url="https://hooks.slack.com/actions/T12345/B12345/abc123",
        channel_id="C12345ABC"
    )


# Test approve button handler

@pytest.mark.asyncio
async def test_approve_updates_message_correctly(interaction_handler, approve_action):
    """
    Test that approve button updates message to show approval status.
    
    Validates: Requirements 3.2, 3.5
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "approved"}
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock successful Slack update
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": approve_action.message_ts}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute approve
    await interaction_handler.handle_approve(approve_action)
    
    # Verify TrIAge API was called
    interaction_handler.triage_client.post.assert_called_once()
    call_args = interaction_handler.triage_client.post.call_args
    assert f"/api/v1/plans/{approve_action.value}/approve" in str(call_args)
    
    # Verify Slack message was updated
    interaction_handler.slack_client.post.assert_called_once()
    slack_call = interaction_handler.slack_client.post.call_args
    assert "/chat.update" in str(slack_call)
    
    # Verify update payload
    update_payload = slack_call[1]["json"]
    assert update_payload["channel"] == approve_action.channel_id
    assert update_payload["ts"] == approve_action.message_ts
    assert "Approved" in update_payload["text"]
    
    # Verify blocks contain approval indicator
    blocks = update_payload["blocks"]
    assert any("✅" in str(block) or "Approved" in str(block) for block in blocks)


@pytest.mark.asyncio
async def test_approve_handles_plan_not_found(interaction_handler, approve_action):
    """
    Test that approve button handles 404 plan not found gracefully.
    
    Validates: Requirements 3.2
    """
    # Mock 404 response
    mock_response = MagicMock()
    mock_response.status_code = 404
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock Slack ephemeral message
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute approve
    await interaction_handler.handle_approve(approve_action)
    
    # Verify ephemeral error message was sent
    interaction_handler.slack_client.post.assert_called_once()
    slack_call = interaction_handler.slack_client.post.call_args
    assert "/chat.postEphemeral" in str(slack_call)
    
    # Verify error message content
    ephemeral_payload = slack_call[1]["json"]
    assert ephemeral_payload["user"] == approve_action.user_id
    error_text = str(ephemeral_payload.get("blocks", [])) + ephemeral_payload.get("text", "")
    assert "not found" in error_text.lower()


@pytest.mark.asyncio
async def test_approve_handles_already_processed(interaction_handler, approve_action):
    """
    Test that approve button handles 409 already processed gracefully.
    
    Validates: Requirements 3.2, 3.5
    """
    # Mock 409 response
    mock_response = MagicMock()
    mock_response.status_code = 409
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock Slack ephemeral message
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute approve
    await interaction_handler.handle_approve(approve_action)
    
    # Verify ephemeral error message was sent
    interaction_handler.slack_client.post.assert_called_once()
    slack_call = interaction_handler.slack_client.post.call_args
    assert "/chat.postEphemeral" in str(slack_call)
    
    # Verify error message content
    ephemeral_payload = slack_call[1]["json"]
    error_text = str(ephemeral_payload.get("blocks", [])) + ephemeral_payload.get("text", "")
    assert any(keyword in error_text.lower() for keyword in ["already", "processed"])


# Test reject button handler

@pytest.mark.asyncio
async def test_reject_creates_thread(interaction_handler, reject_action):
    """
    Test that reject button creates feedback collection thread.
    
    Validates: Requirements 3.3, 6.1
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "rejected"}
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock successful Slack responses
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": reject_action.message_ts}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute reject
    await interaction_handler.handle_reject(reject_action)
    
    # Verify TrIAge API was called
    assert interaction_handler.triage_client.post.call_count >= 1
    
    # Verify Slack API was called multiple times (update + thread message)
    assert interaction_handler.slack_client.post.call_count >= 2
    
    # Find the feedback thread message
    feedback_calls = [
        call for call in interaction_handler.slack_client.post.call_args_list
        if "/chat.postMessage" in str(call)
    ]
    assert len(feedback_calls) >= 1
    
    # Verify thread message
    feedback_payload = feedback_calls[0][1]["json"]
    assert feedback_payload["channel"] == reject_action.channel_id
    assert feedback_payload["thread_ts"] == reject_action.message_ts
    
    # Verify feedback prompt
    feedback_text = str(feedback_payload.get("blocks", [])) + feedback_payload.get("text", "")
    assert any(keyword in feedback_text.lower() for keyword in ["feedback", "why", "reason"])


@pytest.mark.asyncio
async def test_reject_updates_message_status(interaction_handler, reject_action):
    """
    Test that reject button updates message to show rejection status.
    
    Validates: Requirements 3.3, 3.5
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "rejected"}
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock successful Slack responses
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": reject_action.message_ts}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute reject
    await interaction_handler.handle_reject(reject_action)
    
    # Find the update call
    update_calls = [
        call for call in interaction_handler.slack_client.post.call_args_list
        if "/chat.update" in str(call)
    ]
    assert len(update_calls) >= 1
    
    # Verify update payload
    update_payload = update_calls[0][1]["json"]
    assert update_payload["channel"] == reject_action.channel_id
    assert update_payload["ts"] == reject_action.message_ts
    assert "Rejected" in update_payload["text"]
    
    # Verify blocks contain rejection indicator
    blocks = update_payload["blocks"]
    assert any("❌" in str(block) or "Rejected" in str(block) for block in blocks)


# Test modify button handler

@pytest.mark.asyncio
async def test_modify_provides_instructions(interaction_handler, modify_action):
    """
    Test that modify button provides modification instructions.
    
    Validates: Requirements 3.4
    """
    # Mock Slack ephemeral message
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute modify
    await interaction_handler.handle_modify(modify_action)
    
    # Verify ephemeral message was sent
    interaction_handler.slack_client.post.assert_called_once()
    slack_call = interaction_handler.slack_client.post.call_args
    assert "/chat.postEphemeral" in str(slack_call)
    
    # Verify message content
    ephemeral_payload = slack_call[1]["json"]
    assert ephemeral_payload["user"] == modify_action.user_id
    assert ephemeral_payload["channel"] == modify_action.channel_id
    
    # Verify instructions are provided
    message_text = str(ephemeral_payload.get("blocks", [])) + ephemeral_payload.get("text", "")
    assert any(keyword in message_text.lower() for keyword in ["modify", "change", "update", "jira"])


@pytest.mark.asyncio
async def test_modify_mentions_rejection_option(interaction_handler, modify_action):
    """
    Test that modify instructions mention rejection as an option.
    
    Validates: Requirements 3.4
    """
    # Mock Slack ephemeral message
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute modify
    await interaction_handler.handle_modify(modify_action)
    
    # Verify message mentions rejection
    slack_call = interaction_handler.slack_client.post.call_args
    ephemeral_payload = slack_call[1]["json"]
    message_text = str(ephemeral_payload.get("blocks", [])) + ephemeral_payload.get("text", "")
    assert "reject" in message_text.lower()


# Test button disabled after action

@pytest.mark.asyncio
async def test_buttons_disabled_after_approval(interaction_handler, approve_action):
    """
    Test that action buttons are disabled after approval.
    
    Validates: Requirements 3.5
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "approved"}
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock successful Slack update
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": approve_action.message_ts}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute approve
    await interaction_handler.handle_approve(approve_action)
    
    # Verify message was updated
    slack_call = interaction_handler.slack_client.post.call_args
    update_payload = slack_call[1]["json"]
    
    # Verify blocks don't contain action buttons anymore
    # (they're replaced with status message)
    blocks = update_payload["blocks"]
    has_action_block = any(block.get("type") == "actions" for block in blocks)
    assert not has_action_block, "Action buttons should be removed after approval"


@pytest.mark.asyncio
async def test_buttons_disabled_after_rejection(interaction_handler, reject_action):
    """
    Test that action buttons are disabled after rejection.
    
    Validates: Requirements 3.5
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "rejected"}
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock successful Slack responses
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": reject_action.message_ts}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute reject
    await interaction_handler.handle_reject(reject_action)
    
    # Find the update call
    update_calls = [
        call for call in interaction_handler.slack_client.post.call_args_list
        if "/chat.update" in str(call)
    ]
    assert len(update_calls) >= 1
    
    # Verify blocks don't contain action buttons anymore
    update_payload = update_calls[0][1]["json"]
    blocks = update_payload["blocks"]
    has_action_block = any(block.get("type") == "actions" for block in blocks)
    assert not has_action_block, "Action buttons should be removed after rejection"


# Test error handling

@pytest.mark.asyncio
async def test_approve_handles_api_error(interaction_handler, approve_action):
    """
    Test that approve button handles API errors gracefully.
    
    Validates: Requirements 3.2
    """
    # Mock API error
    mock_response = MagicMock()
    mock_response.status_code = 500
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock Slack ephemeral message
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute approve (should not raise exception)
    await interaction_handler.handle_approve(approve_action)
    
    # Verify error message was sent
    interaction_handler.slack_client.post.assert_called_once()
    slack_call = interaction_handler.slack_client.post.call_args
    assert "/chat.postEphemeral" in str(slack_call)


@pytest.mark.asyncio
async def test_reject_handles_api_error(interaction_handler, reject_action):
    """
    Test that reject button handles API errors gracefully.
    
    Validates: Requirements 3.3
    """
    # Mock API error
    mock_response = MagicMock()
    mock_response.status_code = 500
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock Slack ephemeral message
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute reject (should not raise exception)
    await interaction_handler.handle_reject(reject_action)
    
    # Verify error message was sent
    assert interaction_handler.slack_client.post.call_count >= 1
    ephemeral_calls = [
        call for call in interaction_handler.slack_client.post.call_args_list
        if "/chat.postEphemeral" in str(call)
    ]
    assert len(ephemeral_calls) >= 1


# Test action routing

@pytest.mark.asyncio
async def test_handle_action_routes_approve(interaction_handler, approve_action):
    """
    Test that handle_action routes approve actions correctly.
    
    Validates: Requirements 3.2
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock Slack response
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute action
    await interaction_handler.handle_action(approve_action)
    
    # Verify TrIAge API was called with approve endpoint
    interaction_handler.triage_client.post.assert_called_once()
    call_args = interaction_handler.triage_client.post.call_args
    assert "/approve" in str(call_args)


@pytest.mark.asyncio
async def test_handle_action_routes_reject(interaction_handler, reject_action):
    """
    Test that handle_action routes reject actions correctly.
    
    Validates: Requirements 3.3
    """
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    interaction_handler.triage_client.post = AsyncMock(return_value=mock_response)
    
    # Mock Slack response
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute action
    await interaction_handler.handle_action(reject_action)
    
    # Verify TrIAge API was called with reject endpoint
    assert interaction_handler.triage_client.post.call_count >= 1
    first_call = interaction_handler.triage_client.post.call_args_list[0]
    assert "/reject" in str(first_call)


@pytest.mark.asyncio
async def test_handle_action_routes_modify(interaction_handler, modify_action):
    """
    Test that handle_action routes modify actions correctly.
    
    Validates: Requirements 3.4
    """
    # Mock Slack response
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    interaction_handler.slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Execute action
    await interaction_handler.handle_action(modify_action)
    
    # Verify ephemeral message was sent (modify doesn't call TrIAge API)
    interaction_handler.slack_client.post.assert_called_once()
    slack_call = interaction_handler.slack_client.post.call_args
    assert "/chat.postEphemeral" in str(slack_call)
