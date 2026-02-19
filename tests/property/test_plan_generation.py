# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for plan generation.

Feature: ai-secretary
"""

from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.models import (
    IssueLink,
    JiraIssue,
    TaskCategory,
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


# Property 1: Priority Count Constraint
@given(task_list_strategy(min_size=0, max_size=15))  # Reduced from 30
@settings(max_examples=50, deadline=3000)  # Added settings to limit resources
def test_property_1_priority_count_constraint(tasks):
    """Property 1: Priority Count Constraint

    For any generated daily plan, the number of priority tasks shall be at most 3.

    Feature: ai-secretary, Property 1: Priority Count Constraint
    Validates: Requirements 1.5, 11.1
    """
    # Create mock JIRA client that returns our test tasks
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = tasks

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Generate daily plan
    plan = plan_generator.generate_daily_plan()

    # Verify priority count constraint
    assert len(plan.priorities) <= 3, f"Plan has {len(plan.priorities)} priorities, but maximum is 3"

    # Verify priorities is a list
    assert isinstance(plan.priorities, list), "Priorities must be a list"


# Property 2: Priority Task Eligibility
@given(task_list_strategy(min_size=0, max_size=15))  # Reduced from 30
@settings(max_examples=50, deadline=3000)  # Added settings to limit resources
def test_property_2_priority_task_eligibility(tasks):
    """Property 2: Priority Task Eligibility

    For any task in the priority list of a daily plan, that task shall have no third-party
    dependencies AND estimated effort of at most 1.0 days AND shall not be categorized as
    administrative.

    Feature: ai-secretary, Property 2: Priority Task Eligibility
    Validates: Requirements 1.3, 1.4, 2.4, 5.1, 10.2, 10.3
    """
    # Create mock JIRA client that returns our test tasks
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = tasks

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Generate daily plan
    plan = plan_generator.generate_daily_plan()

    # Verify each priority task meets eligibility criteria
    for i, classification in enumerate(plan.priorities):
        # Verify no third-party dependencies
        assert (
            not classification.has_dependencies
        ), f"Priority task {i+1} ({classification.task.key}) has dependencies but should not"

        # Verify estimated effort <= 1.0 days
        assert (
            classification.estimated_days <= 1.0
        ), f"Priority task {i+1} ({classification.task.key}) has effort {classification.estimated_days} days, but maximum is 1.0"

        # Verify not categorized as administrative
        assert (
            classification.category != TaskCategory.ADMINISTRATIVE
        ), f"Priority task {i+1} ({classification.task.key}) is categorized as administrative but should not be in priorities"

        # Additional check: verify not blocking (blocking tasks go through re-planning)
        assert (
            classification.category != TaskCategory.BLOCKING
        ), f"Priority task {i+1} ({classification.task.key}) is categorized as blocking but should not be in priorities"


# Property 5: Administrative Task Grouping
@given(task_list_strategy(min_size=0, max_size=15))  # Reduced from 30
@settings(max_examples=50, deadline=3000)  # Added settings to limit resources
def test_property_5_administrative_task_grouping(tasks):
    """Property 5: Administrative Task Grouping

    For any generated daily plan, all tasks categorized as administrative shall appear in
    the admin block AND no administrative task shall appear in the priority list AND the
    admin block time allocation shall not exceed 90 minutes.

    Feature: ai-secretary, Property 5: Administrative Task Grouping
    Validates: Requirements 2.3, 5.1, 5.2, 5.4
    """
    # Create mock JIRA client that returns our test tasks
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = tasks

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Generate daily plan
    plan = plan_generator.generate_daily_plan()

    # Classify all tasks to identify which are administrative
    all_classifications = [classifier.classify_task(task) for task in tasks]
    admin_classifications = [c for c in all_classifications if c.category == TaskCategory.ADMINISTRATIVE]

    # Get keys of tasks in admin block
    admin_block_keys = {c.task.key for c in plan.admin_block.tasks}

    # Get keys of tasks in priorities
    priority_keys = {c.task.key for c in plan.priorities}

    # Verify no administrative task appears in priorities
    for classification in admin_classifications:
        assert (
            classification.task.key not in priority_keys
        ), f"Administrative task {classification.task.key} appears in priorities but should not"

    # Verify all tasks in admin block are administrative
    for classification in plan.admin_block.tasks:
        assert (
            classification.category == TaskCategory.ADMINISTRATIVE
        ), f"Task {classification.task.key} in admin block is not categorized as administrative"

    # Verify admin block time allocation does not exceed 90 minutes
    assert (
        plan.admin_block.time_allocation_minutes <= 90
    ), f"Admin block time allocation is {plan.admin_block.time_allocation_minutes} minutes, but maximum is 90"

    # Verify time allocation is non-negative
    assert (
        plan.admin_block.time_allocation_minutes >= 0
    ), f"Admin block time allocation is negative: {plan.admin_block.time_allocation_minutes}"


# Property 7: Administrative Overflow Handling
@st.composite
def admin_heavy_task_list_strategy(draw):
    """Generate a list with >90 minutes of administrative work."""
    # Generate 5-10 administrative tasks (reduced from 5-15)
    num_admin_tasks = draw(st.integers(min_value=5, max_value=10))
    tasks = []
    used_keys = set()

    for i in range(num_admin_tasks):
        # Each admin task takes 15-30 minutes (0.03-0.06 days at 8 hours/day)
        estimated_days = draw(st.floats(min_value=0.03, max_value=0.06))

        task = draw(
            jira_issue_strategy(has_dependencies=False, estimated_days=estimated_days, is_admin=True, is_blocking=False)
        )

        # Ensure unique key with limited retries
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

    # Add some non-admin tasks too (reduced from 0-10 to 0-5)
    num_other_tasks = draw(st.integers(min_value=0, max_value=5))
    for i in range(num_other_tasks):
        has_deps = draw(st.booleans())
        estimated_days = draw(st.floats(min_value=0.25, max_value=2.0))

        task = draw(
            jira_issue_strategy(
                has_dependencies=has_deps, estimated_days=estimated_days, is_admin=False, is_blocking=False
            )
        )

        # Ensure unique key with limited retries
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


@given(admin_heavy_task_list_strategy())
@settings(max_examples=30, deadline=5000)  # Added settings to limit resources
def test_property_7_administrative_overflow_handling(tasks):
    """Property 7: Administrative Overflow Handling

    For any set of administrative tasks where total estimated time exceeds 90 minutes,
    some tasks shall be deferred (not included in the current plan's admin block).

    Feature: ai-secretary, Property 7: Administrative Overflow Handling
    Validates: Requirements 5.5
    """
    # Create mock JIRA client that returns our test tasks
    mock_jira_client = Mock()
    mock_jira_client.fetch_active_tasks.return_value = tasks

    # Create real classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)

    # Generate daily plan
    plan = plan_generator.generate_daily_plan()

    # Classify all tasks to identify administrative ones
    all_classifications = [classifier.classify_task(task) for task in tasks]
    admin_classifications = [c for c in all_classifications if c.category == TaskCategory.ADMINISTRATIVE]

    # Calculate total admin time available
    total_admin_minutes = sum(c.estimated_days * 8 * 60 for c in admin_classifications)

    # If total admin time exceeds 90 minutes, verify some tasks are deferred
    if total_admin_minutes > 90:
        # Get keys of tasks in admin block
        admin_block_keys = {c.task.key for c in plan.admin_block.tasks}

        # Get keys of all admin tasks
        all_admin_keys = {c.task.key for c in admin_classifications}

        # Verify some admin tasks are NOT in the admin block (deferred)
        deferred_admin_keys = all_admin_keys - admin_block_keys
        assert (
            len(deferred_admin_keys) > 0
        ), f"Total admin time is {total_admin_minutes:.1f} minutes (>{90}), but no tasks were deferred"

        # Verify admin block does not exceed 90 minutes
        assert (
            plan.admin_block.time_allocation_minutes <= 90
        ), f"Admin block time allocation is {plan.admin_block.time_allocation_minutes} minutes, but maximum is 90"

    # Always verify admin block does not exceed 90 minutes
    assert (
        plan.admin_block.time_allocation_minutes <= 90
    ), f"Admin block time allocation is {plan.admin_block.time_allocation_minutes} minutes, but maximum is 90"
