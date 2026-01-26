# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for error logging completeness.

Feature: slack-integration, Property 26: Error Logging Completeness

**Validates: Requirements 11.5**
"""

import pytest
import logging
import json
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch
from io import StringIO

from slack_bot.logging_config import (
    JSONFormatter,
    LogContext,
    log_error_with_context,
    log_api_call
)
from slack_bot.triage_api_client import TriageAPIError
from slack_bot.slack_api_client import SlackAPIRetryError


# Custom strategies
@st.composite
def log_level(draw):
    """Generate valid log levels."""
    return draw(st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']))


@st.composite
def exception_with_context(draw):
    """Generate exceptions with various attributes."""
    exc_type = draw(st.sampled_from([
        ValueError, KeyError, TypeError, RuntimeError
    ]))
    message = draw(st.text(min_size=10, max_size=100))
    
    exc = exc_type(message)
    
    # Add optional attributes
    if draw(st.booleans()):
        exc.status_code = draw(st.integers(min_value=400, max_value=599))
    if draw(st.booleans()):
        exc.response_body = draw(st.text(max_size=200))
    if draw(st.booleans()):
        exc.attempts = draw(st.integers(min_value=1, max_value=5))
    
    return exc


@st.composite
def context_dict(draw):
    """Generate context dictionaries with non-reserved keys."""
    # Reserved LogRecord attributes that must be avoided
    reserved_attrs = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
        'levelno', 'lineno', 'module', 'msecs', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
        'exc_text', 'stack_info', 'getMessage', 'message', 'asctime'
    }
    
    # Generate keys that don't conflict with reserved attributes
    # Must start with a letter to avoid numeric-only keys
    keys = draw(st.lists(
        st.text(
            min_size=2,  # Minimum 2 chars
            max_size=20,
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))
        ).filter(lambda k: (
            k not in reserved_attrs and 
            not k.startswith('_') and
            k[0].isalpha()  # Must start with a letter
        )),
        min_size=1,
        max_size=5,
        unique=True
    ))
    
    context = {}
    for key in keys:
        value = draw(st.one_of(
            st.text(max_size=50),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans()
        ))
        context[key] = value
    
    return context


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    level=log_level(),
    message=st.text(min_size=10, max_size=200),
    context=context_dict()
)
@settings(max_examples=20, deadline=None)
def test_json_formatter_includes_all_required_fields(level, message, context):
    """
    Property 26: Error Logging Completeness
    
    For any log record, the JSON formatter should include all required fields:
    timestamp, level, logger, message, module, function, line.
    
    Validates: Requirements 11.5
    """
    # Create logger and formatter
    logger = logging.getLogger('test_logger')
    formatter = JSONFormatter()
    
    # Create log record
    record = logger.makeRecord(
        name='test_logger',
        level=getattr(logging, level),
        fn='test_file.py',
        lno=42,
        msg=message,
        args=(),
        exc_info=None,
        func='test_function',
        extra=context
    )
    
    # Format record
    formatted = formatter.format(record)
    
    # Parse JSON
    log_data = json.loads(formatted)
    
    # Verify required fields
    required_fields = ['timestamp', 'level', 'logger', 'message', 'module', 'function', 'line']
    for field in required_fields:
        assert field in log_data, f"Log record must include '{field}' field"
        assert log_data[field] is not None, f"Field '{field}' must not be None"
    
    # Verify level matches
    assert log_data['level'] == level
    
    # Verify message matches
    assert log_data['message'] == message
    
    # Verify context fields are included
    for key, value in context.items():
        if key not in ['message', 'asctime']:  # Reserved fields
            assert key in log_data, f"Context field '{key}' should be included"


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    exception=exception_with_context(),
    context=context_dict()
)
@settings(max_examples=20, deadline=None)
def test_error_logs_include_exception_info(exception, context):
    """
    Property 26: Error Logging Completeness
    
    For any error log with an exception, the log should include
    exception type, message, and stack trace.
    
    Validates: Requirements 11.5
    """
    # Create logger and formatter
    logger = logging.getLogger('test_logger')
    formatter = JSONFormatter()
    
    # Create log record with exception
    try:
        raise exception
    except Exception:
        import sys
        exc_info = sys.exc_info()
        
        record = logger.makeRecord(
            name='test_logger',
            level=logging.ERROR,
            fn='test_file.py',
            lno=42,
            msg='Error occurred',
            args=(),
            exc_info=exc_info,
            func='test_function',
            extra=context
        )
    
    # Format record
    formatted = formatter.format(record)
    
    # Parse JSON
    log_data = json.loads(formatted)
    
    # Verify exception fields
    assert 'exception' in log_data, "Error log must include exception field"
    assert 'exception_type' in log_data, "Error log must include exception_type field"
    assert 'stack_trace' in log_data, "Error log must include stack_trace field"
    
    # Verify exception type matches
    assert log_data['exception_type'] == type(exception).__name__
    
    # Verify stack trace is not empty
    assert len(log_data['stack_trace']) > 0


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    context=context_dict()
)
@settings(max_examples=20, deadline=None)
def test_log_context_manager_adds_context_to_all_logs(context):
    """
    Property 26: Error Logging Completeness
    
    For any log context, all logs within the context should
    include the context fields.
    
    Validates: Requirements 11.5
    """
    # Create logger and capture output
    logger = logging.getLogger('test_context_logger')
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Add string handler
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log with context
    with LogContext(**context):
        logger.info("Test message")
    
    # Parse output
    output = stream.getvalue()
    log_data = json.loads(output.strip())
    
    # Verify context fields are present
    for key, value in context.items():
        if key not in ['message', 'asctime']:  # Reserved fields
            assert key in log_data, f"Context field '{key}' should be in log"
            # Convert both to strings for comparison (JSON serialization)
            assert str(log_data[key]) == str(value), \
                f"Context field '{key}' value mismatch"


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    error=exception_with_context(),
    context=context_dict()
)
@settings(max_examples=20, deadline=None)
def test_log_error_with_context_includes_all_error_attributes(error, context):
    """
    Property 26: Error Logging Completeness
    
    For any error logged with context, the log should include
    error type, message, and any error-specific attributes.
    
    Validates: Requirements 11.5
    """
    # Create logger and capture output
    logger = logging.getLogger('test_error_logger')
    logger.setLevel(logging.ERROR)
    logger.handlers = []
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log error with context
    log_error_with_context(
        logger,
        "Test error message",
        error,
        **context
    )
    
    # Parse output
    output = stream.getvalue()
    log_data = json.loads(output.strip())
    
    # Verify error fields
    assert 'error_type' in log_data
    assert 'error_message' in log_data
    assert log_data['error_type'] == type(error).__name__
    assert log_data['error_message'] == str(error)
    
    # Verify error-specific attributes
    if hasattr(error, 'status_code'):
        assert 'status_code' in log_data
        assert log_data['status_code'] == error.status_code
    
    if hasattr(error, 'attempts'):
        assert 'retry_attempts' in log_data
        assert log_data['retry_attempts'] == error.attempts
    
    # Verify context fields
    for key, value in context.items():
        if key not in ['message', 'asctime']:
            assert key in log_data


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    api_name=st.sampled_from(['TrIAge', 'Slack']),
    method=st.sampled_from(['GET', 'POST', 'PUT', 'DELETE']),
    endpoint=st.text(min_size=1, max_size=50),
    duration_ms=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    status_code=st.integers(min_value=200, max_value=599),
    success=st.booleans()
)
@settings(max_examples=20, deadline=None)
def test_api_call_logs_include_timing_and_status(
    api_name, method, endpoint, duration_ms, status_code, success
):
    """
    Property 26: Error Logging Completeness
    
    For any API call log, the log should include API name, method,
    endpoint, duration, status code, and success flag.
    
    Validates: Requirements 11.5
    """
    # Create logger and capture output
    logger = logging.getLogger('test_api_logger')
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log API call
    log_api_call(
        logger,
        api_name=api_name,
        method=method,
        endpoint=endpoint,
        duration_ms=duration_ms,
        status_code=status_code,
        success=success
    )
    
    # Parse output
    output = stream.getvalue()
    log_data = json.loads(output.strip())
    
    # Verify API call fields
    assert 'api_name' in log_data
    assert 'method' in log_data
    assert 'endpoint' in log_data
    assert 'duration_ms' in log_data
    assert 'status_code' in log_data
    assert 'success' in log_data
    
    # Verify values match
    assert log_data['api_name'] == api_name
    assert log_data['method'] == method
    assert log_data['endpoint'] == endpoint
    assert abs(log_data['duration_ms'] - duration_ms) < 0.01
    assert log_data['status_code'] == status_code
    assert log_data['success'] == success


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    user_id=st.text(min_size=5, max_size=20),
    team_id=st.text(min_size=5, max_size=20),
    event_id=st.text(min_size=10, max_size=50)
)
@settings(max_examples=20, deadline=None)
def test_slack_specific_context_fields_are_logged(user_id, team_id, event_id):
    """
    Property 26: Error Logging Completeness
    
    For any Slack-related log, Slack-specific context fields
    (user_id, team_id, event_id) should be included.
    
    Validates: Requirements 11.5
    """
    # Create logger and capture output
    logger = logging.getLogger('test_slack_logger')
    logger.setLevel(logging.INFO)
    logger.handlers = []
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Log with Slack context
    with LogContext(user_id=user_id, team_id=team_id, event_id=event_id):
        logger.info("Processing Slack event")
    
    # Parse output
    output = stream.getvalue()
    log_data = json.loads(output.strip())
    
    # Verify Slack fields
    assert 'user_id' in log_data
    assert 'team_id' in log_data
    assert 'event_id' in log_data
    
    assert log_data['user_id'] == user_id
    assert log_data['team_id'] == team_id
    assert log_data['event_id'] == event_id


# Feature: slack-integration, Property 26: Error Logging Completeness
@given(
    message=st.text(min_size=10, max_size=200)
)
@settings(max_examples=20, deadline=None)
def test_logs_are_valid_json(message):
    """
    Property 26: Error Logging Completeness
    
    For any log message, the formatted output should be valid JSON
    that can be parsed.
    
    Validates: Requirements 11.5
    """
    # Create logger and formatter
    logger = logging.getLogger('test_json_logger')
    formatter = JSONFormatter()
    
    # Create log record
    record = logger.makeRecord(
        name='test_json_logger',
        level=logging.INFO,
        fn='test_file.py',
        lno=42,
        msg=message,
        args=(),
        exc_info=None,
        func='test_function'
    )
    
    # Format record
    formatted = formatter.format(record)
    
    # Verify it's valid JSON
    try:
        log_data = json.loads(formatted)
        assert isinstance(log_data, dict), "Formatted log must be a JSON object"
    except json.JSONDecodeError as e:
        pytest.fail(f"Formatted log is not valid JSON: {e}")
