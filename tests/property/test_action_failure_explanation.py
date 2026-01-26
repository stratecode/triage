# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for action failure explanation.

Feature: slack-integration, Property 25: Action Failure Explanation

**Validates: Requirements 11.3**
"""

import pytest
from hypothesis import given, strategies as st, settings

from slack_bot.error_handler import ErrorHandler
from slack_bot.triage_api_client import TriageAPIError
from slack_bot.slack_api_client import SlackAPIRetryError
from slack_sdk.errors import SlackApiError
from unittest.mock import Mock


# Custom strategies
@st.composite
def triage_api_error(draw):
    """Generate TriageAPIError with various status codes."""
    status_code = draw(st.sampled_from([400, 401, 403, 404, 429, 500, 502, 503, 504]))
    message = draw(st.text(min_size=10, max_size=100))
    response_body = draw(st.text(min_size=0, max_size=200))
    
    return TriageAPIError(
        message=message,
        status_code=status_code,
        response_body=response_body
    )


@st.composite
def slack_api_error(draw):
    """Generate SlackApiError with various error codes."""
    error_code = draw(st.sampled_from([
        'invalid_auth', 'not_in_channel', 'channel_not_found',
        'rate_limited', 'internal_error'
    ]))
    status_code = draw(st.sampled_from([400, 401, 403, 404, 429, 500]))
    
    response = Mock()
    response.status_code = status_code
    response.get = Mock(return_value=error_code)
    response.headers = {}
    
    return SlackApiError("Test error", response)


@st.composite
def validation_message(draw):
    """Generate validation error messages."""
    return draw(st.text(min_size=10, max_size=200))


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(error=triage_api_error())
@settings(max_examples=20, deadline=None)
def test_triage_api_errors_have_explanation_and_suggestion(error):
    """
    Property 25: Action Failure Explanation
    
    For any TrIAge API error, the error handler should provide
    a user-friendly explanation and troubleshooting suggestion.
    
    Validates: Requirements 11.3
    """
    handler = ErrorHandler()
    
    # Handle the error
    message = handler.handle_triage_api_error(error)
    
    # Verify message has required components
    assert message.text is not None and len(message.text) > 0, \
        "Error message must have fallback text"
    
    assert message.blocks is not None and len(message.blocks) > 0, \
        "Error message must have Block Kit blocks"
    
    # Verify blocks contain header, error description, and suggestion
    block_types = [block.get('type') for block in message.blocks]
    assert 'header' in block_types, \
        "Error message must have header block"
    
    # Check for error description and suggestion in section blocks
    section_blocks = [block for block in message.blocks if block.get('type') == 'section']
    assert len(section_blocks) >= 2, \
        "Error message must have at least error description and suggestion sections"
    
    # Verify text content is not empty
    for block in section_blocks:
        if 'text' in block:
            text_content = block['text'].get('text', '')
            assert len(text_content) > 0, \
                "Section blocks must have non-empty text"


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(error=slack_api_error())
@settings(max_examples=20, deadline=None)
def test_slack_api_errors_have_explanation_and_suggestion(error):
    """
    Property 25: Action Failure Explanation
    
    For any Slack API error, the error handler should provide
    a user-friendly explanation and troubleshooting suggestion.
    
    Validates: Requirements 11.3
    """
    handler = ErrorHandler()
    
    # Wrap in SlackAPIRetryError
    retry_error = SlackAPIRetryError(
        message="Slack API failed",
        original_error=error,
        attempts=3
    )
    
    # Handle the error
    message = handler.handle_slack_api_error(retry_error)
    
    # Verify message has required components
    assert message.text is not None and len(message.text) > 0, \
        "Error message must have fallback text"
    
    assert message.blocks is not None and len(message.blocks) > 0, \
        "Error message must have Block Kit blocks"
    
    # Verify blocks contain header and sections
    block_types = [block.get('type') for block in message.blocks]
    assert 'header' in block_types, \
        "Error message must have header block"
    
    section_blocks = [block for block in message.blocks if block.get('type') == 'section']
    assert len(section_blocks) >= 2, \
        "Error message must have error description and suggestion"


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(message=validation_message())
@settings(max_examples=20, deadline=None)
def test_validation_errors_have_explanation_and_suggestion(message):
    """
    Property 25: Action Failure Explanation
    
    For any validation error, the error handler should provide
    a user-friendly explanation and troubleshooting suggestion.
    
    Validates: Requirements 11.3
    """
    handler = ErrorHandler()
    
    # Handle validation error
    error_message = handler.handle_validation_error(message)
    
    # Verify message structure
    assert error_message.text is not None and len(error_message.text) > 0
    assert error_message.blocks is not None and len(error_message.blocks) > 0
    
    # Verify has header and sections
    block_types = [block.get('type') for block in error_message.blocks]
    assert 'header' in block_types
    
    section_blocks = [block for block in error_message.blocks if block.get('type') == 'section']
    assert len(section_blocks) >= 2


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(
    error_type=st.sampled_from([
        'api_unavailable', 'invalid_command', 'not_configured',
        'rate_limited', 'unauthorized', 'network_error', 'unknown'
    ]),
    message=st.text(min_size=10, max_size=200)
)
@settings(max_examples=20, deadline=None)
def test_all_error_types_have_suggestions(error_type, message):
    """
    Property 25: Action Failure Explanation
    
    For any error type, the error template should provide
    a default suggestion for troubleshooting.
    
    Validates: Requirements 11.3
    """
    from slack_bot.templates import ErrorTemplate
    
    template = ErrorTemplate()
    
    # Render error message
    error_message = template.render(
        error_type=error_type,
        message=message
    )
    
    # Verify message has suggestion
    assert error_message.blocks is not None
    
    # Find section with suggestion
    suggestion_found = False
    for block in error_message.blocks:
        if block.get('type') == 'section':
            text_content = block.get('text', {}).get('text', '')
            if 'Suggestion:' in text_content or 'suggestion' in text_content.lower():
                suggestion_found = True
                # Verify suggestion is not empty
                assert len(text_content) > len('*Suggestion:* '), \
                    "Suggestion must have actual content"
                break
    
    assert suggestion_found, \
        f"Error type '{error_type}' must have a suggestion section"


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(
    invalid_command=st.text(min_size=1, max_size=50)
)
@settings(max_examples=20, deadline=None)
def test_invalid_commands_get_help_message(invalid_command):
    """
    Property 25: Action Failure Explanation
    
    For any invalid command, the error handler should provide
    a help message with available commands.
    
    Validates: Requirements 11.3
    """
    handler = ErrorHandler()
    
    # Get help message for invalid command
    message = handler.get_command_help_message(invalid_command)
    
    # Verify message structure
    assert message.text is not None and len(message.text) > 0
    assert message.blocks is not None and len(message.blocks) > 0
    
    # Verify help message contains command examples
    message_text = str(message.blocks)
    
    # Should mention available commands
    assert '/triage' in message_text, \
        "Help message must mention /triage commands"
    
    # Should have multiple command examples
    command_count = message_text.count('/triage')
    assert command_count >= 3, \
        f"Help message should show multiple commands, found {command_count}"


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(
    status_code=st.integers(min_value=400, max_value=599)
)
@settings(max_examples=20, deadline=None)
def test_http_errors_map_to_appropriate_error_types(status_code):
    """
    Property 25: Action Failure Explanation
    
    For any HTTP error status code, the error handler should
    map it to an appropriate error type with relevant suggestions.
    
    Validates: Requirements 11.3
    """
    handler = ErrorHandler()
    
    # Create error with status code
    error = TriageAPIError(
        message="Test error",
        status_code=status_code
    )
    
    # Handle error
    message = handler.handle_triage_api_error(error)
    
    # Verify message is generated
    assert message.text is not None
    assert message.blocks is not None
    
    # Verify appropriate error type based on status code
    message_text = str(message.blocks).lower()
    
    if status_code == 401:
        assert 'auth' in message_text or 'permission' in message_text
    elif status_code == 403:
        assert 'permission' in message_text or 'access' in message_text
    elif status_code == 404:
        assert 'not found' in message_text or 'resource' in message_text
    elif status_code == 429:
        assert 'rate' in message_text or 'limit' in message_text
    elif status_code >= 500:
        assert 'unavailable' in message_text or 'error' in message_text


# Feature: slack-integration, Property 25: Action Failure Explanation
@given(
    exception=st.sampled_from([
        ValueError("Invalid value"),
        KeyError("Missing key"),
        TypeError("Wrong type"),
        RuntimeError("Runtime error")
    ])
)
@settings(max_examples=20, deadline=None)
def test_generic_exceptions_have_fallback_explanation(exception):
    """
    Property 25: Action Failure Explanation
    
    For any unexpected exception, the error handler should provide
    a generic but helpful error message.
    
    Validates: Requirements 11.3
    """
    handler = ErrorHandler()
    
    # Handle generic error
    message = handler.handle_generic_error(exception)
    
    # Verify message structure
    assert message.text is not None and len(message.text) > 0
    assert message.blocks is not None and len(message.blocks) > 0
    
    # Verify has header
    block_types = [block.get('type') for block in message.blocks]
    assert 'header' in block_types
    
    # Verify has suggestion to try again or contact support
    message_text = str(message.blocks).lower()
    assert 'try again' in message_text or 'support' in message_text, \
        "Generic error should suggest trying again or contacting support"
