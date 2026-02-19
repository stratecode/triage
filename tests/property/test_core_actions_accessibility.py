# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for core actions accessibility.

Feature: plugin-architecture
"""

from datetime import date, timedelta
from typing import Any, Dict, Optional
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.core.actions_api import CoreActionResult, CoreActionsAPI
from triage.models import AdminBlock, DailyPlan, JiraIssue


# Custom strategies for generating test data
@st.composite
def user_id_strategy(draw):
    """Generate random user IDs."""
    return draw(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_-@."),
        )
    )


@st.composite
def date_strategy(draw):
    """Generate random dates within a reasonable range."""
    days_offset = draw(st.integers(min_value=-365, max_value=365))
    return date.today() + timedelta(days=days_offset)


@st.composite
def closure_rate_strategy(draw):
    """Generate random closure rates (0.0 to 1.0)."""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def task_key_strategy(draw):
    """Generate random JIRA task keys."""
    project = draw(st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    return f"{project}-{number}"


@st.composite
def target_days_strategy(draw):
    """Generate random target days for task decomposition."""
    return draw(st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False))


@st.composite
def settings_strategy(draw):
    """Generate random settings dictionaries."""
    settings = {}

    # Randomly include various settings
    if draw(st.booleans()):
        settings["notification_enabled"] = draw(st.booleans())

    if draw(st.booleans()):
        settings["approval_timeout_hours"] = draw(st.integers(min_value=1, max_value=168))

    if draw(st.booleans()):
        hour1 = draw(st.integers(min_value=0, max_value=23))
        hour2 = draw(st.integers(min_value=0, max_value=23))
        if hour1 != hour2:
            start = min(hour1, hour2)
            end = max(hour1, hour2)
            settings["admin_block_time"] = f"{start:02d}:00-{end:02d}:00"

    if draw(st.booleans()):
        settings["max_priorities"] = draw(st.integers(min_value=1, max_value=5))

    return settings


@st.composite
def feedback_strategy(draw):
    """Generate random feedback strings."""
    return draw(st.one_of(st.none(), st.text(min_size=1, max_size=200)))


# Helper function to create a mock CoreActionsAPI with controlled behavior
def create_mock_core_api(
    generate_plan_succeeds: bool = True,
    approve_plan_succeeds: bool = True,
    reject_plan_succeeds: bool = True,
    decompose_task_succeeds: bool = True,
    get_status_succeeds: bool = True,
    configure_settings_succeeds: bool = True,
):
    """Create a mock CoreActionsAPI with controlled success/failure behavior."""
    # Create mock dependencies
    mock_jira_client = Mock()
    mock_task_classifier = Mock()
    mock_plan_generator = Mock()
    mock_approval_manager = Mock()

    # Setup mock behaviors
    if generate_plan_succeeds:
        mock_jira_client.fetch_active_tasks = Mock(return_value=[])
        mock_plan = DailyPlan(
            date=date.today(),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
        )
        mock_plan_generator.generate_daily_plan = Mock(return_value=mock_plan)
    else:
        mock_jira_client.fetch_active_tasks = Mock(side_effect=Exception("JIRA error"))

    if decompose_task_succeeds:
        mock_task = JiraIssue(
            key="TEST-1",
            summary="Test task",
            description="Test description",
            issue_type="Task",
            priority="High",
            status="To Do",
            assignee="test@example.com",
        )
        mock_jira_client.get_task_by_key = Mock(return_value=mock_task)
        mock_plan_generator.propose_decomposition = Mock(return_value=[])
    else:
        mock_jira_client.get_task_by_key = Mock(side_effect=Exception("Task not found"))

    if get_status_succeeds:
        mock_plan_generator.load_closure_record = Mock(return_value=None)
    else:
        mock_plan_generator.load_closure_record = Mock(side_effect=Exception("Database error"))

    # Create API instance
    return CoreActionsAPI(
        jira_client=mock_jira_client,
        task_classifier=mock_task_classifier,
        plan_generator=mock_plan_generator,
        approval_manager=mock_approval_manager,
    )


# Property 2: Core Actions Accessibility
@given(
    user_id=user_id_strategy(),
    plan_date=st.one_of(st.none(), date_strategy()),
    closure_rate=st.one_of(st.none(), closure_rate_strategy()),
)
@settings(max_examples=100, deadline=None)
def test_property_2_generate_plan_returns_structured_result(
    user_id: str, plan_date: Optional[date], closure_rate: Optional[float]
):
    """Property 2: Core Actions Accessibility - generate_plan

    For any valid user context, invoking generate_plan through the Core Actions API
    should return a structured CoreActionResult (success or error).

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.1
    """
    import asyncio

    # Create mock API
    api = create_mock_core_api(generate_plan_succeeds=True)

    # Execute
    result = asyncio.run(api.generate_plan(user_id=user_id, plan_date=plan_date, closure_rate=closure_rate))

    # Verify result structure
    assert isinstance(result, CoreActionResult), "Result must be a CoreActionResult"
    assert isinstance(result.success, bool), "Result must have a boolean success field"

    # If successful, data should be present
    if result.success:
        assert result.data is not None, "Successful result must have data"
        assert isinstance(result.data, dict), "Result data must be a dictionary"
        assert "plan" in result.data, "Result data must contain 'plan'"
        assert "markdown" in result.data, "Result data must contain 'markdown'"
    else:
        # If failed, error information should be present
        assert result.error is not None, "Failed result must have error message"
        assert result.error_code is not None, "Failed result must have error code"


@given(user_id=user_id_strategy(), plan_date=date_strategy(), approved=st.booleans(), feedback=feedback_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_approve_plan_returns_structured_result(
    user_id: str, plan_date: date, approved: bool, feedback: Optional[str]
):
    """Property 2: Core Actions Accessibility - approve_plan

    For any valid user context, invoking approve_plan through the Core Actions API
    should return a structured CoreActionResult (success or error).

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.2
    """
    import asyncio

    # Create mock API
    api = create_mock_core_api(approve_plan_succeeds=True)

    # Execute
    result = asyncio.run(api.approve_plan(user_id=user_id, plan_date=plan_date, approved=approved, feedback=feedback))

    # Verify result structure
    assert isinstance(result, CoreActionResult), "Result must be a CoreActionResult"
    assert isinstance(result.success, bool), "Result must have a boolean success field"

    # If successful, data should be present
    if result.success:
        assert result.data is not None, "Successful result must have data"
        assert isinstance(result.data, dict), "Result data must be a dictionary"
    else:
        # If failed, error information should be present
        assert result.error is not None, "Failed result must have error message"
        assert result.error_code is not None, "Failed result must have error code"


@given(user_id=user_id_strategy(), plan_date=date_strategy(), feedback=st.text(min_size=1, max_size=200))
@settings(max_examples=100, deadline=None)
def test_property_2_reject_plan_returns_structured_result(user_id: str, plan_date: date, feedback: str):
    """Property 2: Core Actions Accessibility - reject_plan

    For any valid user context, invoking reject_plan through the Core Actions API
    should return a structured CoreActionResult (success or error).

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.3
    """
    import asyncio

    # Create mock API
    api = create_mock_core_api(reject_plan_succeeds=True)

    # Execute
    result = asyncio.run(api.reject_plan(user_id=user_id, plan_date=plan_date, feedback=feedback))

    # Verify result structure
    assert isinstance(result, CoreActionResult), "Result must be a CoreActionResult"
    assert isinstance(result.success, bool), "Result must have a boolean success field"

    # If successful, data should be present
    if result.success:
        assert result.data is not None, "Successful result must have data"
        assert isinstance(result.data, dict), "Result data must be a dictionary"
        assert "rejection_recorded" in result.data, "Result must indicate rejection was recorded"
    else:
        # If failed, error information should be present
        assert result.error is not None, "Failed result must have error message"
        assert result.error_code is not None, "Failed result must have error code"


@given(user_id=user_id_strategy(), task_key=task_key_strategy(), target_days=target_days_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_decompose_task_returns_structured_result(user_id: str, task_key: str, target_days: float):
    """Property 2: Core Actions Accessibility - decompose_task

    For any valid user context, invoking decompose_task through the Core Actions API
    should return a structured CoreActionResult (success or error).

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.4
    """
    import asyncio

    # Create mock API
    api = create_mock_core_api(decompose_task_succeeds=True)

    # Execute
    result = asyncio.run(api.decompose_task(user_id=user_id, task_key=task_key, target_days=target_days))

    # Verify result structure
    assert isinstance(result, CoreActionResult), "Result must be a CoreActionResult"
    assert isinstance(result.success, bool), "Result must have a boolean success field"

    # If successful, data should be present
    if result.success:
        assert result.data is not None, "Successful result must have data"
        assert isinstance(result.data, dict), "Result data must be a dictionary"
        assert "task_key" in result.data, "Result must contain task_key"
        assert "subtasks" in result.data, "Result must contain subtasks"
        assert "count" in result.data, "Result must contain subtask count"
    else:
        # If failed, error information should be present
        assert result.error is not None, "Failed result must have error message"
        assert result.error_code is not None, "Failed result must have error code"


@given(user_id=user_id_strategy(), plan_date=st.one_of(st.none(), date_strategy()))
@settings(max_examples=100, deadline=None)
def test_property_2_get_status_returns_structured_result(user_id: str, plan_date: Optional[date]):
    """Property 2: Core Actions Accessibility - get_status

    For any valid user context, invoking get_status through the Core Actions API
    should return a structured CoreActionResult (success or error).

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.5
    """
    import asyncio

    # Create mock API
    api = create_mock_core_api(get_status_succeeds=True)

    # Execute
    result = asyncio.run(api.get_status(user_id=user_id, plan_date=plan_date))

    # Verify result structure
    assert isinstance(result, CoreActionResult), "Result must be a CoreActionResult"
    assert isinstance(result.success, bool), "Result must have a boolean success field"

    # If successful, data should be present
    if result.success:
        assert result.data is not None, "Successful result must have data"
        assert isinstance(result.data, dict), "Result data must be a dictionary"
        assert "user_id" in result.data, "Result must contain user_id"
        assert "date" in result.data, "Result must contain date"
        assert "status" in result.data, "Result must contain status"
    else:
        # If failed, error information should be present
        assert result.error is not None, "Failed result must have error message"
        assert result.error_code is not None, "Failed result must have error code"


@given(user_id=user_id_strategy(), settings=settings_strategy())
@settings(max_examples=100, deadline=None)
def test_property_2_configure_settings_returns_structured_result(user_id: str, settings: Dict[str, Any]):
    """Property 2: Core Actions Accessibility - configure_settings

    For any valid user context, invoking configure_settings through the Core Actions API
    should return a structured CoreActionResult (success or error).

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.6
    """
    import asyncio

    # Create mock API
    api = create_mock_core_api(configure_settings_succeeds=True)

    # Execute
    result = asyncio.run(api.configure_settings(user_id=user_id, settings=settings))

    # Verify result structure
    assert isinstance(result, CoreActionResult), "Result must be a CoreActionResult"
    assert isinstance(result.success, bool), "Result must have a boolean success field"

    # If successful, data should be present
    if result.success:
        assert result.data is not None, "Successful result must have data"
        assert isinstance(result.data, dict), "Result data must be a dictionary"
        assert "user_id" in result.data, "Result must contain user_id"
        assert "settings" in result.data, "Result must contain settings"
    else:
        # If failed, error information should be present
        assert result.error is not None, "Failed result must have error message"
        assert result.error_code is not None, "Failed result must have error code"


@given(
    user_id=user_id_strategy(),
    action=st.sampled_from(
        ["generate_plan", "approve_plan", "reject_plan", "decompose_task", "get_status", "configure_settings"]
    ),
    should_succeed=st.booleans(),
)
@settings(max_examples=100, deadline=None)
def test_property_2_all_actions_return_consistent_structure(user_id: str, action: str, should_succeed: bool):
    """Property 2: Core Actions Accessibility - Consistency

    For any core action, the result structure should be consistent regardless of
    success or failure. All actions should return CoreActionResult with appropriate
    fields populated.

    Feature: plugin-architecture, Property 2: Core Actions Accessibility
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
    """
    import asyncio

    # Create mock API with controlled success/failure
    api = create_mock_core_api(
        generate_plan_succeeds=should_succeed,
        approve_plan_succeeds=should_succeed,
        reject_plan_succeeds=should_succeed,
        decompose_task_succeeds=should_succeed,
        get_status_succeeds=should_succeed,
        configure_settings_succeeds=should_succeed,
    )

    # Execute the specified action
    if action == "generate_plan":
        result = asyncio.run(api.generate_plan(user_id=user_id))
    elif action == "approve_plan":
        result = asyncio.run(api.approve_plan(user_id=user_id, plan_date=date.today(), approved=True))
    elif action == "reject_plan":
        result = asyncio.run(api.reject_plan(user_id=user_id, plan_date=date.today(), feedback="Test feedback"))
    elif action == "decompose_task":
        result = asyncio.run(api.decompose_task(user_id=user_id, task_key="TEST-1"))
    elif action == "get_status":
        result = asyncio.run(api.get_status(user_id=user_id))
    elif action == "configure_settings":
        result = asyncio.run(api.configure_settings(user_id=user_id, settings={}))

    # Verify consistent structure
    assert isinstance(result, CoreActionResult), f"{action} must return CoreActionResult"
    assert isinstance(result.success, bool), f"{action} must have boolean success field"
    assert hasattr(result, "data"), f"{action} must have data field"
    assert hasattr(result, "error"), f"{action} must have error field"
    assert hasattr(result, "error_code"), f"{action} must have error_code field"

    # Verify success/failure consistency
    if result.success:
        assert result.data is not None, f"Successful {action} must have data"
        # Error fields can be None for successful results
    else:
        assert result.error is not None, f"Failed {action} must have error message"
        assert result.error_code is not None, f"Failed {action} must have error code"
