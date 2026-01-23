# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for ApprovalManager."""

from unittest.mock import patch
from datetime import date

from triage.approval_manager import ApprovalManager
from triage.models import (
    DailyPlan,
    AdminBlock,
    TaskClassification,
    TaskCategory,
    JiraIssue,
    ApprovalResult,
)


class TestApprovalManager:
    """Test suite for ApprovalManager class."""
    
    def test_present_plan_approval(self):
        """Test that present_plan returns approved result when user approves."""
        # Create a simple daily plan
        plan = DailyPlan(
            date=date.today(),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        
        # Create approval manager
        manager = ApprovalManager()
        
        # Mock user input to approve
        with patch('builtins.input', return_value='yes'):
            with patch('builtins.print'):  # Suppress output
                result = manager.present_plan(plan)
        
        # Verify result
        assert isinstance(result, ApprovalResult)
        assert result.approved is True
    
    def test_present_plan_rejection(self):
        """Test that present_plan returns rejected result when user rejects."""
        # Create a simple daily plan
        plan = DailyPlan(
            date=date.today(),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        
        # Create approval manager
        manager = ApprovalManager()
        
        # Mock user input to reject
        with patch('builtins.input', return_value='no'):
            with patch('builtins.print'):  # Suppress output
                result = manager.present_plan(plan)
        
        # Verify result
        assert isinstance(result, ApprovalResult)
        assert result.approved is False
    
    def test_present_plan_accepts_y_shorthand(self):
        """Test that present_plan accepts 'y' as shorthand for yes."""
        plan = DailyPlan(
            date=date.today(),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        
        manager = ApprovalManager()
        
        with patch('builtins.input', return_value='y'):
            with patch('builtins.print'):
                result = manager.present_plan(plan)
        
        assert result.approved is True
    
    def test_present_plan_accepts_n_shorthand(self):
        """Test that present_plan accepts 'n' as shorthand for no."""
        plan = DailyPlan(
            date=date.today(),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        
        manager = ApprovalManager()
        
        with patch('builtins.input', return_value='n'):
            with patch('builtins.print'):
                result = manager.present_plan(plan)
        
        assert result.approved is False
    
    def test_present_plan_retries_on_invalid_input(self):
        """Test that present_plan retries when user provides invalid input."""
        plan = DailyPlan(
            date=date.today(),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        
        manager = ApprovalManager()
        
        # Mock user input: first invalid, then valid
        with patch('builtins.input', side_effect=['maybe', 'invalid', 'yes']):
            with patch('builtins.print'):
                result = manager.present_plan(plan)
        
        assert result.approved is True
    
    def test_present_plan_displays_markdown(self):
        """Test that present_plan displays the plan in markdown format."""
        # Create a plan with some content
        task = JiraIssue(
            key="PROJ-123",
            summary="Test task",
            description="Test description",
            issue_type="Story",
            priority="High",
            status="To Do",
            assignee="test@example.com",
            story_points=3,
        )
        
        classification = TaskClassification(
            task=task,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=0.5,
        )
        
        plan = DailyPlan(
            date=date.today(),
            priorities=[classification],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        
        manager = ApprovalManager()
        
        # Capture print output
        printed_output = []
        
        def mock_print(*args, **kwargs):
            printed_output.append(' '.join(str(arg) for arg in args))
        
        with patch('builtins.input', return_value='yes'):
            with patch('builtins.print', side_effect=mock_print):
                result = manager.present_plan(plan)
        
        # Verify that markdown was printed
        output_text = '\n'.join(printed_output)
        assert 'DAILY PLAN FOR APPROVAL' in output_text
        assert 'PROJ-123' in output_text or 'Test task' in output_text
