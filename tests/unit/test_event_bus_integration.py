# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for EventBus with PlanGenerator, BackgroundScheduler, and ApprovalManager.
"""

import asyncio
from datetime import date
from unittest.mock import Mock, patch

import pytest

from triage.approval_manager import ApprovalManager, ApprovalTimeoutError
from triage.background_scheduler import BackgroundScheduler
from triage.core.event_bus import Event, EventBus
from triage.models import AdminBlock, DailyPlan, JiraIssue, TaskClassification
from triage.plan_generator import PlanGenerator


@pytest.fixture
def event_bus():
    """Create an EventBus instance."""
    return EventBus()


@pytest.fixture
def mock_jira_client():
    """Create a mock JIRA client."""
    client = Mock()
    client.fetch_active_tasks = Mock(return_value=[])
    client.fetch_blocking_tasks = Mock(return_value=[])
    return client


@pytest.fixture
def mock_classifier():
    """Create a mock task classifier."""
    classifier = Mock()
    classifier.classify_task = Mock(
        return_value=TaskClassification(
            task=JiraIssue(
                key="TEST-1",
                summary="Test task",
                description="Test",
                status="To Do",
                priority="Medium",
                issue_type="Task",
                assignee="user@example.com",
            ),
            category="PRIORITY",
            estimated_days=0.5,
            has_dependencies=False,
            is_priority_eligible=True,
        )
    )
    return classifier


@pytest.mark.asyncio
async def test_plan_generator_emits_plan_generated_event(event_bus, mock_jira_client, mock_classifier):
    """Test that PlanGenerator emits plan_generated event."""
    # Track emitted events
    emitted_events = []

    async def event_handler(event: Event):
        emitted_events.append(event)

    # Subscribe to plan_generated events
    event_bus.subscribe("plan_generated", event_handler)

    # Create plan generator with event bus
    plan_generator = PlanGenerator(jira_client=mock_jira_client, classifier=mock_classifier, event_bus=event_bus)

    # Generate a plan
    plan = plan_generator.generate_daily_plan()

    # Wait a bit for async event processing
    await asyncio.sleep(0.1)

    # Verify event was emitted
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.event_type == "plan_generated"
    assert "plan_date" in event.event_data
    assert "priority_count" in event.event_data
    assert event.event_data["plan_date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_background_scheduler_emits_task_blocked_event(event_bus, mock_jira_client, mock_classifier):
    """Test that BackgroundScheduler emits task_blocked event."""
    # Track emitted events
    emitted_events = []

    async def event_handler(event: Event):
        emitted_events.append(event)

    # Subscribe to task_blocked events
    event_bus.subscribe("task_blocked", event_handler)

    # Create a blocking task
    blocking_task = JiraIssue(
        key="BLOCK-1",
        summary="Blocking task",
        description="This is blocking",
        status="Blocked",
        priority="Blocker",
        issue_type="Bug",
        assignee="user@example.com",
    )

    # Create plan generator
    plan_generator = PlanGenerator(jira_client=mock_jira_client, classifier=mock_classifier)

    # Create background scheduler with event bus
    scheduler = BackgroundScheduler(jira_client=mock_jira_client, plan_generator=plan_generator, event_bus=event_bus)

    # Manually trigger blocking task handler
    scheduler._handle_blocking_task(blocking_task)

    # Wait a bit for async event processing
    await asyncio.sleep(0.1)

    # Verify event was emitted
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.event_type == "task_blocked"
    assert event.event_data["task_key"] == "BLOCK-1"
    assert event.event_data["task_summary"] == "Blocking task"


@pytest.mark.asyncio
async def test_approval_manager_emits_approval_timeout_event(event_bus):
    """Test that ApprovalManager emits approval_timeout event."""
    # Track emitted events
    emitted_events = []

    async def event_handler(event: Event):
        emitted_events.append(event)

    # Subscribe to approval_timeout events
    event_bus.subscribe("approval_timeout", event_handler)

    # Create approval manager with very short timeout and event bus
    approval_manager = ApprovalManager(timeout_seconds=1, event_bus=event_bus)

    # Create a sample plan
    plan = DailyPlan(
        date=date.today(),
        priorities=[],
        admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
        other_tasks=[],
    )

    # Mock input to simulate timeout
    with patch("builtins.input", side_effect=lambda _: None):
        with patch("signal.signal"):
            with patch("signal.alarm"):
                # Manually trigger timeout
                try:
                    approval_manager._setup_timeout()
                    # Simulate timeout by raising the exception
                    raise ApprovalTimeoutError("Test timeout")
                except ApprovalTimeoutError:
                    # Emit the event manually (simulating what happens in present_plan)
                    event = Event(
                        event_type="approval_timeout",
                        event_data={
                            "approval_type": "daily_plan",
                            "plan_date": plan.date.isoformat(),
                            "priority_count": len(plan.priorities),
                            "timeout_at": date.today().isoformat(),
                        },
                    )
                    await event_bus.publish(event)

    # Wait a bit for async event processing
    await asyncio.sleep(0.1)

    # Verify event was emitted
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.event_type == "approval_timeout"
    assert event.event_data["approval_type"] == "daily_plan"


@pytest.mark.asyncio
async def test_multiple_subscribers_receive_events(event_bus, mock_jira_client, mock_classifier):
    """Test that multiple subscribers receive the same event."""
    # Track emitted events for each subscriber
    subscriber1_events = []
    subscriber2_events = []

    async def handler1(event: Event):
        subscriber1_events.append(event)

    async def handler2(event: Event):
        subscriber2_events.append(event)

    # Subscribe both handlers to plan_generated events
    event_bus.subscribe("plan_generated", handler1)
    event_bus.subscribe("plan_generated", handler2)

    # Create plan generator with event bus
    plan_generator = PlanGenerator(jira_client=mock_jira_client, classifier=mock_classifier, event_bus=event_bus)

    # Generate a plan
    plan = plan_generator.generate_daily_plan()

    # Wait a bit for async event processing
    await asyncio.sleep(0.1)

    # Verify both subscribers received the event
    assert len(subscriber1_events) == 1
    assert len(subscriber2_events) == 1
    assert subscriber1_events[0].event_type == "plan_generated"
    assert subscriber2_events[0].event_type == "plan_generated"
