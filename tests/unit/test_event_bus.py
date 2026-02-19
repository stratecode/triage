# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for EventBus.
"""

import asyncio
from datetime import datetime

import pytest

from triage.core.event_bus import Event, EventBus


@pytest.fixture
def event_bus():
    """Create an EventBus instance."""
    return EventBus()


@pytest.fixture
def sample_event():
    """Create a sample event."""
    return Event(event_type="plan_generated", event_data={"plan_id": "123", "user_id": "user456"})


def test_event_creation():
    """Test creating an Event."""
    event = Event(event_type="plan_generated", event_data={"plan_id": "123"})

    assert event.event_type == "plan_generated"
    assert event.event_data["plan_id"] == "123"
    assert event.source == "triage_core"
    assert isinstance(event.timestamp, datetime)


def test_event_bus_initialization(event_bus):
    """Test EventBus initialization."""
    assert event_bus.subscribers == {}
    assert isinstance(event_bus.event_queue, asyncio.Queue)


def test_subscribe(event_bus):
    """Test subscribing to an event type."""

    async def handler(event):
        pass

    event_bus.subscribe("plan_generated", handler)

    assert "plan_generated" in event_bus.subscribers
    assert len(event_bus.subscribers["plan_generated"]) == 1
    assert event_bus.subscribers["plan_generated"][0] == handler


def test_subscribe_multiple_handlers(event_bus):
    """Test subscribing multiple handlers to the same event type."""

    async def handler1(event):
        pass

    async def handler2(event):
        pass

    event_bus.subscribe("plan_generated", handler1)
    event_bus.subscribe("plan_generated", handler2)

    assert len(event_bus.subscribers["plan_generated"]) == 2


def test_unsubscribe(event_bus):
    """Test unsubscribing from an event type."""

    async def handler(event):
        pass

    event_bus.subscribe("plan_generated", handler)
    result = event_bus.unsubscribe("plan_generated", handler)

    assert result is True
    assert len(event_bus.subscribers["plan_generated"]) == 0


def test_unsubscribe_nonexistent(event_bus):
    """Test unsubscribing a handler that doesn't exist."""

    async def handler(event):
        pass

    result = event_bus.unsubscribe("plan_generated", handler)

    assert result is False


@pytest.mark.asyncio
async def test_publish_with_subscribers(event_bus, sample_event):
    """Test publishing an event with subscribers."""
    handler_called = []

    async def handler(event):
        handler_called.append(event)

    event_bus.subscribe("plan_generated", handler)
    await event_bus.publish(sample_event)

    assert len(handler_called) == 1
    assert handler_called[0] == sample_event


@pytest.mark.asyncio
async def test_publish_without_subscribers(event_bus, sample_event):
    """Test publishing an event with no subscribers."""
    # Should not raise an exception
    await event_bus.publish(sample_event)


@pytest.mark.asyncio
async def test_publish_multiple_handlers(event_bus, sample_event):
    """Test publishing to multiple handlers."""
    handler1_called = []
    handler2_called = []

    async def handler1(event):
        handler1_called.append(event)

    async def handler2(event):
        handler2_called.append(event)

    event_bus.subscribe("plan_generated", handler1)
    event_bus.subscribe("plan_generated", handler2)

    await event_bus.publish(sample_event)

    assert len(handler1_called) == 1
    assert len(handler2_called) == 1


@pytest.mark.asyncio
async def test_publish_with_handler_error(event_bus, sample_event):
    """Test publishing when a handler raises an error."""
    handler1_called = []
    handler2_called = []

    async def handler1(event):
        raise Exception("Handler error")

    async def handler2(event):
        handler2_called.append(event)

    event_bus.subscribe("plan_generated", handler1)
    event_bus.subscribe("plan_generated", handler2)

    # Should not raise exception
    await event_bus.publish(sample_event)

    # Second handler should still be called
    assert len(handler2_called) == 1


@pytest.mark.asyncio
async def test_publish_async(event_bus, sample_event):
    """Test publishing an event asynchronously to the queue."""
    await event_bus.publish_async(sample_event)

    assert event_bus.event_queue.qsize() == 1


@pytest.mark.asyncio
async def test_process_queue(event_bus):
    """Test processing events from the queue."""
    handler_called = []

    async def handler(event):
        handler_called.append(event)

    event_bus.subscribe("plan_generated", handler)

    event = Event(event_type="plan_generated", event_data={"plan_id": "123"})

    await event_bus.publish_async(event)

    # Process one event then cancel
    task = asyncio.create_task(event_bus.process_queue())
    await asyncio.sleep(0.1)  # Give it time to process
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(handler_called) == 1


def test_get_subscriber_count(event_bus):
    """Test getting subscriber count for an event type."""

    async def handler1(event):
        pass

    async def handler2(event):
        pass

    event_bus.subscribe("plan_generated", handler1)
    event_bus.subscribe("plan_generated", handler2)

    count = event_bus.get_subscriber_count("plan_generated")
    assert count == 2

    count_none = event_bus.get_subscriber_count("nonexistent")
    assert count_none == 0


def test_get_all_event_types(event_bus):
    """Test getting all event types with subscribers."""

    async def handler(event):
        pass

    event_bus.subscribe("plan_generated", handler)
    event_bus.subscribe("task_blocked", handler)

    event_types = event_bus.get_all_event_types()

    assert len(event_types) == 2
    assert "plan_generated" in event_types
    assert "task_blocked" in event_types


def test_clear_subscribers_specific(event_bus):
    """Test clearing subscribers for a specific event type."""

    async def handler(event):
        pass

    event_bus.subscribe("plan_generated", handler)
    event_bus.subscribe("task_blocked", handler)

    event_bus.clear_subscribers("plan_generated")

    assert "plan_generated" not in event_bus.subscribers
    assert "task_blocked" in event_bus.subscribers


def test_clear_subscribers_all(event_bus):
    """Test clearing all subscribers."""

    async def handler(event):
        pass

    event_bus.subscribe("plan_generated", handler)
    event_bus.subscribe("task_blocked", handler)

    event_bus.clear_subscribers()

    assert len(event_bus.subscribers) == 0


@pytest.mark.asyncio
async def test_start_stop_processing(event_bus):
    """Test starting and stopping queue processing."""
    event_bus.start_processing()

    assert event_bus._processing_task is not None
    assert not event_bus._processing_task.done()

    # Give it a moment to start
    await asyncio.sleep(0.01)

    event_bus.stop_processing()

    # Give it a moment to stop
    await asyncio.sleep(0.01)

    # Task should be cancelled
    assert event_bus._processing_task.cancelled() or event_bus._processing_task.done()
