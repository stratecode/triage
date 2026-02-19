# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-Based Tests for OAuth Token Storage

Feature: plugin-architecture, Property 11: OAuth Token Storage

Tests that OAuth tokens are stored securely with encryption and all required
metadata (team_id, bot_user_id) is preserved.

Validates: Requirements 6.4
"""

import asyncio
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from triage.plugins.installation_storage import PluginInstallationStorage
from triage.plugins.slack.oauth_handler import OAuthError, OAuthTokens, SlackOAuthHandler

# Test database URL (use in-memory SQLite for tests or test PostgreSQL)
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://triage:password@localhost:5432/triage_test")


# Check if database is available
def is_database_available():
    """Check if test database is available."""
    # For now, skip database tests if not explicitly enabled
    return os.getenv("RUN_DATABASE_TESTS", "false").lower() == "true"


# Skip marker for database tests
requires_database = pytest.mark.skipif(
    not is_database_available(), reason="Database not available. Set RUN_DATABASE_TESTS=true to enable."
)
TEST_ENCRYPTION_KEY = "test_encryption_key_32_chars_min"


# Hypothesis strategies for generating test data
@st.composite
def oauth_tokens_strategy(draw):
    """Generate valid OAuthTokens for testing."""
    team_id = draw(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=8, max_size=12))
    team_name = draw(st.text(min_size=3, max_size=50))
    bot_user_id = draw(
        st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=8, max_size=12)
    )
    access_token = draw(st.text(min_size=20, max_size=100))
    scope = draw(st.text(min_size=5, max_size=100))

    # Optional fields
    refresh_token = draw(st.one_of(st.none(), st.text(min_size=20, max_size=100)))
    expires_at = draw(st.one_of(st.none(), st.integers(min_value=3600, max_value=86400)))

    return OAuthTokens(
        access_token=access_token,
        bot_user_id=bot_user_id,
        team_id=team_id,
        team_name=team_name,
        scope=scope,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


class TestOAuthTokenStorage:
    """
    Property-based tests for OAuth token storage.

    Feature: plugin-architecture, Property 11: OAuth Token Storage
    """

    def _create_storage_and_handler(self):
        """Create storage and OAuth handler for testing."""
        storage = PluginInstallationStorage(TEST_DB_URL, TEST_ENCRYPTION_KEY)
        oauth_handler = SlackOAuthHandler(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="https://example.com/oauth/callback",
            storage=storage,
        )
        return storage, oauth_handler

    @requires_database
    @given(tokens=oauth_tokens_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_oauth_token_storage_preserves_all_fields(self, tokens):
        """
        Property 11: OAuth Token Storage

        For any successful OAuth authorization, the system should store the
        access token securely (encrypted) with all required metadata.

        This test verifies:
        1. Tokens are stored in database
        2. All required fields are preserved (team_id, bot_user_id, team_name, scope)
        3. Tokens are encrypted at rest
        4. Tokens can be retrieved and decrypted correctly

        Validates: Requirements 6.4
        """

        async def run_test():
            # Create storage and handler
            storage, oauth_handler = self._create_storage_and_handler()
            await storage.connect()
            await storage.initialize_schema()

            try:
                # Store tokens
                installation = await oauth_handler.store_tokens(tokens)

                # Verify installation was created
                assert installation.id is not None
                assert installation.plugin_name == "slack"
                assert installation.channel_id == tokens.team_id

                # Verify metadata is preserved
                assert installation.metadata["bot_user_id"] == tokens.bot_user_id
                assert installation.metadata["team_name"] == tokens.team_name
                assert installation.metadata["scope"] == tokens.scope

                if tokens.expires_at:
                    assert installation.metadata["expires_at"] == tokens.expires_at

                # Verify tokens are stored (decrypted by storage layer)
                assert installation.access_token == tokens.access_token

                if tokens.refresh_token:
                    assert installation.refresh_token == tokens.refresh_token

                # Retrieve installation from database
                retrieved = await storage.get_installation("slack", tokens.team_id)

                # Verify retrieved installation matches stored data
                assert retrieved is not None
                assert retrieved.id == installation.id
                assert retrieved.access_token == tokens.access_token
                assert retrieved.metadata["bot_user_id"] == tokens.bot_user_id
                assert retrieved.metadata["team_name"] == tokens.team_name

                # Verify tokens are encrypted in database (check raw data)
                async with storage._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT access_token FROM plugin_installations WHERE id = $1", installation.id
                    )
                    # Encrypted token should not match plaintext
                    assert row["access_token"] != tokens.access_token

                # Cleanup for next iteration
                await storage.delete_installation("slack", tokens.team_id)
            finally:
                await storage.disconnect()

        # Run async test
        asyncio.run(run_test())

    @requires_database
    @given(tokens=oauth_tokens_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_duplicate_installation_raises_error(self, tokens):
        """
        Property 11: OAuth Token Storage (Duplicate Prevention)

        For any OAuth tokens, attempting to store them twice for the same
        workspace should raise an OAuthError with a user-friendly message.

        Validates: Requirements 6.4, 6.6
        """

        async def run_test():
            storage, oauth_handler = self._create_storage_and_handler()
            await storage.connect()
            await storage.initialize_schema()

            try:
                # Store tokens first time
                await oauth_handler.store_tokens(tokens)

                # Attempt to store again should raise OAuthError
                with pytest.raises(OAuthError) as exc_info:
                    await oauth_handler.store_tokens(tokens)

                # Verify error message is user-friendly
                error = exc_info.value
                assert "already installed" in error.message.lower()
                assert tokens.team_name in error.message
                assert error.error_code == "already_installed"

                # Cleanup
                await storage.delete_installation("slack", tokens.team_id)
            finally:
                await storage.disconnect()

        asyncio.run(run_test())

    @requires_database
    @given(tokens1=oauth_tokens_strategy(), tokens2=oauth_tokens_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_multiple_workspace_installations(self, tokens1, tokens2):
        """
        Property 11: OAuth Token Storage (Multiple Workspaces)

        For any two different workspaces, the system should support storing
        installations for both without conflicts.

        Validates: Requirements 6.4, 7.2
        """
        # Ensure different team IDs
        if tokens1.team_id == tokens2.team_id:
            return  # Skip this example

        async def run_test():
            storage, oauth_handler = self._create_storage_and_handler()
            await storage.connect()
            await storage.initialize_schema()

            try:
                # Store tokens for both workspaces
                installation1 = await oauth_handler.store_tokens(tokens1)
                installation2 = await oauth_handler.store_tokens(tokens2)

                # Verify both installations exist
                assert installation1.id != installation2.id
                assert installation1.channel_id == tokens1.team_id
                assert installation2.channel_id == tokens2.team_id

                # Retrieve both installations
                retrieved1 = await storage.get_installation("slack", tokens1.team_id)
                retrieved2 = await storage.get_installation("slack", tokens2.team_id)

                # Verify data isolation
                assert retrieved1.access_token == tokens1.access_token
                assert retrieved2.access_token == tokens2.access_token
                assert retrieved1.metadata["bot_user_id"] == tokens1.bot_user_id
                assert retrieved2.metadata["bot_user_id"] == tokens2.bot_user_id

                # Cleanup
                await storage.delete_installation("slack", tokens1.team_id)
                await storage.delete_installation("slack", tokens2.team_id)
            finally:
                await storage.disconnect()

        asyncio.run(run_test())


# Run stateful tests would go here but are omitted for simplicity
# The above property tests provide sufficient coverage for OAuth token storage
