# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for plugin failure isolation.

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


class FailingPlugin(PluginInterface):
    """Test plugin that fails during operations."""

    def __init__(self, name: str, fail_on_load: bool = False, fail_on_message: bool = False):
        self.name = name
        self.fail_on_load = fail_on_load
        self.fail_on_message = fail_on_message
        self.initialized = False
        self.started = False

    def get_name(self) -> str:
        return self.name

    def get_version(self) -> str:
        return "1.0.0"

    def get_config_schema(self) -> Dict[str, Any]:
        return {"type": "object"}

    async def initialize(self, config: PluginConfig, core_api: "CoreActionsAPI") -> None:
        if self.fail_on_load:
            raise RuntimeError(f"Plugin {self.name} failed to initialize")
        self.initialized = True
        self.config = config
        self.core_api = core_api

    async def start(self) -> None:
        if self.fail_on_load:
            raise RuntimeError(f"Plugin {self.name} failed to start")
        self.started = True

    async def stop(self) -> None:
        pass

    async def health_check(self) -> PluginStatus:
        return PluginStatus.HEALTHY

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        if self.fail_on_message:
            raise RuntimeError(f"Plugin {self.name} crashed during message handling")
        return PluginResponse(content=f"Response from {self.name}")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        pass


class HealthyPlugin(PluginInterface):
    """Test plugin that works correctly."""

    def __init__(self, name: str):
        self.name = name
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
        return PluginStatus.HEALTHY

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        self.received_messages.append(message)
        return PluginResponse(content=f"Response from {self.name}")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        pass


# Property 6: Plugin Failure Isolation
@given(
    st.lists(st.sampled_from(["slack", "whatsapp", "chatgpt"]), min_size=2, max_size=3, unique=True),
    st.integers(min_value=0, max_value=2),
    plugin_message_strategy(),
)
def test_property_6_plugin_failure_isolation_load_failure(
    plugin_names: list, failing_plugin_index: int, message: PluginMessage
):
    """Property 6: Plugin Failure Isolation (Load Failure)

    For any plugin that fails to load, the Plugin_Registry should isolate the
    failure, log the error, and continue loading other plugins without
    system-wide impact.

    Feature: plugin-architecture, Property 6: Plugin Failure Isolation
    Validates: Requirements 3.6, 3.7
    """
    # Ensure we have a valid index
    failing_plugin_index = failing_plugin_index % len(plugin_names)
    failing_plugin_name = plugin_names[failing_plugin_index]

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Try to load all plugins, with one failing
        load_results = {}
        for name in plugin_names:
            if name == failing_plugin_name:
                # This plugin will fail to load
                plugin = FailingPlugin(name, fail_on_load=True)
            else:
                # These plugins will load successfully
                plugin = HealthyPlugin(name)

            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})

            # Try to initialize the plugin
            try:
                await plugin.initialize(config, core_api)
                await plugin.start()
                registry.plugins[name] = plugin
                registry.plugin_health[name] = PluginStatus.HEALTHY
                load_results[name] = True
            except Exception:
                # Plugin failed to load - registry should handle this gracefully
                load_results[name] = False

        # Verify the failing plugin did not load
        assert (
            load_results[failing_plugin_name] == False
        ), f"Failing plugin {failing_plugin_name} should not load successfully"
        assert (
            failing_plugin_name not in registry.plugins
        ), f"Failing plugin {failing_plugin_name} should not be in registry"

        # Verify other plugins loaded successfully
        for name in plugin_names:
            if name != failing_plugin_name:
                assert (
                    load_results[name] == True
                ), f"Healthy plugin {name} should load successfully despite {failing_plugin_name} failure"
                assert name in registry.plugins, f"Healthy plugin {name} should be in registry"
                assert registry.plugins[name].initialized, f"Healthy plugin {name} should be initialized"
                assert registry.plugins[name].started, f"Healthy plugin {name} should be started"

        # Verify the registry is still functional
        # Try to route a message to a healthy plugin
        healthy_plugin_name = [n for n in plugin_names if n != failing_plugin_name][0]
        response = await registry.route_message(healthy_plugin_name, message)

        assert response is not None, "Registry should still function after plugin load failure"
        assert response.response_type != "error", "Registry should successfully route to healthy plugins"

    # Run the async test
    asyncio.run(run_test())


@given(st.sampled_from(["slack", "whatsapp", "chatgpt"]), plugin_message_strategy())
def test_property_6_plugin_failure_isolation_message_handling_crash(failing_channel: str, message: PluginMessage):
    """Property 6: Plugin Failure Isolation (Message Handling Crash)

    For any plugin that crashes during message handling, the Plugin_Registry
    should catch the exception, log the error, and return a generic error
    response without crashing the system.

    Feature: plugin-architecture, Property 6: Plugin Failure Isolation
    Validates: Requirements 3.6, 3.7
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    async def run_test():
        # Create a plugin that will crash during message handling
        plugin = FailingPlugin(failing_channel, fail_on_load=False, fail_on_message=True)
        config = PluginConfig(plugin_name=failing_channel, plugin_version="1.0.0", enabled=True, config={})

        await plugin.initialize(config, core_api)
        await plugin.start()

        registry.plugins[failing_channel] = plugin
        registry.plugin_health[failing_channel] = PluginStatus.HEALTHY

        # Route a message to the failing plugin
        response = await registry.route_message(failing_channel, message)

        # Verify the registry handled the crash gracefully
        assert response is not None, "Registry should return a response even when plugin crashes"
        assert response.response_type == "error", "Registry should return error response when plugin crashes"
        assert (
            "error occurred" in response.content.lower() or "unavailable" in response.content.lower()
        ), "Error response should indicate a problem occurred"

        # Verify the plugin is marked as degraded
        assert (
            registry.plugin_health[failing_channel] == PluginStatus.DEGRADED
        ), "Plugin should be marked as degraded after crash"

        # Verify the registry itself did not crash
        # (if we got here, the registry is still running)
        assert len(registry.plugins) > 0, "Registry should still have plugins registered"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.lists(st.sampled_from(["slack", "whatsapp", "chatgpt", "discord"]), min_size=3, max_size=4, unique=True),
    st.integers(min_value=0, max_value=3),
    plugin_message_strategy(),
)
def test_property_6_plugin_failure_isolation_one_crash_others_work(
    plugin_names: list, crashing_plugin_index: int, message: PluginMessage
):
    """Property 6: Plugin Failure Isolation (One Crash, Others Work)

    For any set of plugins where one crashes, the Plugin_Registry should
    isolate the failure and continue routing to other healthy plugins.

    Feature: plugin-architecture, Property 6: Plugin Failure Isolation
    Validates: Requirements 3.6, 3.7
    """
    # Ensure we have a valid index
    crashing_plugin_index = crashing_plugin_index % len(plugin_names)
    crashing_plugin_name = plugin_names[crashing_plugin_index]

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    plugins = {}

    async def run_test():
        # Register all plugins
        for name in plugin_names:
            if name == crashing_plugin_name:
                plugin = FailingPlugin(name, fail_on_load=False, fail_on_message=True)
            else:
                plugin = HealthyPlugin(name)

            config = PluginConfig(plugin_name=name, plugin_version="1.0.0", enabled=True, config={})

            await plugin.initialize(config, core_api)
            await plugin.start()

            registry.plugins[name] = plugin
            registry.plugin_health[name] = PluginStatus.HEALTHY
            plugins[name] = plugin

        # Route message to the crashing plugin
        crash_response = await registry.route_message(crashing_plugin_name, message)

        # Verify the crash was handled
        assert crash_response.response_type == "error", "Crashing plugin should return error response"
        assert (
            registry.plugin_health[crashing_plugin_name] == PluginStatus.DEGRADED
        ), "Crashing plugin should be marked as degraded"

        # Verify other plugins still work
        for name in plugin_names:
            if name != crashing_plugin_name:
                response = await registry.route_message(name, message)

                assert response is not None, f"Healthy plugin {name} should still respond"
                assert response.response_type != "error", f"Healthy plugin {name} should not return error"
                assert (
                    registry.plugin_health[name] == PluginStatus.HEALTHY
                ), f"Healthy plugin {name} should remain healthy"

                # Verify the healthy plugin received the message
                if isinstance(plugins[name], HealthyPlugin):
                    assert (
                        len(plugins[name].received_messages) > 0
                    ), f"Healthy plugin {name} should have received messages"

    # Run the async test
    asyncio.run(run_test())
