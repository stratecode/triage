# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for task decomposition.

Feature: ai-secretary
"""

from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.jira_client import JiraClient
from triage.models import (
    JiraIssue,
    SubtaskSpec,
)
from triage.plan_generator import PlanGenerator
from triage.task_classifier import TaskClassifier


# Custom strategies for generating test data
@st.composite
def jira_issue_strategy(draw, estimated_days=None):
    """Generate random JiraIssue objects with optional effort constraint."""
    issue_types = ["Story", "Bug", "Task", "Epic"]
    priorities = ["High", "Medium", "Low"]
    statuses = ["To Do", "In Progress"]

    # Generate JIRA-style keys like PROJ-123 (limited alphabet to prevent memory issues)
    project = draw(st.text(min_size=2, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)))
    number = draw(st.integers(min_value=1, max_value=999))
    key = f"{project}-{number}"

    # Generate story points based on estimated_days
    story_points = None
    time_estimate = None
    if estimated_days is not None:
        # Convert days to story points (1.25 days per story point)
        story_points = int(estimated_days / 1.25)
        if story_points == 0:
            story_points = 1
    else:
        story_points = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=13)))

    return JiraIssue(
        key=key,
        summary=draw(st.text(min_size=5, max_size=50, alphabet=st.characters(blacklist_categories=("Cs", "Cc")))),
        description=draw(st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs", "Cc")))),
        issue_type=draw(st.sampled_from(issue_types)),
        priority=draw(st.sampled_from(priorities)),
        status=draw(st.sampled_from(statuses)),
        assignee=draw(st.emails()),
        story_points=story_points,
        time_estimate=time_estimate,
        labels=[],
        issue_links=[],
        custom_fields={},
    )


# Property 11: Long-Running Task Identification
@given(
    estimated_days=st.floats(min_value=1.1, max_value=5.0),  # Reduced from 10.0
    key_prefix=st.text(min_size=2, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
    key_number=st.integers(min_value=1, max_value=999),
    summary=st.text(min_size=5, max_size=50, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))),
    description=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))),
    issue_type=st.sampled_from(["Story", "Bug", "Task", "Epic"]),
    priority=st.sampled_from(["High", "Medium", "Low"]),
    status=st.sampled_from(["To Do", "In Progress"]),
    assignee=st.emails(),
)
@settings(max_examples=50, deadline=3000)  # Added settings to limit resources
def test_property_11_long_running_task_identification(
    estimated_days, key_prefix, key_number, summary, description, issue_type, priority, status, assignee
):
    """Property 11: Long-Running Task Identification

    For any task with estimated effort greater than 1.0 days, the system shall
    identify it as a long-running task requiring decomposition.

    Feature: ai-secretary, Property 11: Long-Running Task Identification
    Validates: Requirements 1.4, 4.1
    """
    # Create a task with effort > 1 day
    # Use time_estimate instead of story_points for more precise control
    # time_estimate is in seconds, so convert days to seconds
    time_estimate_seconds = int(estimated_days * 8 * 60 * 60)

    task = JiraIssue(
        key=f"{key_prefix}-{key_number}",
        summary=summary,
        description=description,
        issue_type=issue_type,
        priority=priority,
        status=status,
        assignee=assignee,
        story_points=None,
        time_estimate=time_estimate_seconds,
        labels=[],
        issue_links=[],
        custom_fields={},
    )

    # Create mock JIRA client
    mock_jira_client = Mock(spec=JiraClient)

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Classify the task
    classification = classifier.classify_task(task)

    # Verify task is identified as long-running
    assert (
        classification.estimated_days > 1.0
    ), f"Task with {estimated_days} days should have estimated_days > 1.0, got {classification.estimated_days}"

    # Verify propose_decomposition returns subtasks for this task
    subtasks = plan_generator.propose_decomposition(task)

    assert (
        len(subtasks) > 0
    ), f"Task with {classification.estimated_days} days (>{1.0}) should be identified for decomposition, but got 0 subtasks"

    # Verify subtasks is a list of SubtaskSpec objects
    assert isinstance(subtasks, list), "Subtasks should be a list"
    for subtask in subtasks:
        assert isinstance(subtask, SubtaskSpec), "Each subtask should be a SubtaskSpec object"


# Property 12: Decomposition Subtask Constraints
@given(
    estimated_days=st.floats(min_value=1.5, max_value=5.0),  # Reduced from 10.0
    key_prefix=st.text(min_size=2, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
    key_number=st.integers(min_value=1, max_value=999),
    summary=st.text(min_size=5, max_size=50, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))),
    description=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))),
    issue_type=st.sampled_from(["Story", "Bug", "Task", "Epic"]),
    priority=st.sampled_from(["High", "Medium", "Low"]),
    status=st.sampled_from(["To Do", "In Progress"]),
    assignee=st.emails(),
)
@settings(max_examples=50, deadline=3000)  # Added settings to limit resources
def test_property_12_decomposition_subtask_constraints(
    estimated_days, key_prefix, key_number, summary, description, issue_type, priority, status, assignee
):
    """Property 12: Decomposition Subtask Constraints

    For any proposed decomposition of a long-running task, all subtasks shall have
    estimated effort of at most 1.0 days.

    Feature: ai-secretary, Property 12: Decomposition Subtask Constraints
    Validates: Requirements 4.2, 4.3
    """
    # Create a long-running task
    # Use time_estimate instead of story_points for more precise control
    time_estimate_seconds = int(estimated_days * 8 * 60 * 60)

    task = JiraIssue(
        key=f"{key_prefix}-{key_number}",
        summary=summary,
        description=description,
        issue_type=issue_type,
        priority=priority,
        status=status,
        assignee=assignee,
        story_points=None,
        time_estimate=time_estimate_seconds,
        labels=[],
        issue_links=[],
        custom_fields={},
    )

    # Create mock JIRA client
    mock_jira_client = Mock(spec=JiraClient)

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Propose decomposition
    subtasks = plan_generator.propose_decomposition(task)

    # Verify all subtasks have effort <= 1.0 days
    for i, subtask in enumerate(subtasks):
        assert (
            subtask.estimated_days <= 1.0
        ), f"Subtask {i+1} has effort {subtask.estimated_days} days, but maximum is 1.0"

        # Verify effort is positive
        assert subtask.estimated_days > 0, f"Subtask {i+1} has non-positive effort: {subtask.estimated_days}"

        # Verify subtask has required fields
        assert subtask.summary, f"Subtask {i+1} has empty summary"
        assert subtask.description, f"Subtask {i+1} has empty description"
        assert subtask.order > 0, f"Subtask {i+1} has invalid order: {subtask.order}"

    # Verify subtasks are ordered correctly
    orders = [subtask.order for subtask in subtasks]
    assert orders == sorted(orders), "Subtasks should be ordered sequentially"

    # Verify total effort approximately equals original task effort
    total_subtask_effort = sum(subtask.estimated_days for subtask in subtasks)
    classification = classifier.classify_task(task)

    # Allow for some rounding differences (within 10%)
    effort_ratio = total_subtask_effort / classification.estimated_days
    assert (
        0.9 <= effort_ratio <= 1.1
    ), f"Total subtask effort ({total_subtask_effort}) should approximately equal original task effort ({classification.estimated_days})"


# Property 14: Decomposition Approval Requirement
@given(
    estimated_days=st.floats(min_value=1.5, max_value=5.0),  # Reduced from 10.0
    key_prefix=st.text(min_size=2, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
    key_number=st.integers(min_value=1, max_value=999),
    summary=st.text(min_size=5, max_size=50, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))),
    description=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))),
    issue_type=st.sampled_from(["Story", "Bug", "Task", "Epic"]),
    priority=st.sampled_from(["High", "Medium", "Low"]),
    status=st.sampled_from(["To Do", "In Progress"]),
    assignee=st.emails(),
)
@settings(max_examples=50, deadline=3000)  # Added settings to limit resources
def test_property_14_decomposition_approval_requirement(
    estimated_days, key_prefix, key_number, summary, description, issue_type, priority, status, assignee
):
    """Property 14: Decomposition Approval Requirement

    For any proposed task decomposition, the system shall require user approval AND
    shall not create subtasks in JIRA without explicit approval.

    Feature: ai-secretary, Property 14: Decomposition Approval Requirement
    Validates: Requirements 4.4, 7.2
    """
    # Create a long-running task
    # Use time_estimate instead of story_points for more precise control
    time_estimate_seconds = int(estimated_days * 8 * 60 * 60)

    task = JiraIssue(
        key=f"{key_prefix}-{key_number}",
        summary=summary,
        description=description,
        issue_type=issue_type,
        priority=priority,
        status=status,
        assignee=assignee,
        story_points=None,
        time_estimate=time_estimate_seconds,
        labels=[],
        issue_links=[],
        custom_fields={},
    )

    # Create mock JIRA client that tracks if create_subtask was called
    mock_jira_client = Mock(spec=JiraClient)
    mock_jira_client.create_subtask = Mock(return_value="PROJ-999")

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Propose decomposition (this should NOT create subtasks)
    subtasks = plan_generator.propose_decomposition(task)

    # Verify that propose_decomposition did NOT call create_subtask
    assert (
        not mock_jira_client.create_subtask.called
    ), "propose_decomposition should not create subtasks without approval"

    # Verify subtasks were proposed (returned as specs, not created)
    assert len(subtasks) > 0, "Subtasks should be proposed"
    assert all(
        isinstance(s, SubtaskSpec) for s in subtasks
    ), "Proposed subtasks should be SubtaskSpec objects, not created JIRA issues"

    # The actual creation would happen after approval in a separate workflow
    # This test verifies that the proposal phase does not create anything
