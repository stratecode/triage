# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for OAuth manager.

Tests OAuth installation flow, token exchange, encryption/decryption,
and token lifecycle management.

Validates: Requirements 1.1, 1.2, 1.3, 1.5, 12.1, 12.5
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
import httpx

from slack_bot.oauth_manager import OAuthManager, TokenEncryption
from slack_bot.models import WorkspaceToken


class TestTokenEncryption:
    """Test token encryption and decryption."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are inverse operations."""
        encryption = TokenEncryption("a" * 32)
        plaintext = "xoxb-test-token-12345"
        
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == plaintext
        assert encrypted != plaintext
    
    def test_encryption_produces_different_ciphertext(self):
        """Test that encrypting same plaintext twice produces different ciphertext."""
        encryption = TokenEncryption("a" * 32)
        plaintext = "xoxb-test-token-12345"
        
        encrypted1 = encryption.encrypt(plaintext)
        encrypted2 = encryption.encrypt(plaintext)
        
        # Different IVs should produce different ciphertext
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same plaintext
        assert encryption.decrypt(encrypted1) == plaintext
        assert encryption.decrypt(encrypted2) == plaintext
    
    def test_invalid_encryption_key_raises_error(self):
        """Test that short encryption key raises ValueError."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            TokenEncryption("short")
    
    def test_decrypt_invalid_data_raises_error(self):
        """Test that decrypting invalid data raises ValueError."""
        encryption = TokenEncryption("a" * 32)
        
        with pytest.raises(ValueError, match="Failed to decrypt"):
            encryption.decrypt("invalid-base64-data")
    
    def test_decrypt_corrupted_data_raises_error(self):
        """Test that decrypting corrupted data raises ValueError."""
        encryption = TokenEncryption("a" * 32)
        
        # Encrypt valid data
        encrypted = encryption.encrypt("test")
        
        # Corrupt the encrypted data
        corrupted = encrypted[:-5] + "XXXXX"
        
        with pytest.raises(ValueError, match="Failed to decrypt"):
            encryption.decrypt(corrupted)


class TestOAuthManager:
    """Test OAuth manager functionality."""
    
    @pytest.fixture
    def oauth_manager(self):
        """Create OAuth manager for testing."""
        return OAuthManager(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_url="https://example.com/oauth/callback",
            encryption_key="a" * 32,
            token_storage={}  # Use in-memory storage for tests
        )
    
    def test_generate_install_url(self, oauth_manager):
        """Test OAuth installation URL generation."""
        url = oauth_manager.generate_install_url(state="test_state")
        
        assert "https://slack.com/oauth/v2/authorize" in url
        assert "client_id=test_client_id" in url
        assert "state=test_state" in url
        assert "redirect_uri=https%3A%2F%2Fexample.com%2Foauth%2Fcallback" in url
        assert "scope=" in url
        
        # Check all required scopes are present (URL encoded)
        from urllib.parse import unquote
        decoded_url = unquote(url)
        for scope in OAuthManager.REQUIRED_SCOPES:
            assert scope in decoded_url
    
    def test_generate_install_url_with_auto_state(self, oauth_manager):
        """Test OAuth URL generation with automatic state generation."""
        url = oauth_manager.generate_install_url()
        
        assert "state=" in url
        assert "https://slack.com/oauth/v2/authorize" in url
    
    @pytest.mark.asyncio
    async def test_handle_callback_success(self, oauth_manager):
        """Test successful OAuth callback and token exchange."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'ok': True,
            'access_token': 'xoxb-test-token',
            'team': {'id': 'T12345ABCD'},
            'bot_user_id': 'U67890EFGH',
            'scope': 'chat:write,commands'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            token = await oauth_manager.handle_callback(
                code="test_code",
                state="test_state"
            )
        
        assert token.team_id == "T12345ABCD"
        assert token.bot_user_id == "U67890EFGH"
        assert token.scope == "chat:write,commands"
        
        # Token should be encrypted
        assert token.access_token != "xoxb-test-token"
        
        # Should be able to decrypt it
        decrypted = oauth_manager.encryption.decrypt(token.access_token)
        assert decrypted == "xoxb-test-token"
    
    @pytest.mark.asyncio
    async def test_handle_callback_authorization_denied(self, oauth_manager):
        """Test OAuth callback when authorization is denied."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'ok': False,
            'error': 'access_denied'
        }
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(ValueError, match="access_denied"):
                await oauth_manager.handle_callback(code="test_code")
    
    @pytest.mark.asyncio
    async def test_handle_callback_http_error(self, oauth_manager):
        """Test OAuth callback with HTTP error."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Network error")
            )
            
            with pytest.raises(httpx.HTTPError):
                await oauth_manager.handle_callback(code="test_code")
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_token(self, oauth_manager):
        """Test storing and retrieving workspace token."""
        token = WorkspaceToken(
            team_id="T12345ABCD",
            access_token=oauth_manager.encryption.encrypt("xoxb-test-token"),
            bot_user_id="U67890EFGH",
            scope="chat:write",
            installed_at=datetime.now(timezone.utc)
        )
        
        await oauth_manager.store_token(token)
        
        retrieved = await oauth_manager.get_token("T12345ABCD")
        
        assert retrieved is not None
        assert retrieved.team_id == "T12345ABCD"
        assert retrieved.bot_user_id == "U67890EFGH"
        assert retrieved.access_token == "xoxb-test-token"  # Should be decrypted
    
    @pytest.mark.asyncio
    async def test_get_token_not_found(self, oauth_manager):
        """Test retrieving non-existent token returns None."""
        token = await oauth_manager.get_token("T99999")
        assert token is None
    
    @pytest.mark.asyncio
    async def test_revoke_token_success(self, oauth_manager):
        """Test successful token revocation."""
        # Store a token first
        token = WorkspaceToken(
            team_id="T12345ABCD",
            access_token=oauth_manager.encryption.encrypt("xoxb-test-token"),
            bot_user_id="U67890EFGH",
            scope="chat:write",
            installed_at=datetime.now(timezone.utc)
        )
        await oauth_manager.store_token(token)
        
        # Mock Slack API revocation
        mock_response = Mock()
        mock_response.json.return_value = {'ok': True}
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await oauth_manager.revoke_token("T12345ABCD")
        
        assert result is True
        
        # Token should be deleted
        retrieved = await oauth_manager.get_token("T12345ABCD")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_revoke_token_not_found(self, oauth_manager):
        """Test revoking non-existent token returns False."""
        result = await oauth_manager.revoke_token("T99999")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_revoke_token_api_failure_still_deletes(self, oauth_manager):
        """Test that token is deleted even if Slack API revocation fails."""
        # Store a token first
        token = WorkspaceToken(
            team_id="T12345ABCD",
            access_token=oauth_manager.encryption.encrypt("xoxb-test-token"),
            bot_user_id="U67890EFGH",
            scope="chat:write",
            installed_at=datetime.now(timezone.utc)
        )
        await oauth_manager.store_token(token)
        
        # Mock Slack API failure
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("API error")
            )
            
            result = await oauth_manager.revoke_token("T12345ABCD")
        
        # Should still return True and delete token
        assert result is True
        
        # Token should be deleted
        retrieved = await oauth_manager.get_token("T12345ABCD")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, oauth_manager):
        """Test token refresh (currently returns existing token)."""
        # Store a token first
        token = WorkspaceToken(
            team_id="T12345ABCD",
            access_token=oauth_manager.encryption.encrypt("xoxb-test-token"),
            bot_user_id="U67890EFGH",
            scope="chat:write",
            installed_at=datetime.now(timezone.utc)
        )
        await oauth_manager.store_token(token)
        
        # Refresh token
        refreshed = await oauth_manager.refresh_token("T12345ABCD")
        
        assert refreshed is not None
        assert refreshed.team_id == "T12345ABCD"
        assert refreshed.access_token == "xoxb-test-token"
    
    @pytest.mark.asyncio
    async def test_refresh_token_not_found(self, oauth_manager):
        """Test refreshing non-existent token returns None."""
        refreshed = await oauth_manager.refresh_token("T99999")
        assert refreshed is None
    
    @pytest.mark.asyncio
    async def test_get_token_with_corrupted_encryption(self, oauth_manager):
        """Test that corrupted encrypted token returns None."""
        # Manually insert corrupted token
        oauth_manager._token_storage["T12345ABCD"] = WorkspaceToken(
            team_id="T12345ABCD",
            access_token="corrupted-data",
            bot_user_id="U67890EFGH",
            scope="chat:write",
            installed_at=datetime.now(timezone.utc)
        )
        
        token = await oauth_manager.get_token("T12345ABCD")
        assert token is None
