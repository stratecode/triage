# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for Lambda invocation pattern support.

Feature: plugin-architecture
"""

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.core.event_bus import Event, EventBus
from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from triage.plugins.registry import PluginRegistry


class InvocationPattern(Enum):
    """Lambda invocation patterns."""

    SYNCHRONOUS = "synchronous"  # Direct Lambda invocation (API Gateway)
    ASYNCHRONOUS = "asynchronous"  # SQS/SNS event processing


@dataclass
class LambdaEvent:
    """Represents a Lambda event."""

    invocation_pattern: InvocationPattern
    event_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


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
def core_event_strategy(draw):
    """Generate random core events."""
    event_type = draw(
        st.sampled_from(["plan_generated", "task_blocked", "approval_timeout", "task_completed", "plan_approved"])
    )

    event_data = {
        "user_id": draw(st.text(min_size=5, max_size=30)),
        "timestamp": draw(st.floats(min_value=1000000000, max_value=2000000000)),
    }

    # Add event-specific data
    if event_type == "plan_generated":
        event_data["plan_id"] = draw(st.text(min_size=10, max_size=20))
        event_data["task_count"] = draw(st.integers(min_value=1, max_value=10))
    elif event_type == "task_blocked":
        event_data["task_key"] = draw(st.text(min_size=5, max_size=15))
        event_data["blocker_reason"] = draw(st.text(min_size=10, max_size=100))
    elif event_type == "approval_timeout":
        event_data["plan_id"] = draw(st.text(min_size=10, max_size=20))
        event_data["timeout_hours"] = draw(st.integers(min_value=1, max_value=48))

    return Event(event_type=event_type, event_data=event_data, timestamp=None, source="triage_core")


@st.composite
def lambda_event_strategy(draw, invocation_pattern: InvocationPattern):
    """Generate Lambda events for different invocation patterns."""
    if invocation_pattern == InvocationPattern.SYNCHRONOUS:
        # API Gateway event structure
        message = draw(plugin_message_strategy())
        return LambdaEvent(
            invocation_pattern=invocation_pattern,
            event_data={
                "path": "/plugins/slack/webhook",
                "httpMethod": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "X-Slack-Request-Timestamp": str(draw(st.integers(min_value=1000000000, max_value=2000000000))),
                    "X-Slack-Signature": draw(st.text(min_size=20, max_size=100)),
                },
                "body": json.dumps(
                    {
                        "type": "slash_command",
                        "command": message.command or "plan",
                        "text": message.content,
                        "user_id": message.user_id,
                        "channel_id": message.channel_id,
                    }
                ),
            },
            context={"request_id": draw(st.text(min_size=10, max_size=30)), "function_name": "plugin-handler"},
        )
    else:  # ASYNCHRONOUS
        # SQS event structure
        event = draw(core_event_strategy())
        return LambdaEvent(
            invocation_pattern=invocation_pattern,
            event_data={
                "Records": [
                    {
                        "messageId": draw(st.text(min_size=10, max_size=30)),
                        "body": json.dumps(
                            {"Message": json.dumps({"event_type": event.event_type, "event_data": event.event_data})}
                        ),
                        "attributes": {"ApproximateReceiveCount": str(draw(st.integers(min_value=1, max_value=3)))},
                    }
                ]
            },
            context={"request_id": draw(st.text(min_size=10, max_size=30)), "function_name": "event-processor"},
        )


class MockCoreActionsAPI:
    """Mock Core Actions API for testing."""

    def __init__(self):
        self.invocations = []

    async def generate_plan(self, user_id: str, **kwargs):
        self.invocations.append(("generate_plan", user_id, kwargs))
        return {"success": True, "plan": "mock_plan"}

    async def approve_plan(self, user_id: str, **kwargs):
        self.invocations.append(("approve_plan", user_id, kwargs))
        return {"success": True}

    async def get_status(self, user_id: str, **kwargs):
        self.invocations.append(("get_status", user_id, kwargs))
        return {"success": True, "status": "active"}

    async def reject_plan(self, user_id: str, **kwargs):
        self.invocations.append(("reject_plan", user_id, kwargs))
        return {"success": True}

    async def configure_settings(self, user_id: str, **kwargs):
        self.invocations.append(("configure_settings", user_id, kwargs))
        return {"success": True}


class InvocationTrackingPlugin(PluginInterface):
    """Test plugin that tracks invocations and patterns."""

    def __init__(self, name: str):
        self.name = name
        self.synchronous_invocations = []
        self.asynchronous_invocations = []
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
        """Track synchronous invocation (direct message handling)."""
        self.synchronous_invocations.append(
            {"type": "message", "message": message, "timestamp": asyncio.get_event_loop().time()}
        )

        # Invoke core action based on command
        if message.command == "plan":
            await self.core_api.generate_plan(message.user_id)
        elif message.command == "status":
            await self.core_api.get_status(message.user_id)
        elif message.command == "approve":
            await self.core_api.approve_plan(message.user_id)
        elif message.command == "reject":
            await self.core_api.reject_plan(message.user_id)
        elif message.command == "config":
            await self.core_api.configure_settings(message.user_id, {})

        return PluginResponse(content=f"Response from {self.name}", response_type="message")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Track asynchronous invocation (event handling)."""
        self.asynchronous_invocations.append(
            {
                "type": "event",
                "event_type": event_type,
                "event_data": event_data,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )


# Property 25: Lambda Invocation Pattern Support
@given(st.sampled_from([InvocationPattern.SYNCHRONOUS, InvocationPattern.ASYNCHRONOUS]))
@settings(max_examples=100)
def test_property_25_lambda_invocation_pattern_support(invocation_pattern: InvocationPattern):
    """Property 25: Lambda Invocation Pattern Support

    For any plugin operation, the system should support both synchronous (direct Lambda
    invocation) and asynchronous (SQS/SNS) invocation patterns without changing plugin code.

    Feature: plugin-architecture, Property 25: Lambda Invocation Pattern Support
    Validates: Requirements 15.4, 15.11
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create event bus
    event_bus = EventBus()

    # Create plugin registry
    registry = PluginRegistry(core_api, event_bus)

    # Create tracking plugin
    plugin = InvocationTrackingPlugin("slack")

    async def run_test():
        # Initialize plugin
        config = PluginConfig(plugin_name="slack", plugin_version="1.0.0", enabled=True, config={})
        await plugin.initialize(config, core_api)
        await plugin.start()

        # Register plugin
        registry.plugins["slack"] = plugin
        registry.plugin_health["slack"] = PluginStatus.HEALTHY

        # Generate Lambda event based on invocation pattern
        if invocation_pattern == InvocationPattern.SYNCHRONOUS:
            # Synchronous: Direct message handling (API Gateway -> Lambda)
            message = PluginMessage(
                channel_id="test_channel",
                user_id="test_user",
                content="test message",
                command="plan",
                parameters={},
                metadata={},
            )

            # Route message through registry (simulates synchronous Lambda invocation)
            response = await registry.route_message("slack", message)

            # Verify synchronous invocation was tracked
            assert len(plugin.synchronous_invocations) == 1, "Plugin should track synchronous invocation"
            assert (
                plugin.synchronous_invocations[0]["type"] == "message"
            ), "Synchronous invocation should be message type"
            assert plugin.synchronous_invocations[0]["message"] is message, "Plugin should receive the exact message"

            # Verify response was returned (synchronous pattern)
            assert response is not None, "Synchronous invocation should return response immediately"
            assert response.response_type != "error", "Synchronous invocation should succeed"

            # Verify core action was invoked
            assert len(core_api.invocations) == 1, "Core action should be invoked during synchronous processing"
            assert core_api.invocations[0][0] == "generate_plan", "Correct core action should be invoked"

        else:  # ASYNCHRONOUS
            # Asynchronous: Event handling (SQS -> Lambda)
            event_type = "plan_generated"
            event_data = {"user_id": "test_user", "plan_id": "test_plan", "task_count": 5}

            # Broadcast event through registry (simulates asynchronous Lambda invocation)
            await registry.broadcast_event(event_type, event_data)

            # Verify asynchronous invocation was tracked
            assert len(plugin.asynchronous_invocations) == 1, "Plugin should track asynchronous invocation"
            assert plugin.asynchronous_invocations[0]["type"] == "event", "Asynchronous invocation should be event type"
            assert (
                plugin.asynchronous_invocations[0]["event_type"] == event_type
            ), "Plugin should receive correct event type"
            assert (
                plugin.asynchronous_invocations[0]["event_data"] == event_data
            ), "Plugin should receive correct event data"

        # Verify plugin code didn't need to change for different invocation patterns
        # The plugin implements the same interface methods regardless of how it's invoked
        assert plugin.initialized, "Plugin should be initialized"
        assert plugin.started, "Plugin should be started"
        assert (
            await plugin.health_check() == PluginStatus.HEALTHY
        ), "Plugin should be healthy regardless of invocation pattern"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.lists(st.sampled_from([InvocationPattern.SYNCHRONOUS, InvocationPattern.ASYNCHRONOUS]), min_size=2, max_size=10)
)
@settings(max_examples=50)
def test_property_25_mixed_invocation_patterns(invocation_patterns: List[InvocationPattern]):
    """Property 25: Lambda Invocation Pattern Support (Mixed Patterns)

    For any sequence of plugin operations with mixed invocation patterns, the system
    should handle all patterns correctly without requiring plugin code changes.

    Feature: plugin-architecture, Property 25: Lambda Invocation Pattern Support
    Validates: Requirements 15.4, 15.11
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create event bus
    event_bus = EventBus()

    # Create plugin registry
    registry = PluginRegistry(core_api, event_bus)

    # Create tracking plugin
    plugin = InvocationTrackingPlugin("slack")

    async def run_test():
        # Initialize plugin
        config = PluginConfig(plugin_name="slack", plugin_version="1.0.0", enabled=True, config={})
        await plugin.initialize(config, core_api)
        await plugin.start()

        # Register plugin
        registry.plugins["slack"] = plugin
        registry.plugin_health["slack"] = PluginStatus.HEALTHY

        # Process mixed invocation patterns
        for pattern in invocation_patterns:
            if pattern == InvocationPattern.SYNCHRONOUS:
                # Synchronous invocation
                message = PluginMessage(
                    channel_id="test_channel",
                    user_id="test_user",
                    content="test message",
                    command="status",
                    parameters={},
                    metadata={},
                )
                response = await registry.route_message("slack", message)
                assert response is not None, "Synchronous invocation should return response"

            else:  # ASYNCHRONOUS
                # Asynchronous invocation
                event_type = "task_blocked"
                event_data = {"user_id": "test_user", "task_key": "TEST-123", "blocker_reason": "Waiting for review"}
                await registry.broadcast_event(event_type, event_data)

        # Verify both invocation patterns were tracked
        sync_count = sum(1 for p in invocation_patterns if p == InvocationPattern.SYNCHRONOUS)
        async_count = sum(1 for p in invocation_patterns if p == InvocationPattern.ASYNCHRONOUS)

        assert (
            len(plugin.synchronous_invocations) == sync_count
        ), f"Plugin should track {sync_count} synchronous invocations"
        assert (
            len(plugin.asynchronous_invocations) == async_count
        ), f"Plugin should track {async_count} asynchronous invocations"

        # Verify plugin remained healthy throughout
        assert (
            await plugin.health_check() == PluginStatus.HEALTHY
        ), "Plugin should remain healthy with mixed invocation patterns"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.sampled_from([InvocationPattern.SYNCHRONOUS, InvocationPattern.ASYNCHRONOUS]),
    st.integers(min_value=1, max_value=5),
)
@settings(max_examples=50)
def test_property_25_concurrent_invocations(invocation_pattern: InvocationPattern, concurrent_count: int):
    """Property 25: Lambda Invocation Pattern Support (Concurrent Invocations)

    For any invocation pattern with concurrent operations, the system should handle
    all invocations correctly without interference or state corruption.

    Feature: plugin-architecture, Property 25: Lambda Invocation Pattern Support
    Validates: Requirements 15.4, 15.11
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create event bus
    event_bus = EventBus()

    # Create plugin registry
    registry = PluginRegistry(core_api, event_bus)

    # Create tracking plugin
    plugin = InvocationTrackingPlugin("slack")

    async def run_test():
        # Initialize plugin
        config = PluginConfig(plugin_name="slack", plugin_version="1.0.0", enabled=True, config={})
        await plugin.initialize(config, core_api)
        await plugin.start()

        # Register plugin
        registry.plugins["slack"] = plugin
        registry.plugin_health["slack"] = PluginStatus.HEALTHY

        # Create concurrent invocations
        tasks = []

        for i in range(concurrent_count):
            if invocation_pattern == InvocationPattern.SYNCHRONOUS:
                # Synchronous invocation
                message = PluginMessage(
                    channel_id=f"channel_{i}",
                    user_id=f"user_{i}",
                    content=f"message {i}",
                    command="plan",
                    parameters={},
                    metadata={},
                )
                task = registry.route_message("slack", message)
                tasks.append(task)

            else:  # ASYNCHRONOUS
                # Asynchronous invocation
                event_type = "plan_generated"
                event_data = {"user_id": f"user_{i}", "plan_id": f"plan_{i}", "task_count": i + 1}
                task = registry.broadcast_event(event_type, event_data)
                tasks.append(task)

        # Wait for all concurrent invocations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all invocations succeeded
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Invocation {i} should not raise exception: {result}"

            if invocation_pattern == InvocationPattern.SYNCHRONOUS:
                assert result is not None, f"Synchronous invocation {i} should return response"

        # Verify correct number of invocations were tracked
        if invocation_pattern == InvocationPattern.SYNCHRONOUS:
            assert (
                len(plugin.synchronous_invocations) == concurrent_count
            ), f"Plugin should track {concurrent_count} synchronous invocations"
        else:
            assert (
                len(plugin.asynchronous_invocations) == concurrent_count
            ), f"Plugin should track {concurrent_count} asynchronous invocations"

        # Verify plugin remained healthy
        assert (
            await plugin.health_check() == PluginStatus.HEALTHY
        ), "Plugin should remain healthy with concurrent invocations"

    # Run the async test
    asyncio.run(run_test())


@given(st.sampled_from([InvocationPattern.SYNCHRONOUS, InvocationPattern.ASYNCHRONOUS]))
@settings(max_examples=50)
def test_property_25_invocation_pattern_isolation(invocation_pattern: InvocationPattern):
    """Property 25: Lambda Invocation Pattern Support (Pattern Isolation)

    For any invocation pattern, failures in one pattern should not affect the other pattern.
    The system should isolate synchronous and asynchronous invocations.

    Feature: plugin-architecture, Property 25: Lambda Invocation Pattern Support
    Validates: Requirements 15.4, 15.11
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create event bus
    event_bus = EventBus()

    # Create plugin registry
    registry = PluginRegistry(core_api, event_bus)

    # Create tracking plugin
    plugin = InvocationTrackingPlugin("slack")

    async def run_test():
        # Initialize plugin
        config = PluginConfig(plugin_name="slack", plugin_version="1.0.0", enabled=True, config={})
        await plugin.initialize(config, core_api)
        await plugin.start()

        # Register plugin
        registry.plugins["slack"] = plugin
        registry.plugin_health["slack"] = PluginStatus.HEALTHY

        # First, perform a successful invocation of the target pattern
        if invocation_pattern == InvocationPattern.SYNCHRONOUS:
            message = PluginMessage(
                channel_id="test_channel",
                user_id="test_user",
                content="test message",
                command="plan",
                parameters={},
                metadata={},
            )
            response = await registry.route_message("slack", message)
            assert response is not None, "Synchronous invocation should succeed"
            assert len(plugin.synchronous_invocations) == 1

        else:  # ASYNCHRONOUS
            event_type = "plan_generated"
            event_data = {"user_id": "test_user", "plan_id": "test_plan", "task_count": 5}
            await registry.broadcast_event(event_type, event_data)
            assert len(plugin.asynchronous_invocations) == 1

        # Now perform an invocation of the other pattern
        # This should work independently
        if invocation_pattern == InvocationPattern.SYNCHRONOUS:
            # Test that async still works
            event_type = "task_blocked"
            event_data = {"user_id": "test_user", "task_key": "TEST-123"}
            await registry.broadcast_event(event_type, event_data)
            assert len(plugin.asynchronous_invocations) == 1, "Asynchronous invocation should work independently"

        else:  # ASYNCHRONOUS
            # Test that sync still works
            message = PluginMessage(
                channel_id="test_channel",
                user_id="test_user",
                content="test message",
                command="status",
                parameters={},
                metadata={},
            )
            response = await registry.route_message("slack", message)
            assert response is not None, "Synchronous invocation should work independently"
            assert len(plugin.synchronous_invocations) == 1

        # Verify both patterns are isolated and functional
        assert plugin.initialized, "Plugin should remain initialized"
        assert plugin.started, "Plugin should remain started"
        assert await plugin.health_check() == PluginStatus.HEALTHY, "Plugin should remain healthy with both patterns"

    # Run the async test
    asyncio.run(run_test())
