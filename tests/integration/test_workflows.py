# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Integration tests for complete workflows."""

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import date
import tempfile
import shutil

from triage.jira_client import JiraClient
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator
from triage.approval_manager import ApprovalManager
from triage.background_scheduler import BackgroundScheduler
from triage.models import JiraIssue, IssueLink, SubtaskSpec, TaskCategory


@pytest.fixture
def temp_closure_dir():
    """Create a temporary directory for closure tracking."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_tasks():
    """Create a sample set of JIRA tasks for testing."""
    return [
        # Priority-eligible task
        JiraIssue(
            key='PROJ-1',
            summary='Implement login feature',
            description='Add user login functionality',
            issue_type='Story',
            priority='High',
            status='To Do',
            assignee='test@example.com',
            story_points=1,
            time_estimate=28800,  # 8 hours
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
        # Another priority-eligible task
        JiraIssue(
            key='PROJ-2',
            summary='Fix navigation bug',
            description='Navigation menu not working',
            issue_type='Bug',
            priority='Medium',
            status='To Do',
            assignee='test@example.com',
            story_points=1,
            time_estimate=14400,  # 4 hours
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
        # Administrative task
        JiraIssue(
            key='PROJ-3',
            summary='Weekly status report',
            description='Prepare weekly status report',
            issue_type='Task',
            priority='Low',
            status='To Do',
            assignee='test@example.com',
            story_points=None,
            time_estimate=7200,  # 2 hours
            labels=['admin', 'report'],
            issue_links=[],
            custom_fields={}
        ),
        # Task with dependency
        JiraIssue(
            key='PROJ-4',
            summary='Deploy to production',
            description='Deploy new features',
            issue_type='Task',
            priority='High',
            status='To Do',
            assignee='test@example.com',
            story_points=1,
            time_estimate=14400,
            labels=[],
            issue_links=[
                IssueLink(
                    link_type='is blocked by',
                    target_key='PROJ-5',
                    target_summary='Code review'
                )
            ],
            custom_fields={}
        ),
        # Long-running task
        JiraIssue(
            key='PROJ-6',
            summary='Refactor authentication system',
            description='Complete refactor of auth',
            issue_type='Epic',
            priority='Medium',
            status='To Do',
            assignee='test@example.com',
            story_points=8,  # 10 days
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
    ]


@pytest.fixture
def blocking_task():
    """Create a blocking task for testing."""
    return JiraIssue(
        key='PROJ-BLOCK',
        summary='Critical production issue',
        description='Production is down',
        issue_type='Bug',
        priority='Blocker',
        status='To Do',
        assignee='test@example.com',
        story_points=1,
        time_estimate=14400,
        labels=[],
        issue_links=[],
        custom_fields={}
    )


class TestDailyPlanGenerationWorkflow:
    """Integration tests for complete daily plan generation workflow."""
    
    def test_complete_plan_generation_workflow(self, sample_tasks, temp_closure_dir):
        """
        Test complete daily plan generation workflow:
        - Fetch tasks from JIRA
        - Classify all tasks
        - Select priorities
        - Group admin tasks
        - Generate markdown output
        """
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch:
            mock_fetch.return_value = sample_tasks
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=temp_closure_dir)
            
            # Generate plan
            plan = plan_generator.generate_daily_plan()
            
            # Verify plan structure
            assert plan.date == date.today()
            assert len(plan.priorities) <= 3
            assert len(plan.priorities) >= 1  # Should have at least one priority
            
            # Verify priorities are eligible
            for priority in plan.priorities:
                assert priority.is_priority_eligible
                assert not priority.has_dependencies
                assert priority.estimated_days <= 1.0
                assert priority.category != TaskCategory.ADMINISTRATIVE
            
            # Verify admin block
            assert plan.admin_block is not None
            assert plan.admin_block.time_allocation_minutes <= 90
            
            # Verify admin tasks are in admin block
            for admin_task in plan.admin_block.tasks:
                assert admin_task.category == TaskCategory.ADMINISTRATIVE
            
            # Verify markdown output
            markdown = plan.to_markdown()
            assert '# Daily Plan' in markdown
            assert "Today's Priorities" in markdown
            # Admin block only appears if there are admin tasks
            if plan.admin_block.tasks:
                assert 'Administrative Block' in markdown
    
    def test_plan_with_approval_workflow(self, sample_tasks, temp_closure_dir):
        """
        Test plan generation with approval workflow:
        - Generate plan
        - Present for approval
        - Handle approval/rejection
        """
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch:
            mock_fetch.return_value = sample_tasks
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=temp_closure_dir)
            approval_manager = ApprovalManager(timeout_seconds=0)  # No timeout for tests
            
            # Generate plan
            plan = plan_generator.generate_daily_plan()
            
            # Mock user approval - patch input to avoid blocking
            with patch('builtins.input', return_value='yes'):
                result = approval_manager.present_plan(plan)
                
                assert result.approved
                assert result.feedback is None


class TestBlockingTaskInterruptionWorkflow:
    """Integration tests for blocking task interruption and re-planning."""
    
    def test_blocking_task_detection_and_replanning(self, sample_tasks, blocking_task, temp_closure_dir):
        """
        Test complete blocking task workflow:
        - Generate initial plan
        - Detect blocking task
        - Trigger re-planning
        - Generate new plan with blocking task
        """
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch_active, \
             patch.object(JiraClient, 'fetch_blocking_tasks') as mock_fetch_blocking:
            
            # Initial state: no blocking tasks
            mock_fetch_active.return_value = sample_tasks
            mock_fetch_blocking.return_value = []
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=temp_closure_dir)
            
            # Generate initial plan
            initial_plan = plan_generator.generate_daily_plan()
            
            # Verify initial plan doesn't have blocking task
            initial_priority_keys = {c.task.key for c in initial_plan.priorities}
            assert blocking_task.key not in initial_priority_keys
            
            # Simulate blocking task appearing
            mock_fetch_blocking.return_value = [blocking_task]
            
            # Generate re-plan
            new_plan = plan_generator.generate_replan(blocking_task, initial_plan)
            
            # Verify new plan includes blocking task
            new_priority_keys = {c.task.key for c in new_plan.priorities}
            assert blocking_task.key in new_priority_keys
            
            # Verify blocking task is first priority
            assert new_plan.priorities[0].task.key == blocking_task.key
    
    def test_background_scheduler_blocking_detection(self, sample_tasks, blocking_task):
        """
        Test background scheduler detecting blocking tasks:
        - Start scheduler
        - Simulate blocking task appearing
        - Verify detection and notification
        
        NOTE: This test uses very short intervals and immediate cleanup to avoid memory issues.
        """
        # Mock JIRA client to avoid real API calls
        with patch.object(JiraClient, 'fetch_blocking_tasks') as mock_fetch_blocking, \
             patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch_active:
            
            mock_fetch_blocking.return_value = [blocking_task]
            mock_fetch_active.return_value = sample_tasks
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            
            # Use a temporary directory for closure tracking
            with tempfile.TemporaryDirectory() as temp_dir:
                plan_generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=temp_dir)
                
                # Create scheduler with very short poll interval for testing
                scheduler = BackgroundScheduler(
                    jira_client=jira_client,
                    plan_generator=plan_generator,
                    poll_interval_minutes=0.001  # Very short - 0.06 seconds
                )
                
                # Track notifications
                notifications = []
                def mock_notify(**kwargs):
                    notifications.append(kwargs)
                
                scheduler.notification_callback = mock_notify
                
                try:
                    # Start scheduler
                    scheduler.start()
                    
                    # Wait very briefly for one polling cycle
                    import time
                    time.sleep(0.2)  # 200ms should be enough for one cycle
                    
                    # Verify blocking task fetch was called
                    assert mock_fetch_blocking.called
                    
                finally:
                    # Always stop scheduler to clean up threads
                    scheduler.stop()
                    
                    # Give threads time to clean up
                    time.sleep(0.1)


class TestLongRunningTaskDecompositionWorkflow:
    """Integration tests for long-running task decomposition."""
    
    def test_complete_decomposition_workflow(self, sample_tasks, temp_closure_dir):
        """
        Test complete decomposition workflow:
        - Identify long-running task
        - Propose decomposition
        - Present for approval
        - Create subtasks in JIRA
        """
        # Find long-running task
        long_task = next(t for t in sample_tasks if t.key == 'PROJ-6')
        
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch, \
             patch.object(JiraClient, 'create_subtask') as mock_create:
            
            mock_fetch.return_value = sample_tasks
            mock_create.side_effect = lambda parent, subtask: f"{parent}-{subtask.order}"
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=temp_closure_dir)
            approval_manager = ApprovalManager(timeout_seconds=0)  # No timeout for tests
            
            # Classify long-running task
            classification = classifier.classify_task(long_task)
            assert classification.category == TaskCategory.LONG_RUNNING
            assert classification.estimated_days > 1.0
            
            # Propose decomposition
            subtasks = plan_generator.propose_decomposition(long_task)
            
            # Verify subtasks
            assert len(subtasks) >= 2
            for subtask in subtasks:
                assert subtask.estimated_days <= 1.0
                assert subtask.summary
                assert subtask.description
            
            # Mock user approval - patch input to avoid blocking
            with patch('builtins.input', return_value='yes'):
                result = approval_manager.present_decomposition(long_task, subtasks)
                
                assert result.approved
            
            # Create subtasks in JIRA (if approved)
            if result.approved:
                created_keys = []
                for subtask in subtasks:
                    key = jira_client.create_subtask(long_task.key, subtask)
                    created_keys.append(key)
                
                # Verify subtasks were created
                assert len(created_keys) == len(subtasks)
                assert mock_create.call_count == len(subtasks)


class TestEndToEndWorkflow:
    """End-to-end integration tests covering multiple workflows."""
    
    def test_full_day_workflow(self, sample_tasks, blocking_task, temp_closure_dir):
        """
        Test a complete day's workflow:
        1. Generate morning plan
        2. Work on priorities
        3. Blocking task appears
        4. Re-plan
        5. Track closure at end of day
        """
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch_active, \
             patch.object(JiraClient, 'fetch_blocking_tasks') as mock_fetch_blocking:
            
            # Morning: Generate initial plan
            mock_fetch_active.return_value = sample_tasks
            mock_fetch_blocking.return_value = []
            
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=temp_closure_dir)
            
            morning_plan = plan_generator.generate_daily_plan()
            assert len(morning_plan.priorities) > 0
            
            # Afternoon: Blocking task appears
            mock_fetch_blocking.return_value = [blocking_task]
            
            # Re-plan
            afternoon_plan = plan_generator.generate_replan(blocking_task, morning_plan)
            assert afternoon_plan.priorities[0].task.key == blocking_task.key
            
            # End of day: Track closure
            # Simulate completing some tasks
            completed_keys = [morning_plan.priorities[0].task.key]
            remaining_tasks = [t for t in sample_tasks if t.key not in completed_keys]
            mock_fetch_active.return_value = remaining_tasks
            
            # Save closure record
            closure_record = plan_generator.save_closure_record(
                date.today(),
                morning_plan.priorities
            )
            
            # Verify closure tracking
            assert closure_record.total_priorities == len(morning_plan.priorities)
            assert closure_record.completed_priorities >= 0
            assert 0.0 <= closure_record.closure_rate <= 1.0
