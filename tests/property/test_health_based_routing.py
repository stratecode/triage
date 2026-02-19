# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for health-based routing.

Feature: plugin-architecture
"""

import asyncio
from typing import Any, Dict

from hypothesis import given
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


class ConfigurableHealthPlugin(PluginInterface):
    """Test plugin with configurable health status."""

    def __init__(self, name: str, health_status: PluginStatus = PluginStatus.HEALTHY):
        self.name = name
        self.health_status = health_status
        self.initialized = False
        self.started = False
        self.received_messages = []

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
        return self.health_status

    def set_health_status(self, status: PluginStatus):
        """Allow changing health status for testing."""
        self.health_status = status

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        self.received_messages.append(message)
        return PluginResponse(content=f"Response from {self.name}")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        pass


# Property 24: Health-Based Routing
@given(
    st.sampled_from(["slack", "whatsapp", "chatgpt"]),
    st.sampled_from([PluginStatus.DEGRADED, PluginStatus.UNHEALTHY, PluginStatus.STOPPED]),
    plugin_message_strategy(),
)
def test_property_24_health_based_routing_unhealthy_plugin(
    channel_type: str, unhealthy_status: PluginStatus, message: PluginMessage
):
    """Property 24: Health-Based Routing

    For any plugin that fails health checks repeatedly, the Plugin_Registry
    should mark it as unhealthy and continue routing requests to healthy plugins.

    Feature: plugin-architecture, Property 24: Health-Based Routing
    Validates: Requirements 11.3, 11.4
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin with unhealthy status
        plugin = ConfigurableHealthPlugin(channel_type, unhealthy_status)
        config = PluginConfig(plugin_name=channel_type, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[channel_type] = plugin
        registry.plugin_health[channel_type] = unhealthy_status

        # Try to route a message to the unhealthy plugin
        response = await registry.route_message(channel_type, message)

        # Verify the registry rejected the request due to health status
        assert response is not None, "Registry should return a response for unhealthy plugin"
        assert response.response_type == "error", "Registry should return error response for unhealthy plugin"
        assert (
            "unavailable" in response.content.lower() or "error" in response.content.lower()
        ), "Error response should indicate service is unavailable"

        # Verify the plugin did NOT receive the message
        assert len(plugin.received_messages) == 0, "Unhealthy plugin should not receive messages"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.lists(st.sampled_from(["slack", "whatsapp", "chatgpt", "discord"]), min_size=3, max_size=4, unique=True),
    st.integers(min_value=0, max_value=3),
    plugin_message_strategy(),
)
def test_property_24_health_based_routing_mixed_health(
    plugin_names: list, unhealthy_plugin_index: int, message: PluginMessage
):
    """Property 24: Health-Based Routing (Mixed Health)

    For any set of plugins with mixed health statuses, the Plugin_Registry
    should route requests only to healthy plugins and reject requests to
    unhealthy ones.

    Feature: plugin-architecture, Property 24: Health-Based Routing
    Validates: Requirements 11.3, 11.4
    """
    # Ensure we have a valid index
    unhealthy_plugin_index = unhealthy_plugin_index % len(plugin_names)
    unhealthy_plugin_name = plugin_names[unhealthy_plugin_index]

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    plugins = {}

    async def run_test():
        # Register all plugins with different health statuses
        for name in plugin_names:
            if name == unhealthy_plugin_name:
                # This plugin is unhealthy
                plugin = ConfigurableHealthPlugin(name, PluginStatus.UNHEALTHY)
                health_status = PluginStatus.UNHEALTHY
            else:
                # These plugins are healthy
                plugin = ConfigurableHealthPlugin(name, PluginStatus.HEALTHY)
                health_status = PluginStatus.HEALTHY

            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})

            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[name] = plugin
            registry.plugin_health[name] = health_status
            plugins[name] = plugin

        # Try to route messages to all plugins
        for name in plugin_names:
            response = await registry.route_message(name, message)

            if name == unhealthy_plugin_name:
                # Unhealthy plugin should be rejected
                assert response.response_type == "error", f"Unhealthy plugin {name} should return error response"
                assert len(plugins[name].received_messages) == 0, f"Unhealthy plugin {name} should not receive messages"
            else:
                # Healthy plugins should work
                assert response.response_type != "error", f"Healthy plugin {name} should not return error"
                assert len(plugins[name].received_messages) > 0, f"Healthy plugin {name} should receive messages"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.sampled_from(["slack", "whatsapp", "chatgpt"]), st.integers(min_value=1, max_value=5), plugin_message_strategy()
)
def test_property_24_health_based_routing_health_check_updates(
    channel_type: str, num_health_checks: int, message: PluginMessage
):
    """Property 24: Health-Based Routing (Health Check Updates)

    For any plugin, when health checks are performed, the Plugin_Registry
    should update the health status and adjust routing accordingly.

    Feature: plugin-architecture, Property 24: Health-Based Routing
    Validates: Requirements 11.3, 11.4
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin that starts healthy
        plugin = ConfigurableHealthPlugin(channel_type, PluginStatus.HEALTHY)
        config = PluginConfig(plugin_name=channel_type, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[channel_type] = plugin
        registry.plugin_health[channel_type] = PluginStatus.HEALTHY

        # Verify plugin works when healthy
        response = await registry.route_message(channel_type, message)
        assert response.response_type != "error", "Healthy plugin should work"
        assert len(plugin.received_messages) == 1, "Healthy plugin should receive messages"

        # Change plugin health to unhealthy
        plugin.set_health_status(PluginStatus.UNHEALTHY)

        # Run health checks multiple times
        for i in range(num_health_checks):
            health_statuses = await registry.health_check_all()

            # Verify the health status was updated
            assert (
                health_statuses[channel_type] == PluginStatus.UNHEALTHY
            ), f"Health check {i+1} should detect unhealthy status"
            assert (
                registry.plugin_health[channel_type] == PluginStatus.UNHEALTHY
            ), f"Registry should update health status after check {i+1}"

        # Try to route a message after health checks
        response = await registry.route_message(channel_type, message)

        # Verify the unhealthy plugin is now rejected
        assert response.response_type == "error", "Unhealthy plugin should be rejected after health checks"
        assert (
            len(plugin.received_messages) == 1
        ), "Unhealthy plugin should not receive new messages (still only 1 from before)"

    # Run the async test
    asyncio.run(run_test())


@given(st.sampled_from(["slack", "whatsapp", "chatgpt"]), plugin_message_strategy())
def test_property_24_health_based_routing_recovery(channel_type: str, message: PluginMessage):
    """Property 24: Health-Based Routing (Recovery)

    For any plugin that recovers from unhealthy to healthy status, the
    Plugin_Registry should resume routing requests to it.

    Feature: plugin-architecture, Property 24: Health-Based Routing
    Validates: Requirements 11.3, 11.4
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin that starts unhealthy
        plugin = ConfigurableHealthPlugin(channel_type, PluginStatus.UNHEALTHY)
        config = PluginConfig(plugin_name=channel_type, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[channel_type] = plugin
        registry.plugin_health[channel_type] = PluginStatus.UNHEALTHY

        # Verify plugin is rejected when unhealthy
        response = await registry.route_message(channel_type, message)
        assert response.response_type == "error", "Unhealthy plugin should be rejected"
        assert len(plugin.received_messages) == 0, "Unhealthy plugin should not receive messages"

        # Plugin recovers to healthy
        plugin.set_health_status(PluginStatus.HEALTHY)

        # Run health check to detect recovery
        await registry.health_check_all()

        # Verify health status was updated
        assert registry.plugin_health[channel_type] == PluginStatus.HEALTHY, "Registry should detect plugin recovery"

        # Try to route a message after recovery
        response = await registry.route_message(channel_type, message)

        # Verify the recovered plugin now works
        assert response.response_type != "error", "Recovered plugin should work"
        assert len(plugin.received_messages) == 1, "Recovered plugin should receive messages"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.lists(st.sampled_from(["slack", "whatsapp", "chatgpt"]), min_size=2, max_size=3, unique=True),
    plugin_message_strategy(),
)
def test_property_24_health_based_routing_all_unhealthy(plugin_names: list, message: PluginMessage):
    """Property 24: Health-Based Routing (All Unhealthy)

    For any set of plugins where all are unhealthy, the Plugin_Registry
    should reject all routing requests with appropriate error messages.

    Feature: plugin-architecture, Property 24: Health-Based Routing
    Validates: Requirements 11.3, 11.4
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Register all plugins as unhealthy
        for name in plugin_names:
            plugin = ConfigurableHealthPlugin(name, PluginStatus.UNHEALTHY)
            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})

            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[name] = plugin
            registry.plugin_health[name] = PluginStatus.UNHEALTHY

        # Try to route messages to all plugins
        for name in plugin_names:
            response = await registry.route_message(name, message)

            # Verify all requests are rejected
            assert response is not None, f"Registry should return response for {name}"
            assert response.response_type == "error", f"Unhealthy plugin {name} should return error response"
            assert (
                "unavailable" in response.content.lower() or "error" in response.content.lower()
            ), f"Error response for {name} should indicate unavailability"

        # Verify the registry is still operational
        assert len(registry.plugins) == len(plugin_names), "All plugins should still be registered"

    # Run the async test
    asyncio.run(run_test())
