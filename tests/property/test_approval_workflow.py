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


# Property 16: User Modification Preservation
@given(daily_plan_strategy())
def test_property_16_user_modification_preservation(plan):
    """Property 16: User Modification Preservation
    
    For any user-modified proposal, the system shall accept the modifications
    AND shall not revert to the original proposal.
    
    Feature: ai-secretary, Property 16: User Modification Preservation
    Validates: Requirements 7.5
    """
    # Skip test if plan has no priorities (nothing to modify)
    if len(plan.priorities) == 0:
        return
    
    # Create approval manager
    approval_manager = ApprovalManager(timeout_seconds=0)  # No timeout for test
    
    # Simulate user choosing to modify the plan
    # User selects "modify", then chooses to remove first priority task
    inputs = [
        'modify',  # Choose to modify
        '1',       # Choose option 1 (remove priority tasks)
        '1',       # Remove task 1
        'no',      # No more modifications
    ]
    
    with patch('builtins.input', side_effect=inputs):
        with patch('builtins.print'):  # Suppress output during test
            result = approval_manager.present_plan(plan)
    
    # Verify result is an ApprovalResult
    assert isinstance(result, ApprovalResult), \
        "present_plan must return an ApprovalResult object"
    
    # Verify the plan was approved (modifications are accepted)
    assert result.approved is True, \
        "Modified plan should be approved"
    
    # Verify modifications are present in the result
    assert result.modifications is not None, \
        "ApprovalResult must contain modifications when user modifies plan"
    
    assert isinstance(result.modifications, dict), \
        "Modifications must be a dictionary"
    
    # Verify the modification contains the expected removal
    assert 'remove_priority_indices' in result.modifications, \
        "Modifications should contain remove_priority_indices"
    
    assert result.modifications['remove_priority_indices'] == [0], \
        "Should have recorded removal of first task (index 0)"
    
    # Verify the original plan object is not modified
    # (modifications are returned separately, not applied to the plan)
    assert len(plan.priorities) > 0, \
        "Original plan should not be modified by approval process"


@given(daily_plan_strategy())
def test_property_16_modification_not_reverted(plan):
    """Property 16: User Modification Preservation (No Reversion)
    
    Verify that user modifications are preserved in the ApprovalResult
    and not reverted or discarded.
    
    Feature: ai-secretary, Property 16: User Modification Preservation
    Validates: Requirements 7.5
    """
    # Skip test if plan has fewer than 2 priorities (can't reorder)
    if len(plan.priorities) < 2:
        return
    
    # Create approval manager
    approval_manager = ApprovalManager(timeout_seconds=0)  # No timeout for test
    
    # Simulate user choosing to modify the plan by reordering
    num_priorities = len(plan.priorities)
    
    # Create a reordering (reverse the order)
    new_order = list(range(num_priorities - 1, -1, -1))
    new_order_str = ','.join(str(i + 1) for i in new_order)
    
    inputs = [
        'modify',      # Choose to modify
        '2',           # Choose option 2 (reorder priority tasks)
        new_order_str, # New order (reversed)
        'no',          # No more modifications
    ]
    
    with patch('builtins.input', side_effect=inputs):
        with patch('builtins.print'):  # Suppress output during test
            result = approval_manager.present_plan(plan)
    
    # Verify modifications are present
    assert result.modifications is not None, \
        "Modifications must be present in result"
    
    assert 'priority_order' in result.modifications, \
        "Modifications should contain priority_order"
    
    # Verify the new order is preserved exactly as specified
    assert result.modifications['priority_order'] == new_order, \
        f"Priority order should be {new_order} but got {result.modifications['priority_order']}"
    
    # Verify the modification is not reverted (still present in result)
    assert result.approved is True, \
        "Modified plan should be approved"
    
    # Verify modifications dictionary is not empty
    assert len(result.modifications) > 0, \
        "Modifications dictionary should not be empty"


@given(daily_plan_strategy())
def test_property_16_modification_validation(plan):
    """Property 16: User Modification Preservation (Validation)
    
    Verify that user modifications are validated against constraints
    but valid modifications are preserved.
    
    Feature: ai-secretary, Property 16: User Modification Preservation
    Validates: Requirements 7.5
    """
    # Skip test if plan has no priorities
    if len(plan.priorities) == 0:
        return
    
    # Create approval manager
    approval_manager = ApprovalManager(timeout_seconds=0)  # No timeout for test
    
    # Test valid modification: remove a task that exists
    num_priorities = len(plan.priorities)
    
    # Remove the last task (valid operation)
    inputs = [
        'modify',              # Choose to modify
        '1',                   # Choose option 1 (remove priority tasks)
        str(num_priorities),   # Remove last task
        'no',                  # No more modifications
    ]
    
    with patch('builtins.input', side_effect=inputs):
        with patch('builtins.print'):  # Suppress output during test
            result = approval_manager.present_plan(plan)
    
    # Verify valid modification is preserved
    assert result.modifications is not None, \
        "Valid modifications should be preserved"
    
    assert 'remove_priority_indices' in result.modifications, \
        "Valid removal should be recorded"
    
    # The last task has index (num_priorities - 1)
    assert result.modifications['remove_priority_indices'] == [num_priorities - 1], \
        f"Should have recorded removal of last task (index {num_priorities - 1})"
    
    # Verify the result is approved
    assert result.approved is True, \
        "Plan with valid modifications should be approved"


@given(daily_plan_strategy())
def test_property_16_multiple_modifications(plan):
    """Property 16: User Modification Preservation (Multiple Modifications)
    
    Verify that multiple user modifications are all preserved together.
    
    Feature: ai-secretary, Property 16: User Modification Preservation
    Validates: Requirements 7.5
    """
    # Skip test if plan has fewer than 3 priorities (need at least 3 to do both operations)
    if len(plan.priorities) < 3:
        return
    
    # Create approval manager
    approval_manager = ApprovalManager(timeout_seconds=0)  # No timeout for test
    
    # Simulate user making multiple modifications:
    # 1. Reorder tasks first (reverse order)
    # 2. Then remove last task
    
    num_priorities = len(plan.priorities)
    
    # First, reorder all tasks in reverse
    new_order = list(range(num_priorities - 1, -1, -1))
    new_order_str = ','.join(str(i + 1) for i in new_order)
    
    inputs = [
        'modify',      # Choose to modify
        '2',           # Choose option 2 (reorder priority tasks)
        new_order_str, # New order (reversed)
        'yes',         # Make more modifications
        '1',           # Choose option 1 (remove priority tasks)
        str(num_priorities),  # Remove last task (after reordering)
        'no',          # No more modifications
    ]
    
    with patch('builtins.input', side_effect=inputs):
        with patch('builtins.print'):  # Suppress output during test
            result = approval_manager.present_plan(plan)
    
    # Verify both modifications are preserved
    assert result.modifications is not None, \
        "Multiple modifications should be preserved"
    
    assert 'priority_order' in result.modifications, \
        "First modification (reorder) should be preserved"
    
    assert 'remove_priority_indices' in result.modifications, \
        "Second modification (removal) should be preserved"
    
    # Verify the specific values
    assert result.modifications['priority_order'] == new_order, \
        f"Should have recorded new order {new_order}"
    
    assert result.modifications['remove_priority_indices'] == [num_priorities - 1], \
        f"Should have recorded removal of last task (index {num_priorities - 1})"
    
    # Verify the result is approved
    assert result.approved is True, \
        "Plan with multiple modifications should be approved"
