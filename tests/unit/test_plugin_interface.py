# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for plugin interface and data models.
"""

import pytest

from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from triage.plugins.models import PluginInstallation


def test_plugin_message_creation():
    """Test creating a PluginMessage with required fields."""
    message = PluginMessage(channel_id="workspace_123", user_id="user_456", content="Hello, TrIAge!")

    assert message.channel_id == "workspace_123"
    assert message.user_id == "user_456"
    assert message.content == "Hello, TrIAge!"
    assert message.command is None
    assert message.parameters == {}
    assert message.metadata == {}
    assert message.thread_id is None


def test_plugin_message_with_command():
    """Test creating a PluginMessage with command and parameters."""
    message = PluginMessage(
        channel_id="workspace_123",
        user_id="user_456",
        content="/triage plan",
        command="plan",
        parameters={"date": "2026-02-18"},
        metadata={"source": "slack"},
    )

    assert message.command == "plan"
    assert message.parameters["date"] == "2026-02-18"
    assert message.metadata["source"] == "slack"


def test_plugin_response_creation():
    """Test creating a PluginResponse."""
    response = PluginResponse(content="Your plan has been generated!", response_type="message")

    assert response.content == "Your plan has been generated!"
    assert response.response_type == "message"
    assert response.attachments == []
    assert response.actions == []
    assert response.metadata == {}


def test_plugin_response_with_actions():
    """Test creating a PluginResponse with interactive actions."""
    response = PluginResponse(
        content="Approve this plan?",
        response_type="message",
        actions=[
            {"type": "button", "text": "Approve", "action_id": "approve_plan"},
            {"type": "button", "text": "Reject", "action_id": "reject_plan"},
        ],
    )

    assert len(response.actions) == 2
    assert response.actions[0]["text"] == "Approve"
    assert response.actions[1]["text"] == "Reject"


def test_plugin_status_enum():
    """Test PluginStatus enum values."""
    assert PluginStatus.HEALTHY.value == "healthy"
    assert PluginStatus.DEGRADED.value == "degraded"
    assert PluginStatus.UNHEALTHY.value == "unhealthy"
    assert PluginStatus.STOPPED.value == "stopped"


def test_plugin_config_creation():
    """Test creating a PluginConfig."""
    config = PluginConfig(
        plugin_name="slack",
        plugin_version="1.0.0",
        enabled=True,
        config={"client_id": "test_client_id", "signing_secret": "test_secret"},
    )

    assert config.plugin_name == "slack"
    assert config.plugin_version == "1.0.0"
    assert config.enabled is True
    assert config.config["client_id"] == "test_client_id"


def test_plugin_installation_creation():
    """Test creating a PluginInstallation."""
    installation = PluginInstallation(
        id=1,
        plugin_name="slack",
        channel_id="workspace_123",
        access_token="encrypted_token",
        refresh_token="encrypted_refresh",
        metadata={"team_name": "Test Team"},
        is_active=True,
    )

    assert installation.id == 1
    assert installation.plugin_name == "slack"
    assert installation.channel_id == "workspace_123"
    assert installation.access_token == "encrypted_token"
    assert installation.metadata["team_name"] == "Test Team"


def test_plugin_installation_to_dict():
    """Test converting PluginInstallation to dictionary."""
    installation = PluginInstallation(
        id=1, plugin_name="slack", channel_id="workspace_123", access_token="token", is_active=True
    )

    data = installation.to_dict()

    assert data["id"] == 1
    assert data["plugin_name"] == "slack"
    assert data["channel_id"] == "workspace_123"
    assert data["is_active"] is True


def test_plugin_installation_from_dict():
    """Test creating PluginInstallation from dictionary."""
    data = {
        "id": 1,
        "plugin_name": "slack",
        "channel_id": "workspace_123",
        "access_token": "token",
        "refresh_token": "refresh",
        "metadata": {"key": "value"},
        "is_active": True,
    }

    installation = PluginInstallation.from_dict(data)

    assert installation.id == 1
    assert installation.plugin_name == "slack"
    assert installation.channel_id == "workspace_123"
    assert installation.metadata["key"] == "value"


def test_plugin_interface_is_abstract():
    """Test that PluginInterface cannot be instantiated directly."""
    with pytest.raises(TypeError):
        # Should raise TypeError because PluginInterface has abstract methods
        PluginInterface()


class MockPlugin(PluginInterface):
    """Mock plugin implementation for testing."""

    def get_name(self) -> str:
        return "mock"

    def get_version(self) -> str:
        return "1.0.0"

    def get_config_schema(self) -> dict:
        return {"type": "object"}

    async def initialize(self, config, core_api) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self):
        return PluginStatus.HEALTHY

    async def handle_message(self, message):
        return PluginResponse(content="Mock response")

    async def send_message(self, channel_id, user_id, response) -> bool:
        return True

    async def handle_event(self, event_type, event_data) -> None:
        pass


@pytest.mark.asyncio
async def test_mock_plugin_implementation():
    """Test that a concrete plugin implementation works."""
    plugin = MockPlugin()

    assert plugin.get_name() == "mock"
    assert plugin.get_version() == "1.0.0"

    status = await plugin.health_check()
    assert status == PluginStatus.HEALTHY

    message = PluginMessage(channel_id="test", user_id="user", content="test")
    response = await plugin.handle_message(message)
    assert response.content == "Mock response"
