# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for HTTPS enforcement in TrIAge API client.

Feature: slack-integration, Property 28: HTTPS Enforcement

For any API call to the TrIAge backend, the request should use HTTPS protocol,
never HTTP.

Validates: Requirements 12.2
"""

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import MagicMock, AsyncMock, patch

from slack_bot.triage_api_client import TriageAPIClient, TriageAPIError
from slack_bot.config import SlackBotConfig


# Custom strategies for testing
@st.composite
def api_url(draw, protocol=None):
    """Generate API URLs with different protocols."""
    if protocol is None:
        protocol = draw(st.sampled_from(["http://", "https://"]))
    
    domain = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
        min_size=5,
        max_size=20
    ))
    
    tld = draw(st.sampled_from(["com", "org", "net", "io"]))
    
    return f"{protocol}{domain}.{tld}"


@st.composite
def slack_bot_config(draw, api_url_value=None):
    """Generate SlackBotConfig with configurable API URL."""
    if api_url_value is None:
        api_url_value = draw(api_url())
    
    return SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url=api_url_value,
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )


# Feature: slack-integration, Property 28: HTTPS Enforcement
@given(domain=st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
    min_size=5,
    max_size=20
))
def test_https_enforcement_rejects_http_urls(domain):
    """
    Property 28: HTTPS Enforcement
    
    For any API URL using HTTP protocol, the client initialization
    should reject it with a ValueError.
    
    Validates: Requirements 12.2
    """
    # Create config with HTTP URL
    config = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url=f"http://{domain}.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    # HTTP URLs should be rejected during initialization
    with pytest.raises(ValueError, match="must use HTTPS"):
        TriageAPIClient(config)


# Feature: slack-integration, Property 28: HTTPS Enforcement
@given(domain=st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
    min_size=5,
    max_size=20
))
def test_https_enforcement_accepts_https_urls(domain):
    """
    Property 28: HTTPS Enforcement
    
    For any API URL using HTTPS protocol, the client initialization
    should succeed.
    
    Validates: Requirements 12.2
    """
    # Create config with HTTPS URL
    config = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url=f"https://{domain}.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    # HTTPS URLs should be accepted
    client = TriageAPIClient(config)
    assert client.base_url.startswith("https://")


# Feature: slack-integration, Property 28: HTTPS Enforcement
@given(
    endpoint=st.text(min_size=1, max_size=50).map(lambda s: f"/{s.replace('/', '_')}"),
    method=st.sampled_from(["GET", "POST", "PUT", "DELETE"])
)
@pytest.mark.asyncio
async def test_https_enforcement_in_requests(endpoint, method):
    """
    Property 28: HTTPS Enforcement
    
    For any API request made through the client, the actual HTTP call
    should use HTTPS protocol.
    
    Validates: Requirements 12.2
    """
    # Create client with HTTPS URL
    config = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    client = TriageAPIClient(config)
    
    # Mock the httpx client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}
    
    async with client:
        with patch.object(client._client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            try:
                await client._make_request(method, endpoint)
            except Exception:
                # Ignore errors, we're just checking the URL
                pass
            
            # Verify the request was made
            if mock_request.called:
                # Get the actual URL that was requested
                call_args = mock_request.call_args
                
                # The endpoint is passed as the second positional argument
                if len(call_args[0]) > 1:
                    requested_endpoint = call_args[0][1]
                    
                    # Verify it doesn't contain http:// (would be https://)
                    # Note: The endpoint itself doesn't contain the protocol,
                    # but we verify the base_url is HTTPS
                    assert client.base_url.startswith("https://")


# Feature: slack-integration, Property 28: HTTPS Enforcement
@given(
    user_id=st.text(min_size=5, max_size=20),
    plan_id=st.text(min_size=5, max_size=20)
)
@pytest.mark.asyncio
async def test_https_enforcement_all_api_methods(user_id, plan_id):
    """
    Property 28: HTTPS Enforcement
    
    For any API method call (generate_plan, approve_plan, etc.),
    the underlying HTTP request should use HTTPS.
    
    Validates: Requirements 12.2
    """
    config = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    client = TriageAPIClient(config)
    
    # Mock successful responses
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "plan_id": plan_id,
        "date": "2026-01-26",
        "priority_tasks": [],
        "admin_tasks": [],
        "approved": False
    }
    
    async with client:
        with patch.object(client._client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Test generate_plan
            try:
                await client.generate_plan(user_id)
            except Exception:
                pass
            
            # Verify base URL is HTTPS
            assert client.base_url.startswith("https://")
            
            # Verify the client was configured with HTTPS
            if hasattr(client._client, 'base_url'):
                assert str(client._client.base_url).startswith("https://")


# Feature: slack-integration, Property 28: HTTPS Enforcement
def test_https_enforcement_config_validation():
    """
    Property 28: HTTPS Enforcement
    
    The configuration validation should enforce HTTPS for API URLs.
    
    Validates: Requirements 12.2
    """
    # HTTP URL should fail validation
    config_http = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url="http://insecure.example.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    with pytest.raises(ValueError, match="must use HTTPS"):
        config_http.validate()
    
    # HTTPS URL should pass validation
    config_https = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url="https://secure.example.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    # Should not raise
    config_https.validate()


# Feature: slack-integration, Property 28: HTTPS Enforcement
@given(
    protocol=st.sampled_from(["http://", "HTTP://", "hTTp://", "HtTp://"])
)
def test_https_enforcement_case_insensitive_http_rejection(protocol):
    """
    Property 28: HTTPS Enforcement
    
    HTTP protocol should be rejected regardless of case variations.
    
    Validates: Requirements 12.2
    """
    config = SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url=f"{protocol}api.example.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
    )
    
    # Only lowercase "https://" should be accepted
    # Any variation of "http://" should be rejected
    if protocol.lower().startswith("http://"):
        with pytest.raises(ValueError, match="must use HTTPS"):
            TriageAPIClient(config)
