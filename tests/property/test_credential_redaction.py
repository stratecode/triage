# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for credential redaction in logs.

Feature: slack-integration, Property 29: Credential Redaction

For any JIRA credential (password, API token) handled by the system,
it should never appear in log files or Slack messages.

Validates: Requirements 12.3
"""

import logging
import io
from hypothesis import given, strategies as st, settings
from slack_bot.logging_config import SensitiveDataFilter, JSONFormatter


# Custom strategies for generating sensitive data
@st.composite
def slack_token(draw):
    """Generate realistic Slack token with ASCII characters only."""
    prefix = draw(st.sampled_from(['xoxb', 'xoxp', 'xoxa', 'xoxr']))
    # Use only ASCII alphanumeric characters for the token part
    token_part = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        min_size=20,
        max_size=50
    ))
    return f"{prefix}-{token_part}"


@st.composite
def jira_credentials(draw):
    """Generate JIRA credentials."""
    email = draw(st.emails())
    password = draw(st.text(min_size=8, max_size=32))
    api_token = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=20,
        max_size=40
    ))
    return {
        'email': email,
        'password': password,
        'api_token': api_token
    }


@st.composite
def bearer_token(draw):
    """Generate Bearer token."""
    token = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-',
        min_size=20,
        max_size=50
    ))
    return f"Bearer {token}"


@st.composite
def sensitive_dict(draw):
    """Generate dictionary with sensitive fields."""
    return {
        'password': draw(st.text(min_size=8, max_size=32)),
        'api_token': draw(st.text(min_size=20, max_size=40)),
        'secret': draw(st.text(min_size=16, max_size=32)),
        'jira_password': draw(st.text(min_size=8, max_size=32)),
        'jira_api_token': draw(st.text(min_size=20, max_size=40)),
        'access_token': draw(st.text(min_size=20, max_size=40)),
        'client_secret': draw(st.text(min_size=16, max_size=32)),
    }


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(token=slack_token())
def test_slack_tokens_are_redacted(token):
    """
    Property: For any Slack token in a log message, the token should be
    redacted and never appear in the log output.
    
    Validates: Requirements 12.3
    """
    # Create a log record with Slack token
    logger = logging.getLogger('test_slack_token')
    logger.setLevel(logging.INFO)
    
    # Create string buffer to capture log output
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message containing token
    logger.info(f"Slack token: {token}")
    
    # Get log output
    log_output = log_stream.getvalue()
    
    # Verify token is not in output
    assert token not in log_output, f"Slack token {token} was not redacted from logs"
    # Check for redaction marker (REDACTED_BOT_TOKEN, REDACTED_USER_TOKEN, etc.)
    assert 'REDACTED' in log_output or token[:4] not in log_output, "Token was not properly redacted"
    
    # Cleanup
    logger.removeHandler(handler)


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(creds=jira_credentials())
def test_jira_credentials_are_redacted(creds):
    """
    Property: For any JIRA credentials (password, API token) in a log message,
    they should be redacted and never appear in the log output.
    
    Validates: Requirements 12.3
    """
    logger = logging.getLogger('test_jira_creds')
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message with JIRA credentials
    logger.info(
        "JIRA login",
        extra={
            'jira_email': creds['email'],
            'jira_password': creds['password'],
            'jira_api_token': creds['api_token']
        }
    )
    
    log_output = log_stream.getvalue()
    
    # Verify credentials are not in output
    assert creds['password'] not in log_output, "JIRA password was not redacted"
    assert creds['api_token'] not in log_output, "JIRA API token was not redacted"
    
    # Email should still be present (not sensitive)
    assert creds['email'] in log_output, "Email was incorrectly redacted"
    
    logger.removeHandler(handler)


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(token=bearer_token())
def test_bearer_tokens_are_redacted(token):
    """
    Property: For any Bearer token in a log message, the token should be
    redacted and never appear in the log output.
    
    Validates: Requirements 12.3
    """
    logger = logging.getLogger('test_bearer_token')
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message with Bearer token
    logger.info(f"Authorization: {token}")
    
    log_output = log_stream.getvalue()
    
    # Verify token is not in output (but "Bearer" prefix might be)
    token_value = token.split(' ')[1]
    assert token_value not in log_output, f"Bearer token value was not redacted"
    
    logger.removeHandler(handler)


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(sensitive=sensitive_dict())
def test_sensitive_dict_fields_are_redacted(sensitive):
    """
    Property: For any dictionary with sensitive field names (password, token,
    secret, etc.), those field values should be redacted in log output.
    
    Validates: Requirements 12.3
    """
    logger = logging.getLogger('test_sensitive_dict')
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message with sensitive dictionary
    logger.info("User config", extra=sensitive)
    
    log_output = log_stream.getvalue()
    
    # Verify all sensitive values are redacted
    for key, value in sensitive.items():
        assert value not in log_output, f"Sensitive field '{key}' value was not redacted"
    
    logger.removeHandler(handler)


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(
    password=st.text(min_size=8, max_size=32),
    message=st.text(min_size=10, max_size=100)
)
def test_json_password_fields_are_redacted(password, message):
    """
    Property: For any JSON string containing password fields, the password
    values should be redacted in log output.
    
    Validates: Requirements 12.3
    """
    logger = logging.getLogger('test_json_password')
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message with JSON-like password field
    json_like = f'{{"password": "{password}", "message": "{message}"}}'
    logger.info(f"Request body: {json_like}")
    
    log_output = log_stream.getvalue()
    
    # Verify password is redacted
    assert password not in log_output, "Password in JSON was not redacted"
    
    # Message should still be present
    assert message in log_output, "Non-sensitive field was incorrectly redacted"
    
    logger.removeHandler(handler)


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(
    email=st.emails(),
    password=st.text(min_size=8, max_size=32)
)
def test_email_password_pairs_are_redacted(email, password):
    """
    Property: For any email:password pair (common in JIRA auth), the password
    should be redacted while preserving the email.
    
    Validates: Requirements 12.3
    """
    logger = logging.getLogger('test_email_password')
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message with email:password format
    auth_string = f"{email}:{password}"
    logger.info(f"JIRA auth: {auth_string}")
    
    log_output = log_stream.getvalue()
    
    # Verify password is redacted but email is preserved
    assert password not in log_output, "Password in email:password pair was not redacted"
    assert email in log_output, "Email was incorrectly redacted"
    
    logger.removeHandler(handler)


# Feature: slack-integration, Property 29: Credential Redaction
@settings(max_examples=50)
@given(
    nested_sensitive=st.fixed_dictionaries({
        'user': st.fixed_dictionaries({
            'name': st.text(min_size=3, max_size=20),
            'credentials': st.fixed_dictionaries({
                'password': st.text(min_size=8, max_size=32),
                'api_token': st.text(min_size=20, max_size=40)
            })
        })
    })
)
def test_nested_sensitive_fields_are_redacted(nested_sensitive):
    """
    Property: For any nested dictionary structure with sensitive fields,
    all sensitive values should be redacted regardless of nesting level.
    
    Validates: Requirements 12.3
    """
    logger = logging.getLogger('test_nested_sensitive')
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    
    # Log message with nested sensitive data
    logger.info("User data", extra=nested_sensitive)
    
    log_output = log_stream.getvalue()
    
    # Verify nested sensitive values are redacted
    password = nested_sensitive['user']['credentials']['password']
    api_token = nested_sensitive['user']['credentials']['api_token']
    username = nested_sensitive['user']['name']
    
    assert password not in log_output, "Nested password was not redacted"
    assert api_token not in log_output, "Nested API token was not redacted"
    assert username in log_output, "Non-sensitive nested field was incorrectly redacted"
    
    logger.removeHandler(handler)
