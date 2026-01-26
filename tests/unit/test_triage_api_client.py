# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for TrIAge API client.

Tests authentication, error handling, and retry logic for the API client
that communicates with the TrIAge backend.

Validates: Requirements 11.2, 12.2
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
import httpx

from slack_bot.triage_api_client import TriageAPIClient, TriageAPIError
from slack_bot.config import SlackBotConfig


@pytest.fixture
def config():
    """Create test configuration."""
    return SlackBotConfig(
        slack_bot_token="xoxb-test-token-12345",
        slack_signing_secret="test-signing-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test-api-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
        max_retries=3,
        retry_backoff_base=2.0
    )


@pytest.fixture
def api_client(config):
    """Create API client instance."""
    return TriageAPIClient(config)


class TestAuthentication:
    """Tests for authentication header inclusion."""
    
    @pytest.mark.asyncio
    async def test_auth_header_included(self, api_client):
        """
        Test that authentication header is included in all requests.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                await api_client._make_request("GET", "/test")
                
                # Verify request was made
                assert mock_request.called
                
                # Verify auth headers were set during client initialization
                assert "Authorization" in api_client._get_auth_headers()
                assert api_client._get_auth_headers()["Authorization"].startswith("Bearer ")
    
    @pytest.mark.asyncio
    async def test_bearer_token_format(self, api_client):
        """Test that bearer token is correctly formatted."""
        headers = api_client._get_auth_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {api_client.api_token}"
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers


class TestErrorHandling:
    """Tests for HTTP error handling."""
    
    @pytest.mark.asyncio
    async def test_401_unauthorized_error(self, api_client):
        """
        Test handling of 401 authentication error.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError) as exc_info:
                    await api_client._make_request("GET", "/test")
                
                assert exc_info.value.status_code == 401
                assert "401" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_403_forbidden_error(self, api_client):
        """
        Test handling of 403 forbidden error.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError) as exc_info:
                    await api_client._make_request("GET", "/test")
                
                assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_404_not_found_error(self, api_client):
        """
        Test handling of 404 not found error.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError) as exc_info:
                    await api_client._make_request("GET", "/test")
                
                assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_503_service_unavailable_error(self, api_client):
        """
        Test handling of 503 service unavailable error with retry.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError) as exc_info:
                    await api_client._make_request("GET", "/test")
                
                # Should have retried max_retries times
                assert mock_request.call_count == api_client.max_retries + 1
                assert exc_info.value.status_code == 503


class TestRetryLogic:
    """Tests for exponential backoff retry logic."""
    
    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, api_client):
        """
        Test retry logic on 500 server error.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError):
                    await api_client._make_request("GET", "/test")
                
                # Should retry max_retries times (3) + initial attempt = 4 total
                assert mock_request.call_count == api_client.max_retries + 1
    
    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self, api_client):
        """
        Test retry logic on 429 rate limit error.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError):
                    await api_client._make_request("GET", "/test")
                
                # Should retry
                assert mock_request.call_count == api_client.max_retries + 1
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, api_client):
        """
        Test retry logic on timeout error.
        
        Validates: Requirements 11.2
        """
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = httpx.TimeoutException("Request timeout")
                
                with pytest.raises(TriageAPIError) as exc_info:
                    await api_client._make_request("GET", "/test")
                
                # Should retry
                assert mock_request.call_count == api_client.max_retries + 1
                assert "retries" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, api_client):
        """
        Test retry logic on network error.
        
        Validates: Requirements 11.2
        """
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = httpx.NetworkError("Connection failed")
                
                with pytest.raises(TriageAPIError):
                    await api_client._make_request("GET", "/test")
                
                # Should retry
                assert mock_request.call_count == api_client.max_retries + 1
    
    @pytest.mark.asyncio
    async def test_successful_retry_after_failure(self, api_client):
        """
        Test successful request after initial failure.
        
        Validates: Requirements 11.2
        """
        # First call fails, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 503
        mock_response_fail.text = "Service Unavailable"
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"status": "ok"}
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = [mock_response_fail, mock_response_success]
                
                response = await api_client._make_request("GET", "/test")
                
                # Should have retried once and succeeded
                assert mock_request.call_count == 2
                assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(self, api_client):
        """
        Test that 400 errors are not retried.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with pytest.raises(TriageAPIError):
                    await api_client._make_request("GET", "/test")
                
                # Should NOT retry on 400
                assert mock_request.call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, api_client):
        """
        Test that retry delays follow exponential backoff.
        
        Validates: Requirements 11.2
        """
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    with pytest.raises(TriageAPIError):
                        await api_client._make_request("GET", "/test")
                    
                    # Verify sleep was called for retries
                    assert mock_sleep.call_count == api_client.max_retries
                    
                    # Verify backoff increases (approximately)
                    sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
                    for i in range(len(sleep_times) - 1):
                        # Each sleep should be longer than the previous (with jitter tolerance)
                        assert sleep_times[i+1] > sleep_times[i] * 0.9


class TestAPIMethodCalls:
    """Tests for specific API method calls."""
    
    @pytest.mark.asyncio
    async def test_generate_plan_success(self, api_client):
        """Test successful plan generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "plan_id": "plan123",
            "date": "2026-01-26",
            "priority_tasks": [],
            "admin_tasks": [],
            "approved": False
        }
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                plan = await api_client.generate_plan("user123")
                
                assert plan.plan_id == "plan123"
                assert len(plan.priority_tasks) == 0
                assert not plan.approved
    
    @pytest.mark.asyncio
    async def test_approve_plan_success(self, api_client):
        """Test successful plan approval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "approved"}
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                result = await api_client.approve_plan("plan123", "user123")
                
                assert result["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_reject_plan_with_reason(self, api_client):
        """Test plan rejection with reason."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "rejected"}
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                result = await api_client.reject_plan("plan123", "user123", "Too many tasks")
                
                assert result["status"] == "rejected"
    
    @pytest.mark.asyncio
    async def test_submit_feedback_success(self, api_client):
        """Test feedback submission."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "feedback_received"}
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                result = await api_client.submit_feedback("plan123", "user123", "Need more time")
                
                assert result["status"] == "feedback_received"
    
    @pytest.mark.asyncio
    async def test_get_config_success(self, api_client):
        """Test user configuration retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": "user123",
            "notification_channel": "DM",
            "delivery_time": "09:00",
            "notifications_enabled": True,
            "timezone": "UTC"
        }
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                config = await api_client.get_config("user123")
                
                assert config.user_id == "user123"
                assert config.notification_channel == "DM"
                assert config.notifications_enabled
    
    @pytest.mark.asyncio
    async def test_update_config_success(self, api_client):
        """Test user configuration update."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": "user123",
            "notification_channel": "C12345",
            "delivery_time": "10:00",
            "notifications_enabled": False,
            "timezone": "America/New_York"
        }
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                config = await api_client.update_config(
                    "user123",
                    notification_channel="C12345",
                    delivery_time="10:00",
                    notifications_enabled=False
                )
                
                assert config.notification_channel == "C12345"
                assert not config.notifications_enabled
    
    @pytest.mark.asyncio
    async def test_create_user_mapping_success(self, api_client):
        """Test user mapping creation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "created", "user_id": "user123"}
        
        async with api_client:
            with patch.object(api_client._client, 'request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                result = await api_client.create_user_mapping(
                    "U12345",
                    "T12345",
                    "user@example.com"
                )
                
                assert result["status"] == "created"


class TestHTTPSEnforcement:
    """Tests for HTTPS enforcement."""
    
    def test_https_required_in_config(self):
        """
        Test that HTTP URLs are rejected in configuration.
        
        Validates: Requirements 12.2
        """
        with pytest.raises(ValueError, match="must use HTTPS"):
            TriageAPIClient(SlackBotConfig(
                slack_bot_token="xoxb-test-token-12345",
                slack_signing_secret="test-signing-secret",
                slack_client_id="test-client-id",
                slack_client_secret="test-client-secret",
                triage_api_url="http://insecure.example.com",
                triage_api_token="test-api-token",
                redis_url="redis://localhost:6379",
                database_url="postgresql://localhost/test",
                encryption_key="a" * 32,
            ))
    
    def test_https_accepted_in_config(self):
        """
        Test that HTTPS URLs are accepted in configuration.
        
        Validates: Requirements 12.2
        """
        client = TriageAPIClient(SlackBotConfig(
            slack_bot_token="xoxb-test-token-12345",
            slack_signing_secret="test-signing-secret",
            slack_client_id="test-client-id",
            slack_client_secret="test-client-secret",
            triage_api_url="https://secure.example.com",
            triage_api_token="test-api-token",
            redis_url="redis://localhost:6379",
            database_url="postgresql://localhost/test",
            encryption_key="a" * 32,
        ))
        
        assert client.base_url.startswith("https://")
