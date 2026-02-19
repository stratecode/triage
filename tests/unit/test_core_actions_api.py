# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for CoreActionsAPI."""

from datetime import date
from unittest.mock import Mock

import pytest

from triage.core.actions_api import CoreActionsAPI
from triage.models import AdminBlock, ClosureRecord, DailyPlan, JiraIssue, SubtaskSpec, TaskCategory, TaskClassification


@pytest.fixture
def mock_jira_client():
    """Create a mock JIRA client."""
    client = Mock()
    client.fetch_active_tasks = Mock(return_value=[])
    client.get_task_by_key = Mock(return_value=None)
    return client


@pytest.fixture
def mock_task_classifier():
    """Create a mock task classifier."""
    classifier = Mock()
    classifier.classify_task = Mock()
    return classifier


@pytest.fixture
def mock_plan_generator():
    """Create a mock plan generator."""
    generator = Mock()
    generator.generate_daily_plan = Mock()
    generator.propose_decomposition = Mock(return_value=[])
    generator.load_closure_record = Mock(return_value=None)
    return generator


@pytest.fixture
def mock_approval_manager():
    """Create a mock approval manager."""
    manager = Mock()
    return manager


@pytest.fixture
def core_api(mock_jira_client, mock_task_classifier, mock_plan_generator, mock_approval_manager):
    """Create a CoreActionsAPI instance with mocked dependencies."""
    return CoreActionsAPI(
        jira_client=mock_jira_client,
        task_classifier=mock_task_classifier,
        plan_generator=mock_plan_generator,
        approval_manager=mock_approval_manager,
    )


@pytest.mark.asyncio
async def test_generate_plan_success(core_api, mock_jira_client, mock_task_classifier, mock_plan_generator):
    """Test successful plan generation."""
    # Setup mocks
    mock_issue = JiraIssue(
        key="TEST-1",
        summary="Test task",
        description="Test description",
        issue_type="Task",
        priority="High",
        status="To Do",
        assignee="test@example.com",
    )
    mock_jira_client.fetch_active_tasks.return_value = [mock_issue]

    mock_classification = TaskClassification(
        task=mock_issue,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5,
    )
    mock_task_classifier.classify_task.return_value = mock_classification

    mock_plan = DailyPlan(
        date=date.today(),
        priorities=[mock_classification],
        admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
        other_tasks=[],
    )
    mock_plan_generator.generate_daily_plan.return_value = mock_plan

    # Execute
    result = await core_api.generate_plan(user_id="test_user")

    # Verify
    assert result.success is True
    assert result.data is not None
    assert "plan" in result.data
    assert "markdown" in result.data
    assert result.error is None


@pytest.mark.asyncio
async def test_generate_plan_not_initialized(mock_approval_manager):
    """Test plan generation when components are not initialized."""
    # Create API without required components
    api = CoreActionsAPI(
        jira_client=None, task_classifier=None, plan_generator=None, approval_manager=mock_approval_manager
    )

    # Execute
    result = await api.generate_plan(user_id="test_user")

    # Verify
    assert result.success is False
    assert result.error == "Core components not initialized"
    assert result.error_code == "NOT_INITIALIZED"


@pytest.mark.asyncio
async def test_generate_plan_exception(core_api, mock_jira_client):
    """Test plan generation when an exception occurs."""
    # Setup mock to raise exception
    mock_jira_client.fetch_active_tasks.side_effect = Exception("JIRA connection failed")

    # Execute
    result = await core_api.generate_plan(user_id="test_user")

    # Verify
    assert result.success is False
    assert "JIRA connection failed" in result.error
    assert result.error_code == "PLAN_GENERATION_FAILED"


@pytest.mark.asyncio
async def test_approve_plan_success(core_api):
    """Test successful plan approval."""
    # Execute
    result = await core_api.approve_plan(user_id="test_user", plan_date=date.today(), approved=True)

    # Verify
    assert result.success is True
    assert result.data is not None
    assert result.data["approved"] is True


@pytest.mark.asyncio
async def test_reject_plan_success(core_api, mock_jira_client, mock_task_classifier, mock_plan_generator):
    """Test successful plan rejection with re-planning."""
    # Setup mocks for re-planning
    mock_jira_client.fetch_active_tasks.return_value = []
    mock_plan = DailyPlan(
        date=date.today(),
        priorities=[],
        admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
        other_tasks=[],
    )
    mock_plan_generator.generate_daily_plan.return_value = mock_plan

    # Execute
    result = await core_api.reject_plan(user_id="test_user", plan_date=date.today(), feedback="Too many tasks")

    # Verify
    assert result.success is True
    assert result.data is not None
    assert result.data["rejection_recorded"] is True
    assert "new_plan" in result.data


@pytest.mark.asyncio
async def test_decompose_task_success(core_api, mock_jira_client, mock_plan_generator):
    """Test successful task decomposition."""
    # Setup mocks
    mock_task = JiraIssue(
        key="TEST-1",
        summary="Long running task",
        description="Test description",
        issue_type="Task",
        priority="High",
        status="To Do",
        assignee="test@example.com",
        story_points=5,
    )
    mock_jira_client.get_task_by_key.return_value = mock_task

    mock_subtasks = [
        SubtaskSpec(summary="Subtask 1", description="Description 1", estimated_days=0.75, order=1),
        SubtaskSpec(summary="Subtask 2", description="Description 2", estimated_days=0.75, order=2),
    ]
    mock_plan_generator.propose_decomposition.return_value = mock_subtasks

    # Execute
    result = await core_api.decompose_task(user_id="test_user", task_key="TEST-1")

    # Verify
    assert result.success is True
    assert result.data is not None
    assert result.data["task_key"] == "TEST-1"
    assert result.data["count"] == 2
    assert len(result.data["subtasks"]) == 2


@pytest.mark.asyncio
async def test_get_status_with_closure_record(core_api, mock_plan_generator):
    """Test getting status when closure record exists."""
    # Setup mock
    mock_record = ClosureRecord(
        date=date.today(), total_priorities=3, completed_priorities=2, closure_rate=0.67, incomplete_tasks=["TEST-1"]
    )
    mock_plan_generator.load_closure_record.return_value = mock_record

    # Execute
    result = await core_api.get_status(user_id="test_user")

    # Verify
    assert result.success is True
    assert result.data is not None
    assert result.data["status"] == "in_progress"
    assert result.data["total_priorities"] == 3
    assert result.data["completed_priorities"] == 2
    assert result.data["closure_rate"] == 0.67


@pytest.mark.asyncio
async def test_get_status_no_record(core_api, mock_plan_generator):
    """Test getting status when no closure record exists."""
    # Setup mock
    mock_plan_generator.load_closure_record.return_value = None

    # Execute
    result = await core_api.get_status(user_id="test_user")

    # Verify
    assert result.success is True
    assert result.data is not None
    assert result.data["status"] == "not_found"


@pytest.mark.asyncio
async def test_configure_settings_success(core_api):
    """Test successful settings configuration."""
    # Execute
    settings = {
        "notification_enabled": True,
        "approval_timeout_hours": 48,
        "admin_block_time": "14:00-15:30",
        "max_priorities": 3,
    }
    result = await core_api.configure_settings(user_id="test_user", settings=settings)

    # Verify
    assert result.success is True
    assert result.data is not None
    assert result.data["settings"]["notification_enabled"] is True
    assert result.data["settings"]["approval_timeout_hours"] == 48
    assert result.data["settings"]["max_priorities"] == 3


@pytest.mark.asyncio
async def test_configure_settings_validation(core_api):
    """Test settings validation filters invalid values."""
    # Execute with invalid settings
    settings = {
        "notification_enabled": "invalid",  # Should be bool
        "approval_timeout_hours": -5,  # Should be positive
        "max_priorities": 10,  # Should be 1-5
        "unknown_setting": "value",  # Should be ignored
    }
    result = await core_api.configure_settings(user_id="test_user", settings=settings)

    # Verify - invalid settings should be filtered out
    assert result.success is True
    assert result.data is not None
    # notification_enabled should be converted to bool (truthy string)
    assert "notification_enabled" in result.data["settings"]
    # Invalid values should be filtered
    assert "approval_timeout_hours" not in result.data["settings"]
    assert "max_priorities" not in result.data["settings"]
    assert "unknown_setting" not in result.data["settings"]
