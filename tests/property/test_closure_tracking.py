# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for closure tracking.

Feature: ai-secretary
"""

from unittest.mock import Mock
from datetime import date, timedelta
from hypothesis import given, strategies as st
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
)
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator


# Custom strategies for generating test data
@st.composite
def jira_issue_strategy(draw):
    """Generate random JiraIssue objects."""
    # Generate JIRA-style keys like PROJ-123
    project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    key = f"{project}-{number}"
    
    return JiraIssue(
        key=key,
        summary=draw(st.text(min_size=5, max_size=200)),
        description=draw(st.text(min_size=0, max_size=500)),
        issue_type=draw(st.sampled_from(["Story", "Bug", "Task"])),
        priority=draw(st.sampled_from(["High", "Medium", "Low"])),
        status=draw(st.sampled_from(["To Do", "In Progress", "Done"])),
        assignee=draw(st.emails()),
        story_points=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=8))),
        time_estimate=None,
        labels=[],
        issue_links=[],
        custom_fields={},
    )


@st.composite
def priority_task_list_strategy(draw):
    """Generate a list of priority-eligible tasks."""
    size = draw(st.integers(min_value=1, max_value=3))
    tasks = []
    used_keys = set()
    
    for i in range(size):
        task = draw(jira_issue_strategy())
        
        # Ensure unique key
        original_key = task.key
        counter = 0
        while task.key in used_keys:
            counter += 1
            task.key = f"{original_key}-{counter}"
        
        used_keys.add(task.key)
        tasks.append(task)
    
    return tasks


@st.composite
def completion_set_strategy(draw, tasks):
    """Generate a random completion set from a list of tasks."""
    # Randomly decide which tasks are completed
    completed_keys = set()
    
    for task in tasks:
        if draw(st.booleans()):
            completed_keys.add(task.key)
    
    return completed_keys


# Property 30: Closure Rate Calculation
@given(st.data())
def test_property_30_closure_rate_calculation(data):
    """Property 30: Closure Rate Calculation
    
    For any set of priority tasks and their completion statuses, the calculated closure
    rate shall equal (number of completed tasks) / (total number of priority tasks).
    
    Feature: ai-secretary, Property 30: Closure Rate Calculation
    Validates: Requirements 12.2
    """
    # Generate priority tasks
    priority_tasks_raw = data.draw(priority_task_list_strategy())
    
    # Create mock JIRA client
    mock_jira_client = Mock()
    
    # Generate completion set
    completed_keys = data.draw(completion_set_strategy(priority_tasks_raw))
    
    # Active tasks are those NOT completed
    active_tasks = [task for task in priority_tasks_raw if task.key not in completed_keys]
    mock_jira_client.fetch_active_tasks.return_value = active_tasks
    
    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)
    
    # Classify priority tasks
    priority_classifications = [classifier.classify_task(task) for task in priority_tasks_raw]
    
    # Calculate closure rate
    plan_date = date.today()
    closure_rate = plan_generator.calculate_closure_rate(plan_date, priority_classifications)
    
    # Verify closure rate formula
    total_priorities = len(priority_tasks_raw)
    completed_count = len(completed_keys)
    expected_rate = completed_count / total_priorities if total_priorities > 0 else 0.0
    
    assert abs(closure_rate - expected_rate) < 0.001, \
        f"Closure rate {closure_rate} does not match expected {expected_rate} " \
        f"(completed: {completed_count}, total: {total_priorities})"
    
    # Verify closure rate is in valid range
    assert 0.0 <= closure_rate <= 1.0, \
        f"Closure rate {closure_rate} is outside valid range [0.0, 1.0]"



# Property 31: Closure Rate Display
@given(st.floats(min_value=0.0, max_value=1.0))
def test_property_31_closure_rate_display(previous_closure_rate):
    """Property 31: Closure Rate Display
    
    For any daily plan generated after the first day, the markdown output shall display
    the previous day's closure rate.
    
    Feature: ai-secretary, Property 31: Closure Rate Display
    Validates: Requirements 12.3
    """
    # Create mock JIRA client with some tasks
    mock_jira_client = Mock()
    
    # Generate some priority-eligible tasks
    tasks = [
        JiraIssue(
            key=f"PROJ-{i}",
            summary=f"Task {i}",
            description="Test task",
            issue_type="Story",
            priority="High",
            status="To Do",
            assignee="test@example.com",
            story_points=1,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        )
        for i in range(3)
    ]
    
    mock_jira_client.fetch_active_tasks.return_value = tasks
    
    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)
    
    # Generate daily plan with previous closure rate
    plan = plan_generator.generate_daily_plan(previous_closure_rate=previous_closure_rate)
    
    # Verify plan has the previous closure rate set
    assert plan.previous_closure_rate == previous_closure_rate, \
        f"Plan's previous_closure_rate {plan.previous_closure_rate} does not match provided {previous_closure_rate}"
    
    # Generate markdown output
    markdown = plan.to_markdown()
    
    # Verify markdown contains "Previous Day" section
    assert "## Previous Day" in markdown, \
        "Markdown output does not contain 'Previous Day' section"
    
    # Verify markdown contains "Closure Rate"
    assert "Closure Rate:" in markdown, \
        "Markdown output does not contain 'Closure Rate:' text"
    
    # Verify markdown contains percentage
    percentage = int(previous_closure_rate * 100)
    assert f"({percentage}%)" in markdown, \
        f"Markdown output does not contain expected percentage ({percentage}%)"
    
    # Verify markdown contains task completion information (X/Y tasks completed)
    assert "tasks completed" in markdown, \
        "Markdown output does not contain 'tasks completed' text"


@given(st.data())
def test_property_31_no_closure_rate_on_first_day(data):
    """Property 31: Closure Rate Display (edge case)
    
    For the first day (no previous closure rate), the markdown output should not
    display a previous day section.
    
    Feature: ai-secretary, Property 31: Closure Rate Display
    Validates: Requirements 12.3
    """
    # Create mock JIRA client with some tasks
    mock_jira_client = Mock()
    
    # Generate some priority-eligible tasks
    tasks = data.draw(st.lists(
        st.builds(
            JiraIssue,
            key=st.text(min_size=5, max_size=20),
            summary=st.text(min_size=5, max_size=100),
            description=st.text(min_size=0, max_size=200),
            issue_type=st.sampled_from(["Story", "Bug", "Task"]),
            priority=st.sampled_from(["High", "Medium", "Low"]),
            status=st.sampled_from(["To Do", "In Progress"]),
            assignee=st.emails(),
            story_points=st.one_of(st.none(), st.integers(min_value=1, max_value=5)),
            time_estimate=st.none(),
            labels=st.just([]),
            issue_links=st.just([]),
            custom_fields=st.just({}),
        ),
        min_size=0,
        max_size=10
    ))
    
    mock_jira_client.fetch_active_tasks.return_value = tasks
    
    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)
    
    # Generate daily plan without previous closure rate (first day)
    plan = plan_generator.generate_daily_plan(previous_closure_rate=None)
    
    # Generate markdown output
    markdown = plan.to_markdown()
    
    # If no previous closure rate, markdown should not contain "Previous Day" section
    if plan.previous_closure_rate is None:
        assert "## Previous Day" not in markdown, \
            "Markdown output contains 'Previous Day' section when it should not (first day)"
        assert "Closure Rate:" not in markdown, \
            "Markdown output contains 'Closure Rate:' when it should not (first day)"
