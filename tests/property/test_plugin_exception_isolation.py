# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for plugin exception isolation.

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


@st.composite
def exception_type_strategy(draw):
    """Generate different types of exceptions."""
    exception_types = [
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        ConnectionError,
        TimeoutError,
    ]
    return draw(st.sampled_from(exception_types))


class MockCoreActionsAPI:
    """Mock Core Actions API for testing."""

    async def generate_plan(self, user_id: str, **kwargs):
        return {"success": True, "plan": "mock_plan"}


class ExceptionThrowingPlugin(PluginInterface):
    """Test plugin that throws various exceptions."""

    def __init__(self, name: str, exception_type: type, error_message: str):
        self.name = name
        self.exception_type = exception_type
        self.error_message = error_message
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
        # Throw the configured exception
        raise self.exception_type(self.error_message)

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        pass


# Property 23: Plugin Exception Isolation
@given(
    st.sampled_from(["slack", "whatsapp", "chatgpt"]),
    exception_type_strategy(),
    st.text(min_size=10, max_size=100),
    plugin_message_strategy(),
)
def test_property_23_plugin_exception_isolation(
    channel_type: str, exception_type: type, error_message: str, message: PluginMessage
):
    """Property 23: Plugin Exception Isolation

    For any exception raised by a plugin during message handling, the
    Plugin_Registry should catch it, log the error, and return a generic
    error response without crashing the system or exposing internal details.

    Feature: plugin-architecture, Property 23: Plugin Exception Isolation
    Validates: Requirements 11.1, 11.2, 11.7
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin that throws exceptions
        plugin = ExceptionThrowingPlugin(channel_type, exception_type, error_message)
        config = PluginConfig(plugin_name=channel_type, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[channel_type] = plugin
        registry.plugin_health[channel_type] = PluginStatus.HEALTHY

        # Route a message to the plugin (which will throw an exception)
        response = await registry.route_message(channel_type, message)

        # Verify the exception was caught and handled
        assert response is not None, "Registry should return a response even when plugin throws exception"

        assert response.response_type == "error", "Registry should return error response when plugin throws exception"

        # Verify the error message is generic (doesn't expose internal details)
        assert error_message not in response.content, "Error response should not expose internal error message"

        # Verify the error message doesn't expose exception type
        assert exception_type.__name__ not in response.content, "Error response should not expose exception type"

        # Verify the error message is user-friendly
        assert len(response.content) > 0, "Error response should have content"
        assert (
            "error" in response.content.lower() or "unavailable" in response.content.lower()
        ), "Error response should indicate a problem occurred"

        # Verify the plugin is marked as degraded
        assert (
            registry.plugin_health[channel_type] == PluginStatus.DEGRADED
        ), "Plugin should be marked as degraded after throwing exception"

        # Verify the system did not crash
        assert len(registry.plugins) > 0, "Registry should still have plugins registered after exception"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.lists(st.sampled_from(["slack", "whatsapp", "chatgpt"]), min_size=2, max_size=3, unique=True),
    exception_type_strategy(),
    st.text(min_size=10, max_size=100),
    plugin_message_strategy(),
)
def test_property_23_plugin_exception_isolation_multiple_exceptions(
    plugin_names: list, exception_type: type, error_message: str, message: PluginMessage
):
    """Property 23: Plugin Exception Isolation (Multiple Exceptions)

    For any set of plugins where multiple throw exceptions, the Plugin_Registry
    should catch each exception independently and continue operating.

    Feature: plugin-architecture, Property 23: Plugin Exception Isolation
    Validates: Requirements 11.1, 11.2, 11.7
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Register all plugins (all will throw exceptions)
        for name in plugin_names:
            plugin = ExceptionThrowingPlugin(name, exception_type, error_message)
            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})

            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[name] = plugin
            registry.plugin_health[name] = PluginStatus.HEALTHY

        # Route messages to all plugins
        for name in plugin_names:
            response = await registry.route_message(name, message)

            # Verify each exception was handled
            assert response is not None, f"Registry should return response for {name}"
            assert response.response_type == "error", f"Registry should return error response for {name}"
            assert (
                error_message not in response.content
            ), f"Error response for {name} should not expose internal details"
            assert registry.plugin_health[name] == PluginStatus.DEGRADED, f"Plugin {name} should be marked as degraded"

        # Verify the system is still operational
        assert len(registry.plugins) == len(plugin_names), "All plugins should still be registered"

    # Run the async test
    asyncio.run(run_test())


@given(st.sampled_from(["slack", "whatsapp", "chatgpt"]), st.text(min_size=10, max_size=100), plugin_message_strategy())
def test_property_23_plugin_exception_isolation_no_internal_details(
    channel_type: str, sensitive_data: str, message: PluginMessage
):
    """Property 23: Plugin Exception Isolation (No Internal Details)

    For any exception with sensitive internal details, the Plugin_Registry
    should never expose those details in the error response to users.

    Feature: plugin-architecture, Property 23: Plugin Exception Isolation
    Validates: Requirements 11.1, 11.2, 11.7
    """
    # Create an error message with "sensitive" data
    error_message = f"Database connection failed: {sensitive_data}"

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin that throws an exception with sensitive data
        plugin = ExceptionThrowingPlugin(channel_type, RuntimeError, error_message)
        config = PluginConfig(plugin_name=channel_type, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[channel_type] = plugin
        registry.plugin_health[channel_type] = PluginStatus.HEALTHY

        # Route a message to the plugin
        response = await registry.route_message(channel_type, message)

        # Verify the sensitive data is not exposed
        assert sensitive_data not in response.content, "Error response should not expose sensitive data from exception"

        assert (
            "Database connection failed" not in response.content
        ), "Error response should not expose internal error details"

        # Verify the response is generic
        assert response.response_type == "error", "Response should be an error type"

        # The response should be short and generic
        assert len(response.content) < 100, "Error response should be brief and generic"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.sampled_from(["slack", "whatsapp", "chatgpt"]), st.integers(min_value=1, max_value=5), plugin_message_strategy()
)
def test_property_23_plugin_exception_isolation_repeated_failures(
    channel_type: str, num_failures: int, message: PluginMessage
):
    """Property 23: Plugin Exception Isolation (Repeated Failures)

    For any plugin that throws exceptions repeatedly, the Plugin_Registry
    should continue to handle each exception gracefully without crashing.

    Feature: plugin-architecture, Property 23: Plugin Exception Isolation
    Validates: Requirements 11.1, 11.2, 11.7
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin that always throws exceptions
        plugin = ExceptionThrowingPlugin(channel_type, RuntimeError, "Plugin internal error")
        config = PluginConfig(plugin_name=channel_type, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[channel_type] = plugin
        registry.plugin_health[channel_type] = PluginStatus.HEALTHY

        # Send multiple messages (all will cause exceptions)
        for i in range(num_failures):
            response = await registry.route_message(channel_type, message)

            # Verify each exception was handled
            assert response is not None, f"Registry should return response for attempt {i+1}"
            assert response.response_type == "error", f"Registry should return error response for attempt {i+1}"
            assert (
                "Plugin internal error" not in response.content
            ), f"Error response {i+1} should not expose internal details"

        # Verify the plugin is marked as degraded
        assert (
            registry.plugin_health[channel_type] == PluginStatus.DEGRADED
        ), "Plugin should be marked as degraded after repeated failures"

        # Verify the system is still operational
        assert len(registry.plugins) > 0, "Registry should still have plugins after repeated failures"

    # Run the async test
    asyncio.run(run_test())
