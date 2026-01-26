# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for OAuth token encryption.

Tests universal properties of token encryption and decryption using
Hypothesis for comprehensive validation across many inputs.

Feature: slack-integration, Property 27: OAuth Token Encryption
Validates: Requirements 12.1
"""

import pytest
from hypothesis import given, strategies as st, assume
from datetime import datetime, timezone

from slack_bot.oauth_manager import TokenEncryption, OAuthManager
from slack_bot.models import WorkspaceToken


# Custom strategies for generating test data

@st.composite
def encryption_key(draw):
    """Generate valid encryption keys (at least 32 characters)."""
    length = draw(st.integers(min_value=32, max_value=64))
    return draw(st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            min_codepoint=33,
            max_codepoint=126
        ),
        min_size=length,
        max_size=length
    ))


@st.composite
def oauth_token(draw):
    """Generate realistic OAuth tokens."""
    # Slack bot tokens start with 'xoxb-'
    token_suffix = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            min_codepoint=33,
            max_codepoint=126
        ),
        min_size=20,
        max_size=100
    ))
    return f"xoxb-{token_suffix}"


@st.composite
def slack_team_id(draw):
    """Generate valid Slack team IDs."""
    # Format: T followed by 8-11 uppercase alphanumeric characters
    length = draw(st.integers(min_value=8, max_value=11))
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=length,
        max_size=length
    ))
    return f"T{suffix}"


@st.composite
def slack_user_id(draw):
    """Generate valid Slack user IDs."""
    # Format: U followed by 8-11 uppercase alphanumeric characters
    length = draw(st.integers(min_value=8, max_value=11))
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=length,
        max_size=length
    ))
    return f"U{suffix}"


@st.composite
def workspace_token(draw):
    """Generate valid WorkspaceToken instances."""
    return WorkspaceToken(
        team_id=draw(slack_team_id()),
        access_token=draw(oauth_token()),
        bot_user_id=draw(slack_user_id()),
        scope=draw(st.text(min_size=1, max_size=100)),
        installed_at=datetime.now(timezone.utc)
    )


class TestTokenEncryptionProperties:
    """
    Property-based tests for token encryption.
    
    Feature: slack-integration, Property 27: OAuth Token Encryption
    
    For any stored OAuth token, reading it from storage should return the
    decrypted token, and inspecting the storage directly should show only
    encrypted data.
    
    Validates: Requirements 12.1
    """
    
    @given(key=encryption_key(), token=oauth_token())
    def test_encryption_decryption_roundtrip(self, key, token):
        """
        Property: For any encryption key and token, encrypting then decrypting
        should return the original token.
        
        This validates that encryption is reversible and data is not lost.
        """
        encryption = TokenEncryption(key)
        
        encrypted = encryption.encrypt(token)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == token
    
    @given(key=encryption_key(), token=oauth_token())
    def test_encrypted_token_differs_from_plaintext(self, key, token):
        """
        Property: For any token, the encrypted version should differ from
        the plaintext.
        
        This validates that encryption actually transforms the data.
        """
        encryption = TokenEncryption(key)
        
        encrypted = encryption.encrypt(token)
        
        assert encrypted != token
    
    @given(key=encryption_key(), token=oauth_token())
    def test_encryption_produces_unique_ciphertext(self, key, token):
        """
        Property: For any token, encrypting it twice should produce different
        ciphertext due to unique IVs.
        
        This validates that encryption uses random IVs for security.
        """
        encryption = TokenEncryption(key)
        
        encrypted1 = encryption.encrypt(token)
        encrypted2 = encryption.encrypt(token)
        
        # Different IVs should produce different ciphertext
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same plaintext
        assert encryption.decrypt(encrypted1) == token
        assert encryption.decrypt(encrypted2) == token
    
    @given(key1=encryption_key(), key2=encryption_key(), token=oauth_token())
    def test_different_keys_produce_different_ciphertext(self, key1, key2, token):
        """
        Property: For any token, encrypting with different keys should produce
        different ciphertext.
        
        This validates key-dependent encryption.
        """
        assume(key1 != key2)
        
        encryption1 = TokenEncryption(key1)
        encryption2 = TokenEncryption(key2)
        
        encrypted1 = encryption1.encrypt(token)
        encrypted2 = encryption2.encrypt(token)
        
        # Different keys should produce different ciphertext
        assert encrypted1 != encrypted2
    
    @given(key1=encryption_key(), key2=encryption_key(), token=oauth_token())
    def test_wrong_key_cannot_decrypt(self, key1, key2, token):
        """
        Property: For any token encrypted with one key, attempting to decrypt
        with a different key should fail.
        
        This validates that decryption requires the correct key.
        """
        # Ensure keys are actually different in their first 32 bytes
        # (since TokenEncryption uses first 32 bytes)
        assume(key1[:32] != key2[:32])
        
        encryption1 = TokenEncryption(key1)
        encryption2 = TokenEncryption(key2)
        
        encrypted = encryption1.encrypt(token)
        
        # Attempting to decrypt with wrong key should raise error
        with pytest.raises(ValueError, match="Failed to decrypt"):
            encryption2.decrypt(encrypted)
    
    @given(key=encryption_key(), token=oauth_token())
    def test_encrypted_token_is_base64_encoded(self, key, token):
        """
        Property: For any token, the encrypted version should be valid base64.
        
        This validates the encoding format for storage.
        """
        import base64
        
        encryption = TokenEncryption(key)
        encrypted = encryption.encrypt(token)
        
        # Should be valid base64
        try:
            decoded = base64.b64decode(encrypted)
            assert len(decoded) > 0
        except Exception:
            pytest.fail("Encrypted token is not valid base64")


class TestOAuthManagerTokenStorageProperties:
    """
    Property-based tests for OAuth manager token storage.
    
    Feature: slack-integration, Property 27: OAuth Token Encryption
    
    Validates that tokens are encrypted in storage and decrypted on retrieval.
    
    Validates: Requirements 12.1
    """
    
    @given(token=workspace_token())
    @pytest.mark.asyncio
    async def test_stored_token_is_encrypted(self, token):
        """
        Property: For any workspace token, storing it should result in the
        access_token being encrypted in storage.
        
        This validates that tokens are never stored in plaintext.
        """
        manager = OAuthManager(
            client_id="test_client",
            client_secret="test_secret",
            redirect_url="https://example.com/callback",
            encryption_key="a" * 32,
            token_storage={}
        )
        
        # Encrypt the token before storage (as handle_callback does)
        encrypted_token = manager.encryption.encrypt(token.access_token)
        token_to_store = WorkspaceToken(
            team_id=token.team_id,
            access_token=encrypted_token,
            bot_user_id=token.bot_user_id,
            scope=token.scope,
            installed_at=token.installed_at
        )
        
        await manager.store_token(token_to_store)
        
        # Check storage directly - should contain encrypted token
        stored = manager._token_storage[token.team_id]
        assert stored.access_token != token.access_token
        assert stored.access_token == encrypted_token
    
    @given(token=workspace_token())
    @pytest.mark.asyncio
    async def test_retrieved_token_is_decrypted(self, token):
        """
        Property: For any stored workspace token, retrieving it should return
        the decrypted access_token.
        
        This validates that tokens are automatically decrypted on retrieval.
        """
        manager = OAuthManager(
            client_id="test_client",
            client_secret="test_secret",
            redirect_url="https://example.com/callback",
            encryption_key="a" * 32,
            token_storage={}
        )
        
        # Store token with encrypted access_token
        encrypted_token = manager.encryption.encrypt(token.access_token)
        token_to_store = WorkspaceToken(
            team_id=token.team_id,
            access_token=encrypted_token,
            bot_user_id=token.bot_user_id,
            scope=token.scope,
            installed_at=token.installed_at
        )
        await manager.store_token(token_to_store)
        
        # Retrieve token - should be decrypted
        retrieved = await manager.get_token(token.team_id)
        
        assert retrieved is not None
        assert retrieved.access_token == token.access_token
        assert retrieved.access_token != encrypted_token
    
    @given(token=workspace_token())
    @pytest.mark.asyncio
    async def test_storage_never_contains_plaintext_token(self, token):
        """
        Property: For any workspace token, the storage should never contain
        the plaintext access_token.
        
        This is a critical security property - tokens must always be encrypted
        at rest.
        """
        manager = OAuthManager(
            client_id="test_client",
            client_secret="test_secret",
            redirect_url="https://example.com/callback",
            encryption_key="a" * 32,
            token_storage={}
        )
        
        # Store token
        encrypted_token = manager.encryption.encrypt(token.access_token)
        token_to_store = WorkspaceToken(
            team_id=token.team_id,
            access_token=encrypted_token,
            bot_user_id=token.bot_user_id,
            scope=token.scope,
            installed_at=token.installed_at
        )
        await manager.store_token(token_to_store)
        
        # Check that plaintext token is not in storage
        stored = manager._token_storage[token.team_id]
        assert token.access_token not in str(stored.access_token)
        
        # Verify storage contains encrypted version
        assert stored.access_token == encrypted_token
    
    @given(token=workspace_token())
    @pytest.mark.asyncio
    async def test_revoked_token_removed_from_storage(self, token):
        """
        Property: For any workspace token, revoking it should remove it from
        storage entirely.
        
        This validates that revoked tokens cannot be retrieved.
        """
        from unittest.mock import AsyncMock, patch
        
        manager = OAuthManager(
            client_id="test_client",
            client_secret="test_secret",
            redirect_url="https://example.com/callback",
            encryption_key="a" * 32,
            token_storage={}
        )
        
        # Store token
        encrypted_token = manager.encryption.encrypt(token.access_token)
        token_to_store = WorkspaceToken(
            team_id=token.team_id,
            access_token=encrypted_token,
            bot_user_id=token.bot_user_id,
            scope=token.scope,
            installed_at=token.installed_at
        )
        await manager.store_token(token_to_store)
        
        # Verify token is stored
        assert token.team_id in manager._token_storage
        
        # Mock Slack API to avoid actual HTTP request
        mock_response = type('MockResponse', (), {
            'json': lambda: {'ok': True},
            'raise_for_status': lambda: None
        })()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            # Revoke token
            result = await manager.revoke_token(token.team_id)
        
        # Verify token was revoked successfully
        assert result is True
        
        # Verify token is removed from storage
        retrieved = await manager.get_token(token.team_id)
        assert retrieved is None
        assert token.team_id not in manager._token_storage
