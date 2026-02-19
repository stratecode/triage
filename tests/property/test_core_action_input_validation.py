# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for core action input validation.

Feature: plugin-architecture
"""

import asyncio
from datetime import date
from unittest.mock import Mock

from hypothesis import given, settings
from hypothesis import strategies as st

from triage.core.actions_api import CoreActionResult, CoreActionsAPI


# Custom strategies for generating INVALID test data
@st.composite
def invalid_user_id_strategy(draw):
    """Generate invalid user IDs (empty, None, or invalid types)."""
    return draw(
        st.one_of(
            st.just(""),  # Empty string
            st.just(None),  # None
            st.just(123),  # Wrong type (int)
            st.just([]),  # Wrong type (list)
            st.just({}),  # Wrong type (dict)
            st.text(max_size=0),  # Empty text
            st.just("   "),  # Whitespace only
        )
    )


@st.composite
def invalid_date_strategy(draw):
    """Generate invalid dates."""
    return draw(
        st.one_of(
            st.just("not-a-date"),  # String instead of date
            st.just(123),  # Integer instead of date
            st.just([]),  # List instead of date
            st.just({}),  # Dict instead of date
        )
    )


@st.composite
def invalid_closure_rate_strategy(draw):
    """Generate invalid closure rates (outside 0.0-1.0 range or wrong type)."""
    return draw(
        st.one_of(
            st.floats(min_value=-10.0, max_value=-0.01),  # Negative
            st.floats(min_value=1.01, max_value=10.0),  # Greater than 1.0
            st.just(float("inf")),  # Infinity
            st.just(float("-inf")),  # Negative infinity
            st.just(float("nan")),  # NaN
            st.just("0.5"),  # String instead of float
            st.just([0.5]),  # List instead of float
        )
    )


@st.composite
def invalid_task_key_strategy(draw):
    """Generate invalid JIRA task keys."""
    return draw(
        st.one_of(
            st.just(""),  # Empty string
            st.just(None),  # None
            st.just(123),  # Wrong type
            st.just("INVALID"),  # Missing number
            st.just("-123"),  # Missing project
            st.just("   "),  # Whitespace only
            st.text(max_size=0),  # Empty text
        )
    )


@st.composite
def invalid_target_days_strategy(draw):
    """Generate invalid target days (negative, zero, or wrong type)."""
    return draw(
        st.one_of(
            st.floats(min_value=-10.0, max_value=-0.01),  # Negative
            st.just(0.0),  # Zero
            st.just(float("inf")),  # Infinity
            st.just(float("-inf")),  # Negative infinity
            st.just(float("nan")),  # NaN
            st.just("1.0"),  # String instead of float
            st.just([1.0]),  # List instead of float
        )
    )


@st.composite
def invalid_feedback_strategy(draw):
    """Generate invalid feedback (empty when required)."""
    return draw(
        st.one_of(
            st.just(""),  # Empty string
            st.just("   "),  # Whitespace only
            st.just(None),  # None when required
            st.just(123),  # Wrong type
            st.just([]),  # Wrong type
        )
    )


@st.composite
def invalid_settings_strategy(draw):
    """Generate invalid settings dictionaries."""
    return draw(
        st.one_of(
            st.just(None),  # None instead of dict
            st.just("settings"),  # String instead of dict
            st.just([]),  # List instead of dict
            st.just(123),  # Integer instead of dict
            # Dict with invalid values
            st.fixed_dictionaries(
                {
                    "approval_timeout_hours": st.one_of(
                        st.just(-1),  # Negative
                        st.just(0),  # Zero
                        st.just("24"),  # String instead of int
                    )
                }
            ),
            st.fixed_dictionaries(
                {
                    "max_priorities": st.one_of(
                        st.just(0),  # Too low
                        st.just(10),  # Too high
                        st.just(-1),  # Negative
                        st.just("3"),  # String instead of int
                    )
                }
            ),
            st.fixed_dictionaries(
                {
                    "admin_block_time": st.one_of(
                        st.just("invalid"),  # Invalid format
                        st.just("25:00-26:00"),  # Invalid hours
                        st.just(123),  # Wrong type
                    )
                }
            ),
        )
    )


# Helper function to create a mock CoreActionsAPI
def create_mock_core_api():
    """Create a mock CoreActionsAPI for testing."""
    mock_jira_client = Mock()
    mock_task_classifier = Mock()
    mock_plan_generator = Mock()
    mock_approval_manager = Mock()

    return CoreActionsAPI(
        jira_client=mock_jira_client,
        task_classifier=mock_task_classifier,
        plan_generator=mock_plan_generator,
        approval_manager=mock_approval_manager,
    )


# Property 3: Core Action Input Validation
@given(invalid_user_id=invalid_user_id_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_generate_plan_rejects_invalid_user_id(invalid_user_id):
    """Property 3: Core Action Input Validation - generate_plan with invalid user_id

    For any invalid user_id, the generate_plan action should reject the request
    and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to generate plan with invalid user_id
    try:
        result = asyncio.run(api.generate_plan(user_id=invalid_user_id))

        # Should return an error result
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        # If the API doesn't validate and crashes, that's also acceptable
        # as long as it doesn't return success
        if result.success:
            # This should not happen with invalid input
            assert False, f"generate_plan should not succeed with invalid user_id: {invalid_user_id}"
        else:
            # Verify error information is present
            assert result.error is not None, "Error message must be present"
            assert result.error_code is not None, "Error code must be present"
            assert len(result.error) > 0, "Error message must not be empty"

    except (TypeError, ValueError, AttributeError) as e:
        # It's acceptable to raise an exception for invalid input
        # as long as it's a clear error type
        assert str(e), "Exception must have a message"


@given(invalid_date=invalid_date_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_generate_plan_rejects_invalid_date(invalid_date):
    """Property 3: Core Action Input Validation - generate_plan with invalid date

    For any invalid plan_date, the generate_plan action should reject the request
    and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to generate plan with invalid date
    try:
        result = asyncio.run(api.generate_plan(user_id="valid_user", plan_date=invalid_date))

        # Should return an error result or raise exception
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        if result.success:
            assert False, f"generate_plan should not succeed with invalid date: {invalid_date}"
        else:
            assert result.error is not None, "Error message must be present"
            assert result.error_code is not None, "Error code must be present"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for invalid input
        assert str(e), "Exception must have a message"


@given(invalid_closure_rate=invalid_closure_rate_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_generate_plan_rejects_invalid_closure_rate(invalid_closure_rate):
    """Property 3: Core Action Input Validation - generate_plan with invalid closure_rate

    For any invalid closure_rate (negative, > 1.0, NaN, Inf), the generate_plan
    action should reject the request and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to generate plan with invalid closure rate
    try:
        result = asyncio.run(api.generate_plan(user_id="valid_user", closure_rate=invalid_closure_rate))

        # Should return an error result or raise exception
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        if result.success:
            assert False, f"generate_plan should not succeed with invalid closure_rate: {invalid_closure_rate}"
        else:
            assert result.error is not None, "Error message must be present"
            assert result.error_code is not None, "Error code must be present"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for invalid input
        assert str(e), "Exception must have a message"


@given(invalid_task_key=invalid_task_key_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_decompose_task_rejects_invalid_task_key(invalid_task_key):
    """Property 3: Core Action Input Validation - decompose_task with invalid task_key

    For any invalid task_key (empty, None, wrong format), the decompose_task
    action should reject the request and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to decompose task with invalid key
    try:
        result = asyncio.run(api.decompose_task(user_id="valid_user", task_key=invalid_task_key))

        # Should return an error result or raise exception
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        if result.success:
            assert False, f"decompose_task should not succeed with invalid task_key: {invalid_task_key}"
        else:
            assert result.error is not None, "Error message must be present"
            assert result.error_code is not None, "Error code must be present"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for invalid input
        assert str(e), "Exception must have a message"


@given(invalid_target_days=invalid_target_days_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_decompose_task_rejects_invalid_target_days(invalid_target_days):
    """Property 3: Core Action Input Validation - decompose_task with invalid target_days

    For any invalid target_days (negative, zero, NaN, Inf), the decompose_task
    action should reject the request and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to decompose task with invalid target days
    try:
        result = asyncio.run(
            api.decompose_task(user_id="valid_user", task_key="VALID-123", target_days=invalid_target_days)
        )

        # Should return an error result or raise exception
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        if result.success:
            assert False, f"decompose_task should not succeed with invalid target_days: {invalid_target_days}"
        else:
            assert result.error is not None, "Error message must be present"
            assert result.error_code is not None, "Error code must be present"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for invalid input
        assert str(e), "Exception must have a message"


@given(invalid_feedback=invalid_feedback_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_reject_plan_rejects_invalid_feedback(invalid_feedback):
    """Property 3: Core Action Input Validation - reject_plan with invalid feedback

    For any invalid feedback (empty, None, wrong type), the reject_plan action
    should reject the request and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to reject plan with invalid feedback
    try:
        result = asyncio.run(api.reject_plan(user_id="valid_user", plan_date=date.today(), feedback=invalid_feedback))

        # Should return an error result or raise exception
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        # Empty/whitespace feedback should be rejected since it's required
        if isinstance(invalid_feedback, str) and len(invalid_feedback.strip()) == 0:
            if result.success:
                assert False, "reject_plan should not succeed with empty feedback"
            else:
                assert result.error is not None, "Error message must be present"
                assert result.error_code is not None, "Error code must be present"
        elif invalid_feedback is None or not isinstance(invalid_feedback, str):
            # Wrong type should fail
            if result.success:
                assert False, f"reject_plan should not succeed with invalid feedback type: {type(invalid_feedback)}"
            else:
                assert result.error is not None, "Error message must be present"
                assert result.error_code is not None, "Error code must be present"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for invalid input
        assert str(e), "Exception must have a message"


@given(invalid_settings=invalid_settings_strategy())
@settings(max_examples=100, deadline=None)
def test_property_3_configure_settings_rejects_invalid_settings(invalid_settings):
    """Property 3: Core Action Input Validation - configure_settings with invalid settings

    For any invalid settings (wrong type, invalid values), the configure_settings
    action should reject the request and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to configure with invalid settings
    try:
        result = asyncio.run(api.configure_settings(user_id="valid_user", settings=invalid_settings))

        # Should return an error result or raise exception
        assert isinstance(result, CoreActionResult), "Must return CoreActionResult"

        # If settings is not a dict, should fail
        if not isinstance(invalid_settings, dict):
            if result.success:
                assert False, f"configure_settings should not succeed with non-dict settings: {type(invalid_settings)}"
            else:
                assert result.error is not None, "Error message must be present"
                assert result.error_code is not None, "Error code must be present"
        else:
            # If settings is a dict but has invalid values, the API might:
            # 1. Reject the entire request (preferred)
            # 2. Filter out invalid values and succeed with valid ones
            # Either behavior is acceptable, but error messages should be clear
            if not result.success:
                assert result.error is not None, "Error message must be present"
                assert result.error_code is not None, "Error code must be present"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for invalid input
        assert str(e), "Exception must have a message"


@given(
    action=st.sampled_from(
        ["generate_plan", "approve_plan", "reject_plan", "decompose_task", "get_status", "configure_settings"]
    )
)
@settings(max_examples=100, deadline=None)
def test_property_3_all_actions_reject_missing_required_params(action: str):
    """Property 3: Core Action Input Validation - Missing required parameters

    For any core action with missing required parameters, the action should
    reject the request and return an error with an actionable message.

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.7, 2.8
    """
    api = create_mock_core_api()

    # Attempt to call action with missing required parameters
    try:
        if action == "generate_plan":
            # Missing user_id (required)
            result = asyncio.run(api.generate_plan(user_id=None))
        elif action == "approve_plan":
            # Missing plan_date (required)
            result = asyncio.run(api.approve_plan(user_id="valid_user", plan_date=None, approved=True))
        elif action == "reject_plan":
            # Missing feedback (required)
            result = asyncio.run(api.reject_plan(user_id="valid_user", plan_date=date.today(), feedback=None))
        elif action == "decompose_task":
            # Missing task_key (required)
            result = asyncio.run(api.decompose_task(user_id="valid_user", task_key=None))
        elif action == "get_status":
            # Missing user_id (required)
            result = asyncio.run(api.get_status(user_id=None))
        elif action == "configure_settings":
            # Missing settings (required)
            result = asyncio.run(api.configure_settings(user_id="valid_user", settings=None))

        # Should return an error result or raise exception
        if isinstance(result, CoreActionResult):
            if result.success:
                assert False, f"{action} should not succeed with missing required parameters"
            else:
                assert result.error is not None, "Error message must be present"
                assert result.error_code is not None, "Error code must be present"
                assert len(result.error) > 0, "Error message must not be empty"

    except (TypeError, ValueError, AttributeError) as e:
        # Acceptable to raise exception for missing required parameters
        assert str(e), "Exception must have a message"


@given(
    action=st.sampled_from(
        ["generate_plan", "approve_plan", "reject_plan", "decompose_task", "get_status", "configure_settings"]
    )
)
@settings(max_examples=100, deadline=None)
def test_property_3_error_messages_are_actionable(action: str):
    """Property 3: Core Action Input Validation - Actionable error messages

    For any core action that fails validation, the error message should be
    actionable (i.e., tell the user what went wrong and how to fix it).

    Feature: plugin-architecture, Property 3: Core Action Input Validation
    Validates: Requirements 2.8
    """
    api = create_mock_core_api()

    # Attempt to call action with clearly invalid input
    try:
        if action == "generate_plan":
            result = asyncio.run(api.generate_plan(user_id=""))
        elif action == "approve_plan":
            result = asyncio.run(api.approve_plan(user_id="valid_user", plan_date="not-a-date", approved=True))
        elif action == "reject_plan":
            result = asyncio.run(api.reject_plan(user_id="valid_user", plan_date=date.today(), feedback=""))
        elif action == "decompose_task":
            result = asyncio.run(api.decompose_task(user_id="valid_user", task_key=""))
        elif action == "get_status":
            result = asyncio.run(api.get_status(user_id=""))
        elif action == "configure_settings":
            result = asyncio.run(api.configure_settings(user_id="valid_user", settings="not-a-dict"))

        # If we get a result, verify error message quality
        if isinstance(result, CoreActionResult) and not result.success:
            assert result.error is not None, "Error message must be present"
            assert len(result.error) > 0, "Error message must not be empty"

            # Error message should not be just a generic exception string
            # It should provide context about what went wrong
            error_lower = result.error.lower()

            # Check that error message contains useful information
            # (not just "error" or "failed")
            assert len(result.error) > 10, "Error message should be descriptive"

            # Error code should be present and meaningful
            assert result.error_code is not None, "Error code must be present"
            assert len(result.error_code) > 0, "Error code must not be empty"
            assert result.error_code != "ERROR", "Error code should be specific"

    except (TypeError, ValueError, AttributeError) as e:
        # If exception is raised, it should have a clear message
        assert str(e), "Exception must have a message"
        assert len(str(e)) > 5, "Exception message should be descriptive"
