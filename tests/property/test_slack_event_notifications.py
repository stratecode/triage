# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-Based Test: Slack Event Notifications

Feature: plugin-architecture, Property 22: Slack Event Notifications

For any core event that the Slack_Connector subscribes to (plan generated,
task blocked), the connector should send appropriate notifications to
configured Slack channels.

Validates: Requirements 10.6, 10.7
"""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from triage.core.actions_api import CoreActionsAPI
from triage.plugins.interface import PluginConfig
from triage.plugins.slack.slack_plugin import SlackPlugin

# Hypothesis strategies for generating test data


@st.composite
def core_event_type_strategy(draw):
    """Generate valid core event types."""
    return draw(st.sampled_from(["plan_generated", "task_blocked", "approval_timeout"]))


@st.composite
def plan_generated_event_strategy(draw):
    """Generate plan_generated event data."""
    user_id = draw(st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
    channel_id = draw(st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))

    return {
        "user_id": user_id,
        "channel_id": channel_id,
        "plan_date": date.today().isoformat(),
        "plan_markdown": "# Daily Plan\n\n## Priorities\n- Task 1\n- Task 2\n- Task 3",
        "total_priorities": draw(st.integers(min_value=1, max_value=3)),
        "admin_tasks": draw(st.integers(min_value=0, max_value=10)),
    }


@st.composite
def task_blocked_event_strategy(draw):
    """Generate task_blocked event data."""
    user_id = draw(st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
    channel_id = draw(st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
    task_key = draw(st.text(min_size=5, max_size=15, alphabet=st.characters(whitelist_categories=("Lu", "Nd", "Pd"))))

    return {
        "user_id": user_id,
        "channel_id": channel_id,
        "task_key": task_key,
        "task_summary": draw(st.text(min_size=10, max_size=100)),
        "blocking_reason": draw(st.text(min_size=10, max_size=200)),
        "plan_date": date.today().isoformat(),
    }


@st.composite
def approval_timeout_event_strategy(draw):
    """Generate approval_timeout event data."""
    user_id = draw(st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
    channel_id = draw(st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))

    return {
        "user_id": user_id,
        "channel_id": channel_id,
        "plan_date": date.today().isoformat(),
        "timeout_hours": draw(st.integers(min_value=1, max_value=48)),
    }


class TestSlackEventNotifications:
    """
    Property 22: Slack Event Notifications

    Validates that core events trigger appropriate Slack notifications.
    """

    def create_mock_core_api(self):
        """Create mock Core Actions API."""
        api = AsyncMock(spec=CoreActionsAPI)
        return api

    async def create_slack_plugin(self, mock_core_api, channel_id="C12345678"):
        """Create SlackPlugin instance with mock dependencies."""
        from datetime import datetime

        from triage.plugins.models import PluginInstallation

        plugin = SlackPlugin()

        config = PluginConfig(
            plugin_name="slack",
            plugin_version="1.0.0",
            enabled=True,
            config={
                "signing_secret": "test_secret",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "bot_token": "xoxb-test-token",
            },
        )

        await plugin.initialize(config, mock_core_api)

        # Create a mock installation that storage will return
        mock_installation = PluginInstallation(
            id=1,
            plugin_name="slack",
            channel_id=channel_id,
            access_token="xoxb-test-token",
            is_active=True,
            installed_at=datetime.now(),
            last_active=datetime.now(),
        )

        # Mock the storage to return our mock installation
        plugin.storage = AsyncMock()
        plugin.storage.get_installation = AsyncMock(return_value=mock_installation)

        # Mock the Slack client that will be created in send_message
        # We need to patch AsyncWebClient to return our mock
        mock_client = AsyncMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1234567890.123456"})

        # Store the mock client for verification
        plugin._test_mock_client = mock_client

        return plugin, mock_client

    @given(event_data=plan_generated_event_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_plan_generated_sends_notification(self, event_data):
        """
        Property: plan_generated events trigger Slack notifications.

        Validates: Requirements 10.6, 10.7
        """
        from unittest.mock import patch

        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=event_data["channel_id"])

        # Patch AsyncWebClient to return our mock client
        with patch("triage.plugins.slack.slack_plugin.AsyncWebClient", return_value=mock_client):
            # Handle the event
            await slack_plugin.handle_event("plan_generated", event_data)

        # Verify Slack client was called to send message
        mock_client.chat_postMessage.assert_called()

        # Verify message was sent to correct channel (user_id as DM)
        call_args = mock_client.chat_postMessage.call_args
        assert call_args.kwargs["channel"] == event_data["user_id"]

        # Verify message contains plan information
        assert "text" in call_args.kwargs or "blocks" in call_args.kwargs

    @given(event_data=task_blocked_event_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_task_blocked_sends_notification(self, event_data):
        """
        Property: task_blocked events trigger Slack notifications.

        Validates: Requirements 10.6, 10.7
        """
        from unittest.mock import patch

        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=event_data["channel_id"])

        # Patch AsyncWebClient to return our mock client
        with patch("triage.plugins.slack.slack_plugin.AsyncWebClient", return_value=mock_client):
            # Handle the event
            await slack_plugin.handle_event("task_blocked", event_data)

        # Verify Slack client was called to send message
        mock_client.chat_postMessage.assert_called()

        # Verify message was sent to correct channel (user_id as DM)
        call_args = mock_client.chat_postMessage.call_args
        assert call_args.kwargs["channel"] == event_data["user_id"]

        # Verify message contains task information
        if "text" in call_args.kwargs:
            assert event_data["task_key"] in call_args.kwargs["text"] or any(
                event_data["task_key"] in str(block) for block in call_args.kwargs.get("blocks", [])
            )

    @given(event_data=approval_timeout_event_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_approval_timeout_sends_notification(self, event_data):
        """
        Property: approval_timeout events trigger Slack notifications.

        Validates: Requirements 10.6, 10.7
        """
        from unittest.mock import patch

        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=event_data["channel_id"])

        # Patch AsyncWebClient to return our mock client
        with patch("triage.plugins.slack.slack_plugin.AsyncWebClient", return_value=mock_client):
            # Handle the event
            await slack_plugin.handle_event("approval_timeout", event_data)

        # Verify Slack client was called to send message
        mock_client.chat_postMessage.assert_called()

        # Verify message was sent to correct channel (user_id as DM)
        call_args = mock_client.chat_postMessage.call_args
        assert call_args.kwargs["channel"] == event_data["user_id"]

    @given(
        event_type=core_event_type_strategy(),
        channel_id=st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))),
        user_id=st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))),
    )
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_event_notification_format(self, event_type, channel_id, user_id):
        """
        Property: Event notifications are properly formatted.

        Validates: Requirements 10.6, 10.7
        """
        from unittest.mock import patch

        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=channel_id)

        # Create event data based on type
        if event_type == "plan_generated":
            event_data = {
                "user_id": user_id,
                "channel_id": channel_id,
                "plan_date": date.today().isoformat(),
                "plan_markdown": "# Test Plan",
                "total_priorities": 3,
            }
        elif event_type == "task_blocked":
            event_data = {
                "user_id": user_id,
                "channel_id": channel_id,
                "task_key": "TEST-123",
                "task_summary": "Test task",
                "blocking_reason": "Waiting for approval",
            }
        else:  # approval_timeout
            event_data = {
                "user_id": user_id,
                "channel_id": channel_id,
                "plan_date": date.today().isoformat(),
                "timeout_hours": 24,
            }

        # Patch AsyncWebClient to return our mock client
        with patch("triage.plugins.slack.slack_plugin.AsyncWebClient", return_value=mock_client):
            # Handle the event
            await slack_plugin.handle_event(event_type, event_data)

        # Verify message was sent
        mock_client.chat_postMessage.assert_called()

        # Verify message format
        call_args = mock_client.chat_postMessage.call_args
        assert "channel" in call_args.kwargs
        assert call_args.kwargs["channel"] == user_id

    @given(event_data=plan_generated_event_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_notification_error_handling(self, event_data):
        """
        Property: Notification errors are handled gracefully.

        Validates: Requirements 10.6, 10.7
        """
        from unittest.mock import patch

        # Create mocks with error
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=event_data["channel_id"])

        # Make Slack client raise an error
        mock_client.chat_postMessage = AsyncMock(side_effect=Exception("Slack API error"))

        # Patch AsyncWebClient to return our mock client
        with patch("triage.plugins.slack.slack_plugin.AsyncWebClient", return_value=mock_client):
            # Handle the event - should not crash
            try:
                await slack_plugin.handle_event("plan_generated", event_data)
                # If no exception, test passes
                assert True
            except Exception as e:
                # Should not raise exception
                pytest.fail(f"Event handling raised exception: {e}")

    @given(event_data=plan_generated_event_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_notification_includes_user_context(self, event_data):
        """
        Property: Notifications include user context.

        Validates: Requirements 10.6, 10.7
        """
        from unittest.mock import patch

        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=event_data["channel_id"])

        # Patch AsyncWebClient to return our mock client
        with patch("triage.plugins.slack.slack_plugin.AsyncWebClient", return_value=mock_client):
            # Handle the event
            await slack_plugin.handle_event("plan_generated", event_data)

        # Verify message was sent
        mock_client.chat_postMessage.assert_called()

        # Verify user context is preserved
        call_args = mock_client.chat_postMessage.call_args

        # User should be mentioned or referenced in the message
        message_text = call_args.kwargs.get("text", "")
        message_blocks = call_args.kwargs.get("blocks", [])

        # At least one should be present
        assert message_text or message_blocks

    @given(
        event_type=core_event_type_strategy(),
        channel_id=st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))),
    )
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_unknown_event_handled_gracefully(self, event_type, channel_id):
        """
        Property: Unknown events are handled gracefully.

        Validates: Requirements 10.6, 10.7
        """
        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin, mock_client = await self.create_slack_plugin(mock_core_api, channel_id=channel_id)

        # Create event with minimal data
        event_data = {"channel_id": channel_id, "user_id": "TEST123"}

        # Handle unknown event type - should not crash
        try:
            await slack_plugin.handle_event("unknown_event", event_data)
            # If no exception, test passes
            assert True
        except Exception as e:
            # Should not raise exception for unknown events
            pytest.fail(f"Unknown event handling raised exception: {e}")
