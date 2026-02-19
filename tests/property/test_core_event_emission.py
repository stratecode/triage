# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for core event emission.

Feature: plugin-architecture
"""

import asyncio
from datetime import date, timedelta
from typing import List
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.background_scheduler import BackgroundScheduler
from triage.core.event_bus import Event, EventBus
from triage.models import JiraIssue, TaskCategory, TaskClassification
from triage.plan_generator import PlanGenerator


# Custom strategies for generating test data
@st.composite
def jira_issue_strategy(draw):
    """Generate random JIRA issues."""
    project = draw(st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))

    return JiraIssue(
        key=f"{project}-{number}",
        summary=draw(st.text(min_size=5, max_size=100)),
        description=draw(st.text(min_size=0, max_size=200)),
        issue_type=draw(st.sampled_from(["Task", "Story", "Bug", "Epic"])),
        priority=draw(st.sampled_from(["Highest", "High", "Medium", "Low", "Lowest"])),
        status=draw(st.sampled_from(["To Do", "In Progress", "Done", "Blocked"])),
        assignee=draw(st.emails()),
    )


@st.composite
def blocking_issue_strategy(draw):
    """Generate random blocking JIRA issues."""
    issue = draw(jira_issue_strategy())
    # Force status to be blocking
    issue.status = "Blocked"
    return issue


@st.composite
def date_strategy(draw):
    """Generate random dates within a reasonable range."""
    days_offset = draw(st.integers(min_value=-30, max_value=30))
    return date.today() + timedelta(days=days_offset)


@st.composite
def closure_rate_strategy(draw):
    """Generate random closure rates (0.0 to 1.0)."""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


# Helper function to create event tracking handler
def create_event_tracker():
    """Create an event tracker that records all events."""
    events = []

    async def handler(event: Event):
        events.append(event)

    return events, handler


# Helper function to create mock JIRA client
def create_mock_jira_client(issues: List[JiraIssue]):
    """Create a mock JIRA client with predefined issues."""
    mock_client = Mock()
    mock_client.fetch_active_tasks = Mock(return_value=issues)
    mock_client.get_task_by_key = Mock(
        side_effect=lambda key: next((issue for issue in issues if issue.key == key), None)
    )
    return mock_client


# Helper function to create mock task classifier
def create_mock_classifier():
    """Create a mock task classifier."""
    mock_classifier = Mock()

    def classify_task(issue):
        return TaskClassification(
            task=issue,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=1.0,
        )

    mock_classifier.classify_task = Mock(side_effect=classify_task)
    return mock_classifier


# Property 20: Core Event Emission
@given(
    issues=st.lists(jira_issue_strategy(), min_size=0, max_size=10),
    plan_date=date_strategy(),
    closure_rate=closure_rate_strategy(),
)
@settings(max_examples=100, deadline=None)
def test_property_20_plan_generator_emits_plan_generated_event(
    issues: List[JiraIssue], plan_date: date, closure_rate: float
):
    """Property 20: Core Event Emission - Plan Generation

    For any plan generation operation that completes, the PlanGenerator should
    emit a 'plan_generated' event to the Event Bus with appropriate event data.

    Feature: plugin-architecture, Property 20: Core Event Emission
    Validates: Requirements 10.1
    """

    async def run_test():
        # Create event bus and tracker
        event_bus = EventBus()
        emitted_events, handler = create_event_tracker()
        event_bus.subscribe("plan_generated", handler)

        # Create mocks
        mock_jira_client = create_mock_jira_client(issues)
        mock_classifier = create_mock_classifier()

        # Create plan generator with event bus
        plan_generator = PlanGenerator(jira_client=mock_jira_client, classifier=mock_classifier, event_bus=event_bus)

        # Generate plan
        plan = plan_generator.generate_daily_plan(previous_closure_rate=closure_rate)

        # Wait a bit for async event emission
        await asyncio.sleep(0.1)

        # Verify event was emitted
        assert len(emitted_events) == 1, "Exactly one plan_generated event should be emitted"

        event = emitted_events[0]
        assert event.event_type == "plan_generated", "Event type must be 'plan_generated'"
        assert isinstance(event.event_data, dict), "Event data must be a dictionary"
        assert "plan_date" in event.event_data, "Event data must contain 'plan_date'"
        assert "priority_count" in event.event_data, "Event data must contain 'priority_count'"
        assert "admin_task_count" in event.event_data, "Event data must contain 'admin_task_count'"
        assert event.source == "triage_core", "Event source must be 'triage_core'"

        # Verify event data matches the generated plan
        assert event.event_data["plan_date"] == str(plan.date), "Event plan_date must match generated plan"
        assert event.event_data["priority_count"] == len(plan.priorities), "Event priority_count must match plan"
        assert event.event_data["admin_task_count"] == len(
            plan.admin_block.tasks
        ), "Event admin_task_count must match plan"

    # Run the async test
    asyncio.run(run_test())


@given(
    blocking_issues=st.lists(blocking_issue_strategy(), min_size=1, max_size=5),
    other_issues=st.lists(jira_issue_strategy(), min_size=0, max_size=5),
)
@settings(max_examples=100, deadline=None)
def test_property_20_background_scheduler_emits_task_blocked_event(
    blocking_issues: List[JiraIssue], other_issues: List[JiraIssue]
):
    """Property 20: Core Event Emission - Blocking Task Detection

    For any blocking task detection operation that completes, the BackgroundScheduler
    should emit a 'task_blocked' event to the Event Bus with appropriate event data.

    Feature: plugin-architecture, Property 20: Core Event Emission
    Validates: Requirements 10.2
    """

    async def run_test():
        # Create event bus and tracker
        event_bus = EventBus()
        emitted_events, handler = create_event_tracker()
        event_bus.subscribe("task_blocked", handler)

        # Combine issues
        all_issues = blocking_issues + other_issues

        # Create mocks
        mock_jira_client = create_mock_jira_client(all_issues)
        mock_classifier = create_mock_classifier()
        mock_plan_generator = PlanGenerator(jira_client=mock_jira_client, classifier=mock_classifier)

        # Create background scheduler with event bus
        scheduler = BackgroundScheduler(
            jira_client=mock_jira_client, plan_generator=mock_plan_generator, event_bus=event_bus
        )

        # Directly call the private method to trigger blocking task handling
        # This simulates what happens when the scheduler detects blocking tasks
        for blocking_issue in blocking_issues:
            scheduler._handle_blocking_task(blocking_issue)

        # Wait a bit for async event emission
        await asyncio.sleep(0.1)

        # Verify events were emitted for each blocking task
        assert len(emitted_events) == len(
            blocking_issues
        ), f"Should emit one event per blocking task (expected {len(blocking_issues)}, got {len(emitted_events)})"

        for event in emitted_events:
            assert event.event_type == "task_blocked", "Event type must be 'task_blocked'"
            assert isinstance(event.event_data, dict), "Event data must be a dictionary"
            assert "task_key" in event.event_data, "Event data must contain 'task_key'"
            assert "task_summary" in event.event_data, "Event data must contain 'task_summary'"
            assert "task_status" in event.event_data, "Event data must contain 'task_status'"
            assert "detected_at" in event.event_data, "Event data must contain 'detected_at'"
            assert event.source == "triage_core", "Event source must be 'triage_core'"

            # Verify the task_key corresponds to one of the blocking issues
            task_keys = [issue.key for issue in blocking_issues]
            assert event.event_data["task_key"] in task_keys, "Event task_key must be one of the blocking issues"

    # Run the async test
    asyncio.run(run_test())


# Note: Approval timeout test is not included because it requires user interaction
# (signal.alarm() and input()) which cannot be automated in property-based tests.
# The approval timeout event emission is tested in unit tests instead.


@given(operation=st.sampled_from(["plan_generation", "blocking_detection"]), should_emit=st.booleans())
@settings(max_examples=100, deadline=None)
def test_property_20_event_emission_consistency(operation: str, should_emit: bool):
    """Property 20: Core Event Emission - Consistency

    For any core operation, events should be emitted consistently when an event bus
    is configured, and should not cause errors when no event bus is configured.

    Feature: plugin-architecture, Property 20: Core Event Emission
    Validates: Requirements 10.1, 10.2, 10.3
    """

    async def run_test():
        # Create event bus and tracker only if should_emit is True
        if should_emit:
            event_bus = EventBus()
            emitted_events, handler = create_event_tracker()
            event_bus.subscribe("plan_generated", handler)
            event_bus.subscribe("task_blocked", handler)
        else:
            event_bus = None
            emitted_events = []

        # Execute the specified operation
        if operation == "plan_generation":
            mock_jira_client = create_mock_jira_client([])
            mock_classifier = create_mock_classifier()

            plan_generator = PlanGenerator(
                jira_client=mock_jira_client, classifier=mock_classifier, event_bus=event_bus
            )

            # This should not raise an error regardless of event_bus
            plan = plan_generator.generate_daily_plan(previous_closure_rate=0.8)
            assert plan is not None, "Plan generation should succeed"

            # Wait for async event emission
            await asyncio.sleep(0.1)

            if should_emit:
                assert len(emitted_events) >= 1, "Event should be emitted when event bus is configured"
                assert any(
                    e.event_type == "plan_generated" for e in emitted_events
                ), "plan_generated event should be emitted"
            else:
                assert len(emitted_events) == 0, "No events should be emitted without event bus"

        elif operation == "blocking_detection":
            blocking_issue = JiraIssue(
                key="BLOCK-1",
                summary="Blocked task",
                description="Test",
                issue_type="Task",
                priority="High",
                status="Blocked",
                assignee="test@example.com",
            )

            mock_jira_client = create_mock_jira_client([blocking_issue])
            mock_classifier = create_mock_classifier()
            mock_plan_generator = PlanGenerator(jira_client=mock_jira_client, classifier=mock_classifier)

            scheduler = BackgroundScheduler(
                jira_client=mock_jira_client, plan_generator=mock_plan_generator, event_bus=event_bus
            )

            # This should not raise an error regardless of event_bus
            # Directly call the private method to trigger event emission
            scheduler._handle_blocking_task(blocking_issue)

            # Wait for async event emission
            await asyncio.sleep(0.1)

            if should_emit:
                assert len(emitted_events) >= 1, "Event should be emitted when event bus is configured"
                assert any(
                    e.event_type == "task_blocked" for e in emitted_events
                ), "task_blocked event should be emitted"
            else:
                assert len(emitted_events) == 0, "No events should be emitted without event bus"

    # Run the async test
    asyncio.run(run_test())
