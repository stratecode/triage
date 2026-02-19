# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for re-planning flow.

Feature: ai-secretary
"""

from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.models import (
    DailyPlan,
    IssueLink,
    JiraIssue,
)
from triage.plan_generator import PlanGenerator
from triage.task_classifier import TaskClassifier


# Custom strategies for generating test data
@st.composite
def jira_issue_strategy(draw, has_dependencies=None, estimated_days=None, is_admin=None, is_blocking=None):
    """Generate random JiraIssue objects with optional constraints."""
    issue_types = ["Story", "Bug", "Task", "Epic", "Sub-task"]
    priorities = ["High", "Medium", "Low"]
    statuses = ["To Do", "In Progress", "Blocked", "Done"]

    # Override with admin types if needed
    if is_admin:
        issue_types = ["Administrative Task", "Admin", "Approval"]

    # Override with blocking priority if needed
    if is_blocking:
        priorities = ["Blocker"]

    # Generate JIRA-style keys like PROJ-123 (limited alphabet to prevent memory issues)
    project = draw(st.text(min_size=2, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)))
    number = draw(st.integers(min_value=1, max_value=999))
    key = f"{project}-{number}"

    # Generate issue links based on has_dependencies (limited to prevent memory issues)
    issue_links = []
    if has_dependencies:
        blocking_link_types = ["is blocked by", "depends on", "blocked by"]
        num_links = draw(st.integers(min_value=1, max_value=2))  # Reduced from 3
        for _ in range(num_links):
            target_project = draw(
                st.text(min_size=2, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90))
            )
            target_number = draw(st.integers(min_value=1, max_value=999))
            target_key = f"{target_project}-{target_number}"
            issue_links.append(
                IssueLink(
                    link_type=draw(st.sampled_from(blocking_link_types)),
                    target_key=target_key,
                    target_summary=draw(
                        st.text(min_size=5, max_size=30, alphabet=st.characters(blacklist_categories=("Cs", "Cc")))
                    ),
                )
            )
    elif has_dependencies is False:
        # Explicitly no dependencies
        issue_links = []
    else:
        # Random (limited)
        issue_links = draw(
            st.lists(
                st.builds(
                    IssueLink,
                    link_type=st.sampled_from(["relates to", "duplicates"]),
                    target_key=st.text(
                        min_size=5, max_size=15, alphabet=st.characters(min_codepoint=65, max_codepoint=90)
                    ),
                    target_summary=st.text(
                        min_size=5, max_size=30, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))
                    ),
                ),
                max_size=1,  # Reduced from 2
            )
        )

    # Generate labels based on is_admin (limited to prevent memory issues)
    labels = []
    if is_admin:
        admin_labels = ["admin", "administrative", "email", "report", "approval"]
        labels = [draw(st.sampled_from(admin_labels))]
    elif is_admin is False:
        # Explicitly no admin labels (limited)
        labels = draw(
            st.lists(
                st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
                max_size=2,
            )
        )
    else:
        # Random (limited)
        labels = draw(
            st.lists(
                st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
                max_size=2,
            )
        )

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
        labels=labels,
        issue_links=issue_links,
        custom_fields={},
    )


@st.composite
def task_list_strategy(draw, min_size=0, max_size=10):  # Reduced from 20
    """Generate a list of random JiraIssue objects with unique keys."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    tasks = []
    used_keys = set()

    for i in range(size):
        # Randomly decide task characteristics
        has_deps = draw(st.booleans())
        is_admin = draw(st.booleans())
        is_blocking = draw(st.booleans())

        # Generate estimated days
        if draw(st.booleans()):
            # Some tasks are short (priority eligible)
            estimated_days = draw(st.floats(min_value=0.25, max_value=1.0))
        else:
            # Some tasks are long
            estimated_days = draw(st.floats(min_value=1.5, max_value=5.0))

        task = draw(
            jira_issue_strategy(
                has_dependencies=has_deps if not is_admin else False,
                estimated_days=estimated_days,
                is_admin=is_admin,
                is_blocking=is_blocking,
            )
        )

        # Ensure unique key with limited retries to prevent infinite loops
        original_key = task.key
        counter = 0
        max_retries = 100
        while task.key in used_keys and counter < max_retries:
            counter += 1
            task.key = f"{original_key}-{counter}"

        # Skip if we couldn't generate a unique key
        if task.key in used_keys:
            continue

        used_keys.add(task.key)
        tasks.append(task)

    return tasks


@st.composite
def daily_plan_strategy(draw):
    """Generate a random DailyPlan for testing."""
    # Generate some tasks (reduced size)
    tasks = draw(task_list_strategy(min_size=3, max_size=8))  # Reduced from 15

    # Create mock JIRA client
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = tasks

    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Generate a plan
    plan = plan_generator.generate_daily_plan()

    return plan, tasks


# Property 9: Re-planning Trigger
@given(daily_plan_strategy())
@settings(max_examples=30, deadline=5000)  # Added settings to limit resources
def test_property_9_replanning_trigger(plan_and_tasks):
    """Property 9: Re-planning Trigger

    For any detected blocking task, the system shall mark the current plan as interrupted
    AND initiate the re-planning flow.

    Feature: ai-secretary, Property 9: Re-planning Trigger
    Validates: Requirements 3.2, 3.3
    """
    current_plan, existing_tasks = plan_and_tasks

    # Generate a blocking task
    blocking_task = JiraIssue(
        key="BLOCK-999",
        summary="Critical blocking issue",
        description="This is a blocking task that requires immediate attention",
        issue_type="Bug",
        priority="Blocker",
        status="To Do",
        assignee="user@example.com",
        story_points=1,
        time_estimate=None,
        labels=[],
        issue_links=[],
        custom_fields={},
    )

    # Create mock JIRA client that returns existing tasks plus blocking task
    all_tasks = existing_tasks + [blocking_task]
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = all_tasks

    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Verify that generate_replan method exists and can be called
    assert hasattr(
        plan_generator, "generate_replan"
    ), "PlanGenerator must have generate_replan method for re-planning flow"

    # Call generate_replan with the blocking task and current plan
    new_plan = plan_generator.generate_replan(blocking_task, current_plan)

    # Verify a new plan was generated
    assert new_plan is not None, "Re-planning must generate a new plan"
    assert isinstance(new_plan, DailyPlan), "Re-planning must return a DailyPlan object"

    # Verify the new plan is different from the current plan
    # (at least one priority should be different or the blocking task should be included)
    new_priority_keys = {c.task.key for c in new_plan.priorities}
    current_priority_keys = {c.task.key for c in current_plan.priorities}

    # The new plan should either include the blocking task or have different priorities
    assert (
        blocking_task.key in new_priority_keys or new_priority_keys != current_priority_keys
    ), "Re-planning must produce a different plan than the current plan"


# Property 10: Blocking Task Inclusion
@given(daily_plan_strategy())
@settings(max_examples=30, deadline=5000)  # Added settings to limit resources
def test_property_10_blocking_task_inclusion(plan_and_tasks):
    """Property 10: Blocking Task Inclusion

    For any re-plan generated due to a blocking task, the new plan shall include that
    blocking task in the priority list.

    Feature: ai-secretary, Property 10: Blocking Task Inclusion
    Validates: Requirements 3.4
    """
    current_plan, existing_tasks = plan_and_tasks

    # Generate a blocking task
    blocking_task = JiraIssue(
        key="BLOCK-888",
        summary="Urgent blocking issue",
        description="This blocking task must be included in the new plan",
        issue_type="Bug",
        priority="Blocker",
        status="To Do",
        assignee="user@example.com",
        story_points=1,
        time_estimate=None,
        labels=[],
        issue_links=[],
        custom_fields={},
    )

    # Create mock JIRA client that returns existing tasks plus blocking task
    all_tasks = existing_tasks + [blocking_task]
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = all_tasks

    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Generate re-plan with the blocking task
    new_plan = plan_generator.generate_replan(blocking_task, current_plan)

    # Verify the blocking task is in the new plan's priorities
    new_priority_keys = {c.task.key for c in new_plan.priorities}

    assert (
        blocking_task.key in new_priority_keys
    ), f"Blocking task {blocking_task.key} must be included in the re-plan's priorities"

    # Verify the blocking task is the first priority (highest priority)
    assert (
        new_plan.priorities[0].task.key == blocking_task.key
    ), f"Blocking task {blocking_task.key} should be the first priority in the re-plan"

    # Verify the plan still respects the max 3 priorities constraint
    assert len(new_plan.priorities) <= 3, f"Re-plan has {len(new_plan.priorities)} priorities, but maximum is 3"
