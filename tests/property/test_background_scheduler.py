# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for background scheduler."""

import time
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.background_scheduler import BackgroundScheduler, OperationPriority
from triage.jira_client import JiraClient
from triage.models import JiraIssue
from triage.plan_generator import PlanGenerator


# Custom strategies for generating test data
@st.composite
def jira_issue_strategy(draw, priority="Blocker"):
    """Generate a JiraIssue with configurable priority."""
    key = f"PROJ-{draw(st.integers(min_value=1, max_value=9999))}"
    summary = draw(st.text(min_size=5, max_size=100))

    return JiraIssue(
        key=key,
        summary=summary,
        description=draw(st.text(max_size=500)),
        issue_type=draw(st.sampled_from(["Story", "Bug", "Task"])),
        priority=priority,
        status=draw(st.sampled_from(["To Do", "In Progress", "In Review"])),
        assignee="test@example.com",
        story_points=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=13))),
        time_estimate=draw(st.one_of(st.none(), st.integers(min_value=3600, max_value=86400))),
        labels=draw(st.lists(st.text(min_size=1, max_size=20), max_size=5)),
        issue_links=[],
        custom_fields={},
    )


@st.composite
def blocking_tasks_list_strategy(draw):
    """Generate a list of blocking tasks."""
    num_tasks = draw(st.integers(min_value=0, max_value=5))
    return [draw(jira_issue_strategy(priority="Blocker")) for _ in range(num_tasks)]


class TestBlockingTaskDetection:
    """
    Feature: ai-secretary, Property 8: Blocking Task Detection

    Validates: Requirements 3.1

    For any JIRA state containing a task marked with blocking priority,
    the system shall detect it during the next polling or planning cycle.
    """

    @given(blocking_tasks=blocking_tasks_list_strategy())
    @settings(max_examples=20, deadline=None)
    def test_blocking_task_detection(self, blocking_tasks):
        """
        Property: Blocking tasks are detected during polling.

        Given a JIRA state with blocking tasks,
        When the scheduler polls for blocking tasks,
        Then all blocking tasks should be detected and queued for handling.
        """
        # Create mock JIRA client that returns our blocking tasks
        mock_jira_client = Mock(spec=JiraClient)
        mock_jira_client.fetch_blocking_tasks.return_value = blocking_tasks

        # Create mock plan generator
        mock_plan_generator = Mock(spec=PlanGenerator)

        # Track operations queued
        queued_operations = []

        # Create scheduler with mocked dependencies
        scheduler = BackgroundScheduler(
            jira_client=mock_jira_client, plan_generator=mock_plan_generator, poll_interval_minutes=1
        )

        # Override queue_operation to track calls
        original_queue = scheduler.queue_operation

        def track_queue(*args, **kwargs):
            queued_operations.append((args, kwargs))
            return original_queue(*args, **kwargs)

        scheduler.queue_operation = track_queue

        # Manually trigger blocking task check (instead of waiting for polling)
        scheduler._check_blocking_tasks()

        # Verify: Number of queued operations should match number of blocking tasks
        assert len(queued_operations) == len(
            blocking_tasks
        ), f"Expected {len(blocking_tasks)} operations queued, got {len(queued_operations)}"

        # Verify: All queued operations should be for blocking tasks
        for args, kwargs in queued_operations:
            assert (
                kwargs.get("operation_type") == "handle_blocking_task"
            ), "Operation type should be 'handle_blocking_task'"
            assert kwargs.get("priority") == OperationPriority.BLOCKING, "Priority should be BLOCKING"

        # Verify: Each blocking task should have a corresponding operation
        queued_task_keys = {kwargs.get("task").key for (args, kwargs) in queued_operations}
        expected_task_keys = {task.key for task in blocking_tasks}

        assert (
            queued_task_keys == expected_task_keys
        ), f"Queued tasks {queued_task_keys} don't match expected {expected_task_keys}"

    @given(blocking_tasks=blocking_tasks_list_strategy())
    @settings(max_examples=10, deadline=None)
    def test_blocking_task_detection_with_polling(self, blocking_tasks):
        """
        Property: Blocking tasks are detected during polling cycle.

        Given a JIRA state with blocking tasks,
        When the scheduler runs its polling loop,
        Then blocking tasks should be detected and queued.
        """
        # Create mock JIRA client
        mock_jira_client = Mock(spec=JiraClient)
        mock_jira_client.fetch_blocking_tasks.return_value = blocking_tasks

        # Create mock plan generator
        mock_plan_generator = Mock(spec=PlanGenerator)

        # Track if blocking tasks were checked
        check_called = []

        # Create scheduler
        scheduler = BackgroundScheduler(
            jira_client=mock_jira_client, plan_generator=mock_plan_generator, poll_interval_minutes=1
        )

        # Override _check_blocking_tasks to track calls
        original_check = scheduler._check_blocking_tasks

        def track_check():
            check_called.append(True)
            return original_check()

        scheduler._check_blocking_tasks = track_check

        # Start scheduler
        scheduler.start()

        # Wait for at least one polling cycle
        time.sleep(2)

        # Stop scheduler
        scheduler.stop()

        # Verify: Blocking task check should have been called
        assert len(check_called) > 0, "Blocking task check should be called during polling"

        # Verify: fetch_blocking_tasks should have been called
        assert mock_jira_client.fetch_blocking_tasks.called, "fetch_blocking_tasks should be called during polling"


class TestOperationPriorityOrdering:
    """
    Feature: ai-secretary, Property 20: Operation Priority Ordering

    Validates: Requirements 8.5

    For any queue of pending operations containing blocking task operations
    and regular operations, blocking task operations shall be processed
    before regular operations.
    """

    @given(num_blocking=st.integers(min_value=1, max_value=5), num_normal=st.integers(min_value=1, max_value=5))
    @settings(max_examples=20, deadline=None)
    def test_operation_priority_ordering(self, num_blocking, num_normal):
        """
        Property: Blocking operations are processed before normal operations.

        Given a queue with both blocking and normal priority operations,
        When operations are processed,
        Then all blocking operations should be processed before normal operations.
        """
        # Create mock dependencies
        mock_jira_client = Mock(spec=JiraClient)
        mock_plan_generator = Mock(spec=PlanGenerator)

        # Track execution order
        execution_order = []

        def blocking_callback(task_id):
            execution_order.append(("blocking", task_id))

        def normal_callback(task_id):
            execution_order.append(("normal", task_id))

        # Create scheduler
        scheduler = BackgroundScheduler(
            jira_client=mock_jira_client, plan_generator=mock_plan_generator, poll_interval_minutes=1
        )

        # Queue operations in mixed order (normal, blocking, normal, blocking, ...)
        for i in range(max(num_blocking, num_normal)):
            if i < num_normal:
                scheduler.queue_operation(
                    operation_type=f"normal_{i}", callback=normal_callback, priority=OperationPriority.NORMAL, task_id=i
                )

            if i < num_blocking:
                scheduler.queue_operation(
                    operation_type=f"blocking_{i}",
                    callback=blocking_callback,
                    priority=OperationPriority.BLOCKING,
                    task_id=i,
                )

        # Start scheduler to process queue
        scheduler.start()

        # Wait for operations to be processed
        # Wait until queue is empty or timeout
        max_wait = 10  # seconds
        start_time = time.time()
        while not scheduler._operation_queue.empty() and (time.time() - start_time) < max_wait:
            time.sleep(0.1)

        # Stop scheduler
        scheduler.stop()

        # Verify: All operations should have been executed
        total_operations = num_blocking + num_normal
        assert (
            len(execution_order) == total_operations
        ), f"Expected {total_operations} operations executed, got {len(execution_order)}"

        # Verify: All blocking operations should come before normal operations
        blocking_indices = [i for i, (op_type, _) in enumerate(execution_order) if op_type == "blocking"]
        normal_indices = [i for i, (op_type, _) in enumerate(execution_order) if op_type == "normal"]

        if blocking_indices and normal_indices:
            max_blocking_index = max(blocking_indices)
            min_normal_index = min(normal_indices)

            assert max_blocking_index < min_normal_index, (
                f"All blocking operations should be processed before normal operations. "
                f"Last blocking at index {max_blocking_index}, first normal at {min_normal_index}. "
                f"Execution order: {execution_order}"
            )

    @given(
        operations=st.lists(
            st.tuples(st.sampled_from(["blocking", "normal"]), st.integers(min_value=0, max_value=100)),
            min_size=2,
            max_size=10,
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_priority_ordering_with_mixed_queue(self, operations):
        """
        Property: Priority ordering is maintained regardless of queue order.

        Given operations queued in any order,
        When they are processed,
        Then blocking operations are always processed first.
        """
        # Create mock dependencies
        mock_jira_client = Mock(spec=JiraClient)
        mock_plan_generator = Mock(spec=PlanGenerator)

        # Track execution order
        execution_order = []

        def callback(op_type, op_id):
            execution_order.append((op_type, op_id))

        # Create scheduler
        scheduler = BackgroundScheduler(
            jira_client=mock_jira_client, plan_generator=mock_plan_generator, poll_interval_minutes=1
        )

        # Queue all operations
        for op_type, op_id in operations:
            priority = OperationPriority.BLOCKING if op_type == "blocking" else OperationPriority.NORMAL
            scheduler.queue_operation(
                operation_type=f"{op_type}_{op_id}", callback=callback, priority=priority, op_type=op_type, op_id=op_id
            )

        # Start scheduler
        scheduler.start()

        # Wait for all operations to complete
        max_wait = 10
        start_time = time.time()
        while not scheduler._operation_queue.empty() and (time.time() - start_time) < max_wait:
            time.sleep(0.1)

        # Stop scheduler
        scheduler.stop()

        # Verify: All operations executed
        assert len(execution_order) == len(
            operations
        ), f"Expected {len(operations)} operations, got {len(execution_order)}"

        # Verify: Blocking operations come before normal operations
        blocking_count = sum(1 for op_type, _ in operations if op_type == "blocking")
        normal_count = len(operations) - blocking_count

        if blocking_count > 0 and normal_count > 0:
            # First blocking_count operations should all be blocking
            first_n = execution_order[:blocking_count]
            assert all(
                op_type == "blocking" for op_type, _ in first_n
            ), f"First {blocking_count} operations should be blocking, got {first_n}"

            # Remaining operations should all be normal
            remaining = execution_order[blocking_count:]
            assert all(
                op_type == "normal" for op_type, _ in remaining
            ), f"Remaining operations should be normal, got {remaining}"
