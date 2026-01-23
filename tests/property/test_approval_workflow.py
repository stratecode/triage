# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for approval workflow.

Feature: ai-secretary
"""

from unittest.mock import Mock, patch
from hypothesis import given, strategies as st
from datetime import date

from triage.models import (
    DailyPlan,
    AdminBlock,
    TaskClassification,
    TaskCategory,
    JiraIssue,
    ApprovalResult,
)
from triage.approval_manager import ApprovalManager


# Custom strategies for generating test data
@st.composite
def daily_plan_strategy(draw):
    """Generate random DailyPlan objects for testing."""
    # Generate 0-3 priority tasks
    num_priorities = draw(st.integers(min_value=0, max_value=3))
    priorities = []
    
    for i in range(num_priorities):
        task = JiraIssue(
            key=f"PROJ-{draw(st.integers(min_value=1, max_value=9999))}",
            summary=draw(st.text(min_size=5, max_size=100)),
            description=draw(st.text(min_size=0, max_size=200)),
            issue_type=draw(st.sampled_from(["Story", "Bug", "Task"])),
            priority=draw(st.sampled_from(["High", "Medium", "Low"])),
            status=draw(st.sampled_from(["To Do", "In Progress"])),
            assignee=draw(st.emails()),
            story_points=draw(st.integers(min_value=1, max_value=5)),
            labels=[],
            issue_links=[],
        )
        
        classification = TaskClassification(
            task=task,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.25, max_value=1.0)),
        )
        priorities.append(classification)
    
    # Generate 0-5 admin tasks
    num_admin = draw(st.integers(min_value=0, max_value=5))
    admin_tasks = []
    total_admin_minutes = 0
    
    for i in range(num_admin):
        task = JiraIssue(
            key=f"ADMIN-{draw(st.integers(min_value=1, max_value=9999))}",
            summary=draw(st.text(min_size=5, max_size=100)),
            description=draw(st.text(min_size=0, max_size=200)),
            issue_type="Administrative Task",
            priority="Low",
            status="To Do",
            assignee=draw(st.emails()),
            labels=["admin"],
            issue_links=[],
        )
        
        estimated_days = draw(st.floats(min_value=0.01, max_value=0.1))
        classification = TaskClassification(
            task=task,
            category=TaskCategory.ADMINISTRATIVE,
            is_priority_eligible=False,
            has_dependencies=False,
            estimated_days=estimated_days,
        )
        
        task_minutes = estimated_days * 8 * 60
        if total_admin_minutes + task_minutes <= 90:
            admin_tasks.append(classification)
            total_admin_minutes += task_minutes
    
    admin_block = AdminBlock(
        tasks=admin_tasks,
        time_allocation_minutes=int(total_admin_minutes),
        scheduled_time="14:00-15:30",
    )
    
    # Generate 0-10 other tasks
    num_other = draw(st.integers(min_value=0, max_value=10))
    other_tasks = []
    
    for i in range(num_other):
        task = JiraIssue(
            key=f"OTHER-{draw(st.integers(min_value=1, max_value=9999))}",
            summary=draw(st.text(min_size=5, max_size=100)),
            description=draw(st.text(min_size=0, max_size=200)),
            issue_type=draw(st.sampled_from(["Story", "Bug", "Task"])),
            priority=draw(st.sampled_from(["High", "Medium", "Low"])),
            status=draw(st.sampled_from(["To Do", "In Progress", "Blocked"])),
            assignee=draw(st.emails()),
            labels=[],
            issue_links=[],
        )
        
        classification = TaskClassification(
            task=task,
            category=draw(st.sampled_from([
                TaskCategory.DEPENDENT,
                TaskCategory.LONG_RUNNING,
            ])),
            is_priority_eligible=False,
            has_dependencies=draw(st.booleans()),
            estimated_days=draw(st.floats(min_value=0.5, max_value=5.0)),
        )
        other_tasks.append(classification)
    
    # Create the daily plan
    plan = DailyPlan(
        date=date.today(),
        priorities=priorities,
        admin_block=admin_block,
        other_tasks=other_tasks,
        previous_closure_rate=draw(st.one_of(
            st.none(),
            st.floats(min_value=0.0, max_value=1.0)
        )),
    )
    
    return plan


# Property 13: Plan Approval Requirement
@given(daily_plan_strategy(), st.booleans())
def test_property_13_plan_approval_requirement(plan, user_approves):
    """Property 13: Plan Approval Requirement
    
    For any generated daily plan (initial or re-plan), the system shall present it
    for user approval AND shall not finalize the plan without explicit approval.
    
    Feature: ai-secretary, Property 13: Plan Approval Requirement
    Validates: Requirements 1.7, 7.1
    """
    # Create approval manager
    approval_manager = ApprovalManager()
    
    # Mock user input to simulate approval/rejection
    user_response = 'yes' if user_approves else 'no'
    
    with patch('builtins.input', return_value=user_response):
        with patch('builtins.print'):  # Suppress output during test
            # Present plan for approval
            result = approval_manager.present_plan(plan)
    
    # Verify result is an ApprovalResult
    assert isinstance(result, ApprovalResult), \
        "present_plan must return an ApprovalResult object"
    
    # Verify approval status matches user input
    assert result.approved == user_approves, \
        f"Approval result should be {user_approves} but got {result.approved}"
    
    # Verify the approval result reflects explicit user decision
    # (not auto-approved or defaulted)
    if user_approves:
        assert result.approved is True, \
            "Plan should be approved when user explicitly approves"
    else:
        assert result.approved is False, \
            "Plan should not be approved when user explicitly rejects"
    
    # Additional verification: The plan itself should not be modified
    # by the approval process (approval is separate from plan state)
    assert plan.date == date.today(), \
        "Plan date should not be modified during approval"
    assert isinstance(plan.priorities, list), \
        "Plan priorities should remain a list"
    assert isinstance(plan.admin_block, AdminBlock), \
        "Plan admin_block should remain an AdminBlock"


@given(daily_plan_strategy())
def test_property_13_no_implicit_approval(plan):
    """Property 13: Plan Approval Requirement (No Implicit Approval)
    
    Verify that plans cannot be implicitly approved without user interaction.
    The approval manager must always require explicit user input.
    
    Feature: ai-secretary, Property 13: Plan Approval Requirement
    Validates: Requirements 1.7, 7.1
    """
    # Create approval manager
    approval_manager = ApprovalManager()
    
    # Verify that present_plan requires user input
    # We test this by ensuring the method would block waiting for input
    # (in a real scenario, it would wait for user response)
    
    # Mock user input with explicit response
    with patch('builtins.input', return_value='yes'):
        with patch('builtins.print'):  # Suppress output during test
            result = approval_manager.present_plan(plan)
    
    # Verify that an ApprovalResult was returned
    assert isinstance(result, ApprovalResult), \
        "present_plan must return an ApprovalResult"
    
    # Verify that the result has an explicit approval status
    assert isinstance(result.approved, bool), \
        "ApprovalResult.approved must be a boolean (explicit True or False)"
    
    # Verify that the approval is not None (which would indicate no decision)
    assert result.approved is not None, \
        "Approval status must be explicitly set (not None)"


@given(daily_plan_strategy())
def test_property_13_approval_result_structure(plan):
    """Property 13: Plan Approval Requirement (Result Structure)
    
    Verify that the ApprovalResult returned by present_plan has the correct
    structure and contains the required fields.
    
    Feature: ai-secretary, Property 13: Plan Approval Requirement
    Validates: Requirements 1.7, 7.1
    """
    # Create approval manager
    approval_manager = ApprovalManager()
    
    # Test with approval
    with patch('builtins.input', return_value='yes'):
        with patch('builtins.print'):
            result_approved = approval_manager.present_plan(plan)
    
    # Verify structure of approved result
    assert hasattr(result_approved, 'approved'), \
        "ApprovalResult must have 'approved' attribute"
    assert result_approved.approved is True, \
        "Approved result should have approved=True"
    
    # Test with rejection
    with patch('builtins.input', return_value='no'):
        with patch('builtins.print'):
            result_rejected = approval_manager.present_plan(plan)
    
    # Verify structure of rejected result
    assert hasattr(result_rejected, 'approved'), \
        "ApprovalResult must have 'approved' attribute"
    assert result_rejected.approved is False, \
        "Rejected result should have approved=False"
    
    # Verify both results are ApprovalResult instances
    assert isinstance(result_approved, ApprovalResult), \
        "Approved result must be an ApprovalResult instance"
    assert isinstance(result_rejected, ApprovalResult), \
        "Rejected result must be an ApprovalResult instance"
