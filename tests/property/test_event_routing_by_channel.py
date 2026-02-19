# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for event routing by channel.

Feature: plugin-architecture
"""

import asyncio
from typing import Any, Dict

from hypothesis import assume, given
from hypothesis import strategies as st

from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from triage.plugins.registry import PluginRegistry


# Custom strategies for generating test data
@st.composite
def plugin_message_strategy(draw):
    """Generate random PluginMessage objects."""
    return PluginMessage(
        channel_id=draw(st.text(min_size=5, max_size=30)),
        user_id=draw(st.text(min_size=5, max_size=30)),
        content=draw(st.text(min_size=1, max_size=200)),
        command=draw(st.one_of(st.none(), st.sampled_from(["plan", "status", "config", "approve", "reject"]))),
        parameters=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3)),
        metadata=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=3)),
        thread_id=draw(st.one_of(st.none(), st.text(min_size=5, max_size=20))),
    )


class MockCoreActionsAPI:
    """Mock Core Actions API for testing."""

    async def generate_plan(self, user_id: str, **kwargs):
        return {"success": True, "plan": "mock_plan"}

    async def approve_plan(self, user_id: str, **kwargs):
        return {"success": True}

    async def get_status(self, user_id: str, **kwargs):
        return {"success": True, "status": "active"}


class TrackingPlugin(PluginInterface):
    """Test plugin that tracks received messages."""

    def __init__(self, name: str):
        self.name = name
        self.received_messages = []
        self.initialized = False
        self.started = False

    def get_name(self) -> str:
        return self.name

    def get_version(self) -> str:
        return "1.0.0"

    def get_config_schema(self) -> Dict[str, Any]:
        return {"type": "object"}

    async def initialize(self, config: PluginConfig, core_api: "CoreActionsAPI") -> None:
        self.initialized = True
        self.config = config
        self.core_api = core_api

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        pass

    async def health_check(self) -> PluginStatus:
        return PluginStatus.HEALTHY

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        """Track the message and return a response."""
        self.received_messages.append(message)
        return PluginResponse(content=f"Response from {self.name}", response_type="message")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        pass


# Property 5: Event Routing by Channel
@given(st.sampled_from(["slack", "whatsapp", "chatgpt", "discord", "teams"]), plugin_message_strategy())
def test_property_5_event_routing_by_channel(channel_type: str, message: PluginMessage):
    """Property 5: Event Routing by Channel

    For any incoming event with a channel identifier, the Plugin_Registry should
    route it to the correct plugin based on the channel type.

    Feature: plugin-architecture, Property 5: Event Routing by Channel
    Validates: Requirements 3.4
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    # Create multiple plugins with different channel types
    plugin_names = ["slack", "whatsapp", "chatgpt", "discord", "teams"]
    plugins = {}

    async def run_test():
        # Initialize and register all plugins
        for name in plugin_names:
            plugin = TrackingPlugin(name)
            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})
            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[name] = plugin
            registry.plugin_health[name] = PluginStatus.HEALTHY
            plugins[name] = plugin

        # Route the message to the specified channel type
        response = await registry.route_message(channel_type, message)

        # Verify the response is not an error
        assert response is not None, "Registry should return a response"
        assert (
            response.response_type != "error" or "Unknown channel type" not in response.content
        ), f"Registry should route to known channel type {channel_type}"

        # Verify the correct plugin received the message
        target_plugin = plugins[channel_type]
        assert len(target_plugin.received_messages) == 1, f"Plugin {channel_type} should receive exactly one message"
        assert (
            target_plugin.received_messages[0] is message
        ), f"Plugin {channel_type} should receive the exact message that was routed"

        # Verify other plugins did NOT receive the message
        for name, plugin in plugins.items():
            if name != channel_type:
                assert (
                    len(plugin.received_messages) == 0
                ), f"Plugin {name} should not receive messages for {channel_type}"

        # Verify the response came from the correct plugin
        assert (
            channel_type in response.content or response.content == f"Response from {channel_type}"
        ), f"Response should indicate it came from {channel_type} plugin"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))), plugin_message_strategy()
)
def test_property_5_event_routing_by_channel_unknown_channel(unknown_channel: str, message: PluginMessage):
    """Property 5: Event Routing by Channel (Unknown Channel)

    For any incoming event with an unknown channel identifier, the Plugin_Registry
    should return an error response indicating the channel is unknown.

    Feature: plugin-architecture, Property 5: Event Routing by Channel
    Validates: Requirements 3.4
    """
    # Assume the channel is not one of the known channels
    known_channels = ["slack", "whatsapp", "chatgpt", "discord", "teams"]
    assume(unknown_channel not in known_channels)

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    # Register only known plugins
    async def run_test():
        for name in known_channels:
            plugin = TrackingPlugin(name)
            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})
            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[name] = plugin
            registry.plugin_health[name] = PluginStatus.HEALTHY

        # Try to route to unknown channel
        response = await registry.route_message(unknown_channel, message)

        # Verify error response
        assert response is not None, "Registry should return a response for unknown channel"
        assert response.response_type == "error", "Registry should return error response for unknown channel"
        assert (
            "Unknown channel type" in response.content or "unknown" in response.content.lower()
        ), "Error message should indicate unknown channel"
        assert unknown_channel in response.content, "Error message should mention the unknown channel name"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.lists(st.sampled_from(["slack", "whatsapp", "chatgpt"]), min_size=2, max_size=5, unique=True),
    st.sampled_from(["slack", "whatsapp", "chatgpt"]),
    plugin_message_strategy(),
)
def test_property_5_event_routing_by_channel_multiple_plugins(
    registered_channels: list, target_channel: str, message: PluginMessage
):
    """Property 5: Event Routing by Channel (Multiple Plugins)

    For any set of registered plugins and a target channel, the Plugin_Registry
    should route messages only to the plugin matching the target channel.

    Feature: plugin-architecture, Property 5: Event Routing by Channel
    Validates: Requirements 3.4
    """
    # Ensure target channel is in registered channels
    if target_channel not in registered_channels:
        registered_channels.append(target_channel)

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    plugins = {}

    async def run_test():
        # Register all plugins
        for channel in registered_channels:
            plugin = TrackingPlugin(channel)
            config = PluginConfig(plugin_name=channel, plugin_version="1.0.0", enabled=True, config={})
            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[channel] = plugin
            registry.plugin_health[channel] = PluginStatus.HEALTHY
            plugins[channel] = plugin

        # Route message to target channel
        response = await registry.route_message(target_channel, message)

        # Verify response is successful
        assert response is not None, "Registry should return a response"
        assert response.response_type != "error", f"Registry should successfully route to {target_channel}"

        # Verify only the target plugin received the message
        for channel, plugin in plugins.items():
            if channel == target_channel:
                assert len(plugin.received_messages) == 1, f"Target plugin {channel} should receive the message"
                assert (
                    plugin.received_messages[0] is message
                ), f"Target plugin {channel} should receive the exact message"
            else:
                assert len(plugin.received_messages) == 0, f"Non-target plugin {channel} should not receive the message"

    # Run the async test
    asyncio.run(run_test())
