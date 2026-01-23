# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for markdown output validation.

Feature: ai-secretary
"""

import markdown
from datetime import date
from hypothesis import given, strategies as st
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
    IssueLink,
)


# Custom strategies for generating test data
@st.composite
def issue_link_strategy(draw):
    """Generate random IssueLink objects."""
    link_types = ["blocks", "is blocked by", "relates to", "duplicates"]
    # Generate JIRA-style keys like PROJ-123
    project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    target_key = f"{project}-{number}"
    
    return IssueLink(
        link_type=draw(st.sampled_from(link_types)),
        target_key=target_key,
        target_summary=draw(st.text(min_size=5, max_size=100)),
    )


@st.composite
def jira_issue_strategy(draw):
    """Generate random JiraIssue objects."""
    issue_types = ["Story", "Bug", "Task", "Epic", "Sub-task"]
    priorities = ["Blocker", "High", "Medium", "Low"]
    statuses = ["To Do", "In Progress", "Blocked", "Done"]
    
    # Generate JIRA-style keys like PROJ-123
    project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    key = f"{project}-{number}"
    
    return JiraIssue(
        key=key,
        summary=draw(st.text(min_size=5, max_size=200)),
        description=draw(st.text(min_size=0, max_size=500)),
        issue_type=draw(st.sampled_from(issue_types)),
        priority=draw(st.sampled_from(priorities)),
        status=draw(st.sampled_from(statuses)),
        assignee=draw(st.emails()),
        story_points=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=13))),
        time_estimate=draw(st.one_of(st.none(), st.integers(min_value=3600, max_value=86400))),
        labels=draw(st.lists(st.text(min_size=1, max_size=20), max_size=5)),
        issue_links=draw(st.lists(issue_link_strategy(), max_size=3)),
        custom_fields=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(min_size=0, max_size=50), max_size=3)),
    )


@st.composite
def task_classification_strategy(draw):
    """Generate random TaskClassification objects."""
    issue = draw(jira_issue_strategy())
    category = draw(st.sampled_from(list(TaskCategory)))
    
    # Determine eligibility based on category
    is_priority_eligible = category == TaskCategory.PRIORITY_ELIGIBLE
    has_dependencies = category == TaskCategory.DEPENDENT
    
    # Estimated days should be <= 1.0 for priority eligible tasks
    if is_priority_eligible:
        estimated_days = draw(st.floats(min_value=0.1, max_value=1.0))
    else:
        estimated_days = draw(st.floats(min_value=0.1, max_value=10.0))
    
    blocking_reason = None
    if category == TaskCategory.BLOCKING:
        blocking_reason = draw(st.text(min_size=10, max_size=100))
    
    return TaskClassification(
        task=issue,
        category=category,
        is_priority_eligible=is_priority_eligible,
        has_dependencies=has_dependencies,
        estimated_days=estimated_days,
        blocking_reason=blocking_reason,
    )


@st.composite
def admin_block_strategy(draw):
    """Generate random AdminBlock objects."""
    # Generate 0-5 administrative tasks
    num_tasks = draw(st.integers(min_value=0, max_value=5))
    tasks = []
    for _ in range(num_tasks):
        issue = draw(jira_issue_strategy())
        classification = TaskClassification(
            task=issue,
            category=TaskCategory.ADMINISTRATIVE,
            is_priority_eligible=False,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.1, max_value=0.5)),
        )
        tasks.append(classification)
    
    time_allocation = draw(st.integers(min_value=0, max_value=90))
    hour = draw(st.integers(min_value=13, max_value=17))
    start_min = draw(st.integers(min_value=0, max_value=30))
    end_hour = hour + 1 if start_min + time_allocation <= 60 else hour + 2
    end_min = (start_min + time_allocation) % 60
    scheduled_time = f"{hour:02d}:{start_min:02d}-{end_hour:02d}:{end_min:02d}"
    
    return AdminBlock(
        tasks=tasks,
        time_allocation_minutes=time_allocation,
        scheduled_time=scheduled_time,
    )


@st.composite
def daily_plan_strategy(draw):
    """Generate random DailyPlan objects."""
    # Generate 0-3 priority tasks
    num_priorities = draw(st.integers(min_value=0, max_value=3))
    priorities = []
    for _ in range(num_priorities):
        issue = draw(jira_issue_strategy())
        classification = TaskClassification(
            task=issue,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.1, max_value=1.0)),
        )
        priorities.append(classification)
    
    admin_block = draw(admin_block_strategy())
    
    # Generate 0-10 other tasks
    num_other = draw(st.integers(min_value=0, max_value=10))
    other_tasks = [draw(task_classification_strategy()) for _ in range(num_other)]
    
    previous_closure_rate = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0)))
    
    plan_date = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    
    return DailyPlan(
        date=plan_date,
        priorities=priorities,
        admin_block=admin_block,
        other_tasks=other_tasks,
        previous_closure_rate=previous_closure_rate,
    )


# Property 22: Markdown Validity
@given(daily_plan_strategy())
def test_property_22_markdown_validity(plan: DailyPlan):
    """Property 22: Markdown Validity
    
    For any generated daily plan, the markdown output shall be valid and parseable
    by standard markdown processors.
    
    Feature: ai-secretary, Property 22: Markdown Validity
    Validates: Requirements 9.1, 9.5
    """
    # Generate markdown output
    markdown_output = plan.to_markdown()
    
    # Verify output is a non-empty string
    assert isinstance(markdown_output, str)
    assert len(markdown_output) > 0
    
    # Verify markdown is parseable by standard markdown processor
    try:
        md = markdown.Markdown()
        html_output = md.convert(markdown_output)
        
        # Verify HTML was generated
        assert isinstance(html_output, str)
        assert len(html_output) > 0
        
    except Exception as e:
        raise AssertionError(f"Markdown parsing failed: {e}")
    
    # Verify basic structure elements are present
    assert "# Daily Plan" in markdown_output
    assert "## Today's Priorities" in markdown_output


# Property 23: Task Information Completeness
@given(daily_plan_strategy())
def test_property_23_task_information_completeness(plan: DailyPlan):
    """Property 23: Task Information Completeness
    
    For any task included in the plan output, the markdown shall contain task ID,
    title, estimated effort, and dependency status.
    
    Feature: ai-secretary, Property 23: Task Information Completeness
    Validates: Requirements 9.2
    """
    markdown_output = plan.to_markdown()
    
    # Check all priority tasks have required information
    for classification in plan.priorities:
        task = classification.task
        
        # Verify task ID is present
        assert task.key in markdown_output, f"Task ID {task.key} not found in markdown output"
        
        # Verify task title/summary is present
        assert task.summary in markdown_output, f"Task summary '{task.summary}' not found in markdown output"
        
        # Verify effort information is present
        # Effort should be displayed in hours (days * 8)
        effort_hours = classification.estimated_days * 8
        assert "Effort:" in markdown_output, "Effort label not found in markdown output"
        assert f"{effort_hours:.1f}" in markdown_output, f"Effort value {effort_hours:.1f} not found in markdown output"
        
        # Verify task type is present
        assert task.issue_type in markdown_output, f"Task type {task.issue_type} not found in markdown output"
    
    # Check all admin block tasks have required information
    for classification in plan.admin_block.tasks:
        task = classification.task
        
        # Verify task ID is present
        assert task.key in markdown_output, f"Admin task ID {task.key} not found in markdown output"
        
        # Verify task title/summary is present
        assert task.summary in markdown_output, f"Admin task summary '{task.summary}' not found in markdown output"
    
    # Check all other tasks have required information and dependency status
    for classification in plan.other_tasks:
        task = classification.task
        
        # Verify task ID is present
        assert task.key in markdown_output, f"Other task ID {task.key} not found in markdown output"
        
        # Verify task title/summary is present
        assert task.summary in markdown_output, f"Other task summary '{task.summary}' not found in markdown output"
        
        # Verify dependency status is indicated for tasks with dependencies
        if classification.has_dependencies:
            # Find the line with this task
            for line in markdown_output.split('\n'):
                if task.key in line:
                    assert "blocked by dependencies" in line, \
                        f"Task {task.key} has dependencies but no dependency indicator found"
                    break
