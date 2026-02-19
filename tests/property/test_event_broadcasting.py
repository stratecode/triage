# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for event broadcasting to plugins.

Feature: plugin-architecture
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.core.event_bus import Event, EventBus
from triage.plugins.interface import PluginConfig, PluginInterface, PluginMessage, PluginResponse, PluginStatus
from triage.plugins.registry import PluginRegistry


# Custom strategies for generating test data
@st.composite
def event_type_strategy(draw):
    """Generate random event types."""
    return draw(
        st.sampled_from(
            ["plan_generated", "task_blocked", "approval_timeout", "task_completed", "plan_approved", "plan_rejected"]
        )
    )


@st.composite
def event_data_strategy(draw):
    """Generate random event data dictionaries."""
    return {
        "plan_date": draw(st.dates()).isoformat(),
        "priority_count": draw(st.integers(min_value=0, max_value=3)),
        "admin_task_count": draw(st.integers(min_value=0, max_value=10)),
        "user_id": draw(st.emails()),
        "task_key": f"{draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=('Lu',))))}-{draw(st.integers(min_value=1, max_value=999))}",
    }


@st.composite
def event_strategy(draw):
    """Generate random events."""
    return Event(
        event_type=draw(event_type_strategy()),
        event_data=draw(event_data_strategy()),
        timestamp=datetime.now(),
        source="triage_core",
    )


# Mock plugin implementation for testing
class MockPlugin(PluginInterface):
    """Mock plugin for testing event broadcasting."""

    def __init__(self, name: str):
        self._name = name
        self.received_events: List[tuple] = []
        self.should_raise_error = False

    def get_name(self) -> str:
        return self._name

    def get_version(self) -> str:
        return "1.0.0"

    def get_config_schema(self) -> Dict[str, Any]:
        return {"type": "object"}

    async def initialize(self, config: PluginConfig, core_api: Any) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> PluginStatus:
        return PluginStatus.HEALTHY

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        return PluginResponse(content="OK")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Record received events for verification."""
        if self.should_raise_error:
            raise Exception(f"Plugin {self._name} error handling event")

        self.received_events.append((event_type, event_data))


# Helper function to create mock core API
def create_mock_core_api():
    """Create a mock Core Actions API."""
    return Mock()


# Property 21: Event Broadcasting to Plugins
@given(event=event_strategy(), num_plugins=st.integers(min_value=1, max_value=5))
@settings(max_examples=100, deadline=None)
def test_property_21_event_broadcast_to_all_plugins(event: Event, num_plugins: int):
    """Property 21: Event Broadcasting to Plugins

    For any core event emitted to the Event Bus, the Plugin_Registry should
    route it to all subscribed plugins.

    Feature: plugin-architecture, Property 21: Event Broadcasting to Plugins
    Validates: Requirements 10.5
    """

    async def run_test():
        # Create event bus and plugin registry
        event_bus = EventBus()
        core_api = create_mock_core_api()
        registry = PluginRegistry(core_api=core_api, event_bus=event_bus)

        # Create multiple mock plugins
        plugins = []
        for i in range(num_plugins):
            plugin = MockPlugin(name=f"plugin_{i}")
            plugins.append(plugin)
            # Manually add to registry (bypassing load_plugin for simplicity)
            registry.plugins[plugin.get_name()] = plugin
            registry.plugin_health[plugin.get_name()] = PluginStatus.HEALTHY

        # Broadcast event to all plugins
        await registry.broadcast_event(event.event_type, event.event_data)

        # Wait a bit for async processing
        await asyncio.sleep(0.1)

        # Verify all plugins received the event
        for plugin in plugins:
            assert len(plugin.received_events) == 1, f"Plugin {plugin.get_name()} should receive exactly one event"

            received_type, received_data = plugin.received_events[0]
            assert received_type == event.event_type, f"Plugin {plugin.get_name()} should receive correct event type"
            assert received_data == event.event_data, f"Plugin {plugin.get_name()} should receive correct event data"

    # Run the async test
    asyncio.run(run_test())


@given(events=st.lists(event_strategy(), min_size=1, max_size=5), num_plugins=st.integers(min_value=1, max_value=3))
@settings(max_examples=100, deadline=None)
def test_property_21_multiple_events_broadcast(events: List[Event], num_plugins: int):
    """Property 21: Event Broadcasting - Multiple Events

    For any sequence of core events, the Plugin_Registry should broadcast
    each event to all plugins in order.

    Feature: plugin-architecture, Property 21: Event Broadcasting to Plugins
    Validates: Requirements 10.5
    """

    async def run_test():
        # Create event bus and plugin registry
        event_bus = EventBus()
        core_api = create_mock_core_api()
        registry = PluginRegistry(core_api=core_api, event_bus=event_bus)

        # Create multiple mock plugins
        plugins = []
        for i in range(num_plugins):
            plugin = MockPlugin(name=f"plugin_{i}")
            plugins.append(plugin)
            registry.plugins[plugin.get_name()] = plugin
            registry.plugin_health[plugin.get_name()] = PluginStatus.HEALTHY

        # Broadcast all events
        for event in events:
            await registry.broadcast_event(event.event_type, event.event_data)

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify all plugins received all events
        for plugin in plugins:
            assert len(plugin.received_events) == len(
                events
            ), f"Plugin {plugin.get_name()} should receive all {len(events)} events"

            # Verify events were received in order
            for i, event in enumerate(events):
                received_type, received_data = plugin.received_events[i]
                assert received_type == event.event_type, f"Plugin {plugin.get_name()} should receive events in order"
                assert (
                    received_data == event.event_data
                ), f"Plugin {plugin.get_name()} should receive correct event data"

    # Run the async test
    asyncio.run(run_test())


@given(
    event=event_strategy(),
    num_healthy_plugins=st.integers(min_value=1, max_value=3),
    num_failing_plugins=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=100, deadline=None)
def test_property_21_event_broadcast_with_plugin_failures(
    event: Event, num_healthy_plugins: int, num_failing_plugins: int
):
    """Property 21: Event Broadcasting - Plugin Failure Isolation

    For any core event, if some plugins fail to handle the event, the
    Plugin_Registry should continue broadcasting to other plugins without
    system-wide impact.

    Feature: plugin-architecture, Property 21: Event Broadcasting to Plugins
    Validates: Requirements 10.5
    """

    async def run_test():
        # Create event bus and plugin registry
        event_bus = EventBus()
        core_api = create_mock_core_api()
        registry = PluginRegistry(core_api=core_api, event_bus=event_bus)

        # Create healthy plugins
        healthy_plugins = []
        for i in range(num_healthy_plugins):
            plugin = MockPlugin(name=f"healthy_plugin_{i}")
            healthy_plugins.append(plugin)
            registry.plugins[plugin.get_name()] = plugin
            registry.plugin_health[plugin.get_name()] = PluginStatus.HEALTHY

        # Create failing plugins
        failing_plugins = []
        for i in range(num_failing_plugins):
            plugin = MockPlugin(name=f"failing_plugin_{i}")
            plugin.should_raise_error = True
            failing_plugins.append(plugin)
            registry.plugins[plugin.get_name()] = plugin
            registry.plugin_health[plugin.get_name()] = PluginStatus.HEALTHY

        # Broadcast event (should not raise exception despite plugin failures)
        await registry.broadcast_event(event.event_type, event.event_data)

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify healthy plugins received the event
        for plugin in healthy_plugins:
            assert len(plugin.received_events) == 1, f"Healthy plugin {plugin.get_name()} should receive the event"

            received_type, received_data = plugin.received_events[0]
            assert received_type == event.event_type, "Healthy plugin should receive correct event type"
            assert received_data == event.event_data, "Healthy plugin should receive correct event data"

        # Verify failing plugins did not receive the event (due to exception)
        for plugin in failing_plugins:
            assert (
                len(plugin.received_events) == 0
            ), f"Failing plugin {plugin.get_name()} should not record event due to exception"

    # Run the async test
    asyncio.run(run_test())


@given(event=event_strategy(), has_plugins=st.booleans())
@settings(max_examples=100, deadline=None)
def test_property_21_event_broadcast_with_no_plugins(event: Event, has_plugins: bool):
    """Property 21: Event Broadcasting - No Plugins Case

    For any core event, the Plugin_Registry should handle broadcasting
    gracefully even when no plugins are loaded.

    Feature: plugin-architecture, Property 21: Event Broadcasting to Plugins
    Validates: Requirements 10.5
    """

    async def run_test():
        # Create event bus and plugin registry
        event_bus = EventBus()
        core_api = create_mock_core_api()
        registry = PluginRegistry(core_api=core_api, event_bus=event_bus)

        # Optionally add a plugin
        if has_plugins:
            plugin = MockPlugin(name="test_plugin")
            registry.plugins[plugin.get_name()] = plugin
            registry.plugin_health[plugin.get_name()] = PluginStatus.HEALTHY

        # Broadcast event (should not raise exception)
        try:
            await registry.broadcast_event(event.event_type, event.event_data)
            broadcast_succeeded = True
        except Exception:
            broadcast_succeeded = False

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify broadcast succeeded regardless of plugin presence
        assert broadcast_succeeded, "Event broadcast should succeed even with no plugins"

        # If plugin was added, verify it received the event
        if has_plugins:
            plugin = registry.plugins["test_plugin"]
            assert len(plugin.received_events) == 1, "Plugin should receive the event when present"

    # Run the async test
    asyncio.run(run_test())


@given(
    event=event_strategy(),
    num_plugins=st.integers(min_value=2, max_value=4),
    plugin_statuses=st.lists(
        st.sampled_from([PluginStatus.HEALTHY, PluginStatus.DEGRADED, PluginStatus.UNHEALTHY]), min_size=2, max_size=4
    ),
)
@settings(max_examples=100, deadline=None)
def test_property_21_event_broadcast_regardless_of_health(
    event: Event, num_plugins: int, plugin_statuses: List[PluginStatus]
):
    """Property 21: Event Broadcasting - Health Status Independence

    For any core event, the Plugin_Registry should broadcast to all plugins
    regardless of their health status (event broadcasting is separate from
    message routing which does check health).

    Feature: plugin-architecture, Property 21: Event Broadcasting to Plugins
    Validates: Requirements 10.5
    """

    async def run_test():
        # Create event bus and plugin registry
        event_bus = EventBus()
        core_api = create_mock_core_api()
        registry = PluginRegistry(core_api=core_api, event_bus=event_bus)

        # Ensure we have enough statuses
        while len(plugin_statuses) < num_plugins:
            plugin_statuses.append(PluginStatus.HEALTHY)

        # Create plugins with various health statuses
        plugins = []
        for i in range(num_plugins):
            plugin = MockPlugin(name=f"plugin_{i}")
            plugins.append(plugin)
            registry.plugins[plugin.get_name()] = plugin
            # Set different health statuses
            registry.plugin_health[plugin.get_name()] = plugin_statuses[i]

        # Broadcast event
        await registry.broadcast_event(event.event_type, event.event_data)

        # Wait for async processing
        await asyncio.sleep(0.1)

        # Verify ALL plugins received the event regardless of health status
        for plugin in plugins:
            assert (
                len(plugin.received_events) == 1
            ), f"Plugin {plugin.get_name()} should receive event regardless of health status"

            received_type, received_data = plugin.received_events[0]
            assert received_type == event.event_type, "Plugin should receive correct event type"
            assert received_data == event.event_data, "Plugin should receive correct event data"

    # Run the async test
    asyncio.run(run_test())
