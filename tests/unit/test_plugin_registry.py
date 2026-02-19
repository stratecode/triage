# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for PluginRegistry.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from triage.core.actions_api import CoreActionsAPI
from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from triage.plugins.registry import PluginRegistry


class MockPlugin(PluginInterface):
    """Mock plugin for testing."""

    def __init__(self):
        self.initialized = False
        self.started = False
        self.stopped = False
        self.config = None
        self.core_api = None

    def get_name(self) -> str:
        return "mock"

    def get_version(self) -> str:
        return "1.0.0"

    def get_config_schema(self) -> dict:
        return {"type": "object"}

    async def initialize(self, config, core_api) -> None:
        self.initialized = True
        self.config = config
        self.core_api = core_api

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def health_check(self):
        return PluginStatus.HEALTHY

    async def handle_message(self, message):
        return PluginResponse(content=f"Handled: {message.content}")

    async def send_message(self, channel_id, user_id, response) -> bool:
        return True

    async def handle_event(self, event_type, event_data) -> None:
        pass


@pytest.fixture
def core_api():
    """Create a mock CoreActionsAPI."""
    return Mock(spec=CoreActionsAPI)


@pytest.fixture
def registry(core_api):
    """Create a PluginRegistry instance."""
    return PluginRegistry(core_api=core_api)


@pytest.mark.asyncio
async def test_registry_initialization(registry, core_api):
    """Test PluginRegistry initialization."""
    assert registry.core_api == core_api
    assert registry.plugins == {}
    assert registry.plugin_health == {}


@pytest.mark.asyncio
async def test_load_plugin_success(registry, core_api):
    """Test successfully loading a plugin."""
    config = PluginConfig(plugin_name="mock", plugin_version="1.0.0", config={})

    # Mock the import
    with patch("importlib.import_module") as mock_import:
        mock_module = Mock()
        mock_module.MockPlugin = MockPlugin
        mock_import.return_value = mock_module

        result = await registry.load_plugin("mock", config)

        assert result is True
        assert "mock" in registry.plugins
        assert registry.plugin_health["mock"] == PluginStatus.HEALTHY


@pytest.mark.asyncio
async def test_load_plugin_import_error(registry):
    """Test loading a plugin that doesn't exist."""
    config = PluginConfig(plugin_name="nonexistent", plugin_version="1.0.0")

    result = await registry.load_plugin("nonexistent", config)

    assert result is False
    assert "nonexistent" not in registry.plugins


@pytest.mark.asyncio
async def test_start_all_plugins(registry):
    """Test starting all loaded plugins."""
    # Add a mock plugin directly
    plugin = MockPlugin()
    await plugin.initialize(PluginConfig(plugin_name="mock", plugin_version="1.0.0"), registry.core_api)
    registry.plugins["mock"] = plugin
    registry.plugin_health["mock"] = PluginStatus.HEALTHY

    await registry.start_all()

    assert plugin.started is True


@pytest.mark.asyncio
async def test_stop_all_plugins(registry):
    """Test stopping all loaded plugins."""
    # Add a mock plugin directly
    plugin = MockPlugin()
    await plugin.initialize(PluginConfig(plugin_name="mock", plugin_version="1.0.0"), registry.core_api)
    registry.plugins["mock"] = plugin
    registry.plugin_health["mock"] = PluginStatus.HEALTHY

    await registry.stop_all()

    assert plugin.stopped is True
    assert registry.plugin_health["mock"] == PluginStatus.STOPPED


@pytest.mark.asyncio
async def test_route_message_success(registry):
    """Test routing a message to a plugin."""
    # Add a mock plugin
    plugin = MockPlugin()
    await plugin.initialize(PluginConfig(plugin_name="mock", plugin_version="1.0.0"), registry.core_api)
    registry.plugins["mock"] = plugin
    registry.plugin_health["mock"] = PluginStatus.HEALTHY

    message = PluginMessage(channel_id="test", user_id="user", content="test message")

    response = await registry.route_message("mock", message)

    assert response.content == "Handled: test message"


@pytest.mark.asyncio
async def test_route_message_unknown_channel(registry):
    """Test routing a message to an unknown channel type."""
    message = PluginMessage(channel_id="test", user_id="user", content="test")

    response = await registry.route_message("unknown", message)

    assert response.response_type == "error"
    assert "Unknown channel type" in response.content


@pytest.mark.asyncio
async def test_route_message_unhealthy_plugin(registry):
    """Test routing a message to an unhealthy plugin."""
    # Add a mock plugin but mark it unhealthy
    plugin = MockPlugin()
    registry.plugins["mock"] = plugin
    registry.plugin_health["mock"] = PluginStatus.UNHEALTHY

    message = PluginMessage(channel_id="test", user_id="user", content="test")

    response = await registry.route_message("mock", message)

    assert response.response_type == "error"
    assert "temporarily unavailable" in response.content


@pytest.mark.asyncio
async def test_route_message_plugin_error(registry):
    """Test routing a message when plugin raises an error."""

    # Create a plugin that raises an error
    class ErrorPlugin(MockPlugin):
        async def handle_message(self, message):
            raise Exception("Plugin error")

    plugin = ErrorPlugin()
    registry.plugins["error"] = plugin
    registry.plugin_health["error"] = PluginStatus.HEALTHY

    message = PluginMessage(channel_id="test", user_id="user", content="test")

    response = await registry.route_message("error", message)

    assert response.response_type == "error"
    assert "error occurred" in response.content
    # Plugin should be marked as degraded
    assert registry.plugin_health["error"] == PluginStatus.DEGRADED


@pytest.mark.asyncio
async def test_broadcast_event(registry):
    """Test broadcasting an event to all plugins."""
    # Add mock plugins
    plugin1 = MockPlugin()
    plugin2 = MockPlugin()

    plugin1.handle_event = AsyncMock()
    plugin2.handle_event = AsyncMock()

    registry.plugins["plugin1"] = plugin1
    registry.plugins["plugin2"] = plugin2

    event_type = "plan_generated"
    event_data = {"plan_id": "123"}

    await registry.broadcast_event(event_type, event_data)

    plugin1.handle_event.assert_called_once_with(event_type, event_data)
    plugin2.handle_event.assert_called_once_with(event_type, event_data)


@pytest.mark.asyncio
async def test_broadcast_event_with_error(registry):
    """Test broadcasting an event when one plugin fails."""
    # Create plugins where one raises an error
    plugin1 = MockPlugin()
    plugin2 = MockPlugin()

    plugin1.handle_event = AsyncMock(side_effect=Exception("Handler error"))
    plugin2.handle_event = AsyncMock()

    registry.plugins["plugin1"] = plugin1
    registry.plugins["plugin2"] = plugin2

    event_type = "plan_generated"
    event_data = {"plan_id": "123"}

    # Should not raise exception
    await registry.broadcast_event(event_type, event_data)

    # Both plugins should have been called
    plugin1.handle_event.assert_called_once()
    plugin2.handle_event.assert_called_once()


@pytest.mark.asyncio
async def test_health_check_all(registry):
    """Test health checking all plugins."""
    # Add mock plugins with different health statuses
    plugin1 = MockPlugin()
    plugin2 = MockPlugin()

    async def healthy_check():
        return PluginStatus.HEALTHY

    async def degraded_check():
        return PluginStatus.DEGRADED

    plugin1.health_check = healthy_check
    plugin2.health_check = degraded_check

    registry.plugins["plugin1"] = plugin1
    registry.plugins["plugin2"] = plugin2

    health = await registry.health_check_all()

    assert health["plugin1"] == PluginStatus.HEALTHY
    assert health["plugin2"] == PluginStatus.DEGRADED


@pytest.mark.asyncio
async def test_health_check_with_error(registry):
    """Test health check when a plugin raises an error."""
    plugin = MockPlugin()

    async def failing_check():
        raise Exception("Health check failed")

    plugin.health_check = failing_check
    registry.plugins["plugin"] = plugin

    health = await registry.health_check_all()

    assert health["plugin"] == PluginStatus.UNHEALTHY


def test_get_plugin(registry):
    """Test getting a plugin by name."""
    plugin = MockPlugin()
    registry.plugins["mock"] = plugin

    retrieved = registry.get_plugin("mock")
    assert retrieved == plugin

    not_found = registry.get_plugin("nonexistent")
    assert not_found is None


def test_get_all_plugins(registry):
    """Test getting all plugins."""
    plugin1 = MockPlugin()
    plugin2 = MockPlugin()

    registry.plugins["plugin1"] = plugin1
    registry.plugins["plugin2"] = plugin2

    all_plugins = registry.get_all_plugins()

    assert len(all_plugins) == 2
    assert "plugin1" in all_plugins
    assert "plugin2" in all_plugins


def test_get_plugin_health(registry):
    """Test getting plugin health status."""
    registry.plugin_health["mock"] = PluginStatus.HEALTHY

    status = registry.get_plugin_health("mock")
    assert status == PluginStatus.HEALTHY

    not_found = registry.get_plugin_health("nonexistent")
    assert not_found is None
