# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-Based Tests for OAuth Error Handling

Feature: plugin-architecture, Property 12: OAuth Error Handling

Tests that OAuth authorization failures return clear, actionable error messages
without exposing internal details.

Validates: Requirements 6.6
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from triage.plugins.slack.oauth_handler import OAuthError, SlackOAuthHandler

# Hypothesis strategies for error scenarios
slack_error_codes = st.sampled_from(
    [
        "invalid_code",
        "code_already_used",
        "invalid_client_id",
        "invalid_client_secret",
        "invalid_redirect_uri",
        "invalid_grant_type",
        "invalid_refresh_token",
        "token_revoked",
        "access_denied",
        "unknown_error",
        "random_error_code",
    ]
)


@st.composite
def http_error_strategy(draw):
    """Generate HTTP errors for testing."""
    status_code = draw(st.sampled_from([400, 401, 403, 404, 500, 502, 503, 504]))
    return httpx.HTTPStatusError(
        message=f"HTTP {status_code}", request=MagicMock(), response=MagicMock(status_code=status_code)
    )


class TestOAuthErrorHandling:
    """
    Property-based tests for OAuth error handling.

    Feature: plugin-architecture, Property 12: OAuth Error Handling
    """

    def _create_oauth_handler(self):
        """Create OAuth handler for testing."""
        storage = MagicMock()
        return SlackOAuthHandler(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="https://example.com/oauth/callback",
            storage=storage,
        )

    @given(error_code=slack_error_codes)
    @settings(max_examples=100, deadline=3000)
    def test_slack_api_errors_return_user_friendly_messages(self, error_code):
        """
        Property 12: OAuth Error Handling

        For any Slack API error code, the system should return a clear,
        actionable error message without exposing internal implementation details.

        Validates: Requirements 6.6
        """

        async def run_test():
            oauth_handler = self._create_oauth_handler()

            mock_response = {"ok": False, "error": error_code, "error_description": "Internal technical details"}

            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = AsyncMock(json=lambda: mock_response, raise_for_status=lambda: None)

                with pytest.raises(OAuthError) as exc_info:
                    await oauth_handler.exchange_code_for_token("test_code")

                error = exc_info.value
                assert error.message is not None
                assert len(error.message) > 0
                assert "test_client_secret" not in error.message
                assert error.error_code == error_code

                actionable_words = ["try", "again", "contact", "support", "reinstall", "install"]
                assert any(word in error.message.lower() for word in actionable_words)

        asyncio.run(run_test())

    def test_error_messages_are_consistent(self):
        """Verify all error messages are professional and consistent."""
        oauth_handler = self._create_oauth_handler()

        error_codes = [
            "invalid_code",
            "code_already_used",
            "invalid_client_id",
            "invalid_client_secret",
            "invalid_redirect_uri",
            "invalid_grant_type",
            "invalid_refresh_token",
            "token_revoked",
            "access_denied",
        ]

        for error_code in error_codes:
            message = oauth_handler._get_user_friendly_error_message(error_code)
            assert message is not None
            assert len(message) > 10
            assert message[0].isupper()
            assert message[-1] in [".", "!", "?"]
