# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
OAuth manager for Slack workspace installation and token management.

This module handles the OAuth installation flow, token exchange, secure
token storage with AES-256 encryption, and token lifecycle management.

Validates: Requirements 1.1, 1.2, 1.5, 12.1, 12.5
"""

import base64
import secrets
from datetime import datetime, timezone
from typing import Optional, Any
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

from slack_bot.models import WorkspaceToken
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


class TokenEncryption:
    """
    Handles AES-256 encryption and decryption of OAuth tokens.
    
    Uses AES-256-CBC with PKCS7 padding for secure token storage.
    Each encryption operation uses a unique IV for security.
    
    Validates: Requirements 12.1
    """
    
    def __init__(self, encryption_key: str):
        """
        Initialize token encryption with a 32-byte key.
        
        Args:
            encryption_key: Base64-encoded 32-byte encryption key
            
        Raises:
            ValueError: If encryption key is invalid
        """
        if len(encryption_key) < 32:
            raise ValueError("Encryption key must be at least 32 characters")
        
        # Use first 32 bytes of key for AES-256
        self.key = encryption_key[:32].encode('utf-8')
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext token using AES-256-CBC.
        
        Args:
            plaintext: Token to encrypt
            
        Returns:
            Base64-encoded encrypted token with IV prepended
        """
        # Generate random IV (16 bytes for AES)
        iv = secrets.token_bytes(16)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Pad plaintext to block size (16 bytes)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode('utf-8')) + padder.finalize()
        
        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Prepend IV to ciphertext and encode as base64
        encrypted = iv + ciphertext
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted token using AES-256-CBC.
        
        Args:
            encrypted: Base64-encoded encrypted token with IV
            
        Returns:
            Decrypted plaintext token
            
        Raises:
            ValueError: If decryption fails
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted)
            
            # Extract IV (first 16 bytes) and ciphertext
            iv = encrypted_bytes[:16]
            ciphertext = encrypted_bytes[16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            
            return plaintext.decode('utf-8')
        except Exception as e:
            logger.error("Token decryption failed", extra={'error': str(e)})
            raise ValueError("Failed to decrypt token") from e


class OAuthManager:
    """
    Manages OAuth installation flow and token lifecycle for Slack workspaces.
    
    Handles:
    - OAuth installation URL generation
    - OAuth callback and token exchange
    - Secure token storage with AES-256 encryption
    - Token retrieval and revocation
    - Token refresh for expired tokens
    
    Validates: Requirements 1.1, 1.2, 1.5, 12.1, 12.5
    """
    
    # Required OAuth scopes for bot functionality
    REQUIRED_SCOPES = [
        "chat:write",      # Send messages
        "commands",        # Handle slash commands
        "users:read",      # Get user information
        "channels:read",   # List channels
        "im:write",        # Send direct messages
    ]
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_url: str,
        encryption_key: str,
        token_storage: Optional[dict] = None,
        user_storage: Optional[Any] = None
    ):
        """
        Initialize OAuth manager.
        
        Args:
            client_id: Slack app client ID
            client_secret: Slack app client secret
            redirect_url: OAuth callback URL
            encryption_key: Encryption key for token storage
            token_storage: Optional in-memory token storage (for testing)
            user_storage: Optional UserMappingStorage for user data deletion
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_url = redirect_url
        self.encryption = TokenEncryption(encryption_key)
        self.user_storage = user_storage
        
        # In-memory storage for development/testing
        # In production, this would be a database
        self._token_storage = token_storage if token_storage is not None else {}
        
        logger.info("OAuth manager initialized", extra={
            'client_id': client_id,
            'redirect_url': redirect_url,
            'scopes': ','.join(self.REQUIRED_SCOPES),
            'has_user_storage': user_storage is not None
        })
    
    def generate_install_url(self, state: Optional[str] = None) -> str:
        """
        Generate OAuth installation URL for workspace installation.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            OAuth authorization URL
            
        Validates: Requirements 1.1
        """
        if state is None:
            state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': self.client_id,
            'scope': ','.join(self.REQUIRED_SCOPES),
            'redirect_uri': self.redirect_url,
            'state': state
        }
        
        url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
        
        logger.info("Generated OAuth install URL", extra={
            'state': state,
            'scopes': ','.join(self.REQUIRED_SCOPES)
        })
        
        return url
    
    async def handle_callback(self, code: str, state: Optional[str] = None) -> WorkspaceToken:
        """
        Handle OAuth callback and exchange code for access token.
        
        Args:
            code: OAuth authorization code from Slack
            state: State parameter for CSRF validation
            
        Returns:
            WorkspaceToken with encrypted access token
            
        Raises:
            ValueError: If token exchange fails
            httpx.HTTPError: If API request fails
            
        Validates: Requirements 1.2
        """
        logger.info("Handling OAuth callback", extra={'state': state})
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'code': code,
                        'redirect_uri': self.redirect_url
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get('ok'):
                    error = data.get('error', 'unknown_error')
                    logger.error("OAuth token exchange failed", extra={'error': error})
                    raise ValueError(f"OAuth token exchange failed: {error}")
                
                # Extract token information
                team_id = data['team']['id']
                access_token = data['access_token']
                bot_user_id = data['bot_user_id']
                scope = data['scope']
                
                # Encrypt access token before storage
                encrypted_token = self.encryption.encrypt(access_token)
                
                # Create workspace token
                workspace_token = WorkspaceToken(
                    team_id=team_id,
                    access_token=encrypted_token,
                    bot_user_id=bot_user_id,
                    scope=scope,
                    installed_at=datetime.now(timezone.utc)
                )
                
                logger.info("OAuth token exchange successful", extra={
                    'team_id': team_id,
                    'bot_user_id': bot_user_id,
                    'scope': scope
                })
                
                return workspace_token
                
            except httpx.HTTPError as e:
                logger.error("OAuth callback HTTP error", extra={'error': str(e)})
                raise
            except Exception as e:
                logger.error("OAuth callback failed", extra={'error': str(e)})
                raise ValueError(f"OAuth callback failed: {str(e)}") from e
    
    async def store_token(self, token: WorkspaceToken) -> None:
        """
        Securely store workspace token with encryption.
        
        The access_token field in the WorkspaceToken should already be
        encrypted by handle_callback().
        
        Args:
            token: WorkspaceToken to store (with encrypted access_token)
            
        Validates: Requirements 1.2, 12.1
        """
        self._token_storage[token.team_id] = token
        
        logger.info("Workspace token stored", extra={
            'team_id': token.team_id,
            'bot_user_id': token.bot_user_id,
            'installed_at': token.installed_at.isoformat()
        })
    
    async def get_token(self, team_id: str) -> Optional[WorkspaceToken]:
        """
        Retrieve workspace token and decrypt access token.
        
        Args:
            team_id: Slack workspace/team ID
            
        Returns:
            WorkspaceToken with decrypted access token, or None if not found
            
        Validates: Requirements 1.2, 12.1
        """
        token = self._token_storage.get(team_id)
        
        if token is None:
            logger.warning("Workspace token not found", extra={'team_id': team_id})
            return None
        
        # Decrypt access token for use
        try:
            decrypted_token = self.encryption.decrypt(token.access_token)
            
            # Return token with decrypted access_token
            return WorkspaceToken(
                team_id=token.team_id,
                access_token=decrypted_token,
                bot_user_id=token.bot_user_id,
                scope=token.scope,
                installed_at=token.installed_at
            )
        except ValueError as e:
            logger.error("Failed to decrypt workspace token", extra={
                'team_id': team_id,
                'error': str(e)
            })
            return None
    
    async def revoke_token(self, team_id: str) -> bool:
        """
        Revoke and delete workspace token.
        
        This is called when a workspace uninstalls the bot or when
        explicitly revoking access.
        
        Args:
            team_id: Slack workspace/team ID
            
        Returns:
            True if token was revoked, False if not found
            
        Validates: Requirements 1.5, 12.5
        """
        token = await self.get_token(team_id)
        
        if token is None:
            logger.warning("Cannot revoke token - not found", extra={'team_id': team_id})
            return False
        
        # Call Slack API to revoke token
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://slack.com/api/auth.revoke",
                    headers={
                        'Authorization': f'Bearer {token.access_token}'
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get('ok'):
                    logger.warning("Slack token revocation failed", extra={
                        'team_id': team_id,
                        'error': data.get('error', 'unknown')
                    })
                
            except Exception as e:
                logger.error("Failed to revoke token with Slack", extra={
                    'team_id': team_id,
                    'error': str(e)
                })
        
        # Delete token from storage regardless of API call result
        if team_id in self._token_storage:
            del self._token_storage[team_id]
            logger.info("Workspace token deleted", extra={'team_id': team_id})
            return True
        
        return False
    
    async def handle_uninstall(self, team_id: str) -> bool:
        """
        Handle workspace uninstall event.
        
        This method:
        1. Revokes the OAuth token with Slack
        2. Deletes all tokens from storage
        3. Deletes all user data associated with the workspace
        
        This ensures compliance with data deletion requirements when
        a workspace uninstalls the bot.
        
        Args:
            team_id: Slack workspace/team ID
            
        Returns:
            True if uninstall was handled successfully
            
        Validates: Requirements 12.5
        """
        logger.info("Handling workspace uninstall", extra={'team_id': team_id})
        
        # Revoke token (which also deletes it from storage)
        token_revoked = await self.revoke_token(team_id)
        
        # Delete all user mappings for this workspace
        users_deleted = 0
        if self.user_storage:
            try:
                users_deleted = await self.user_storage.delete_workspace_mappings(team_id)
                logger.info("Deleted user mappings for workspace", extra={
                    'team_id': team_id,
                    'users_deleted': users_deleted
                })
            except Exception as e:
                logger.error("Failed to delete user mappings", extra={
                    'team_id': team_id,
                    'error': str(e)
                })
        
        logger.info("Workspace uninstall completed", extra={
            'team_id': team_id,
            'token_revoked': token_revoked,
            'users_deleted': users_deleted
        })
        
        return token_revoked
    
    async def refresh_token(self, team_id: str) -> Optional[WorkspaceToken]:
        """
        Refresh an expired workspace token.
        
        Note: Slack bot tokens don't expire, but this method is provided
        for future compatibility if refresh tokens are implemented.
        
        Args:
            team_id: Slack workspace/team ID
            
        Returns:
            Refreshed WorkspaceToken, or None if refresh fails
            
        Validates: Requirements 1.5
        """
        logger.info("Token refresh requested", extra={'team_id': team_id})
        
        # Slack bot tokens don't expire, so just return existing token
        # This is a placeholder for future refresh token support
        token = await self.get_token(team_id)
        
        if token is None:
            logger.warning("Cannot refresh token - not found", extra={'team_id': team_id})
            return None
        
        logger.info("Token refresh not needed (Slack bot tokens don't expire)", extra={
            'team_id': team_id
        })
        
        return token
