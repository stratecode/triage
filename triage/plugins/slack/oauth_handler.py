# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Slack OAuth Handler

Handles Slack OAuth 2.0 authorization flow for workspace installation.
Implements token exchange, storage, and refresh logic.

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlencode

import httpx

from ..installation_storage import PluginInstallationStorage
from ..models import PluginInstallation

logger = logging.getLogger(__name__)


class OAuthError(Exception):
    """
    OAuth-specific error with user-friendly message.

    Validates: Requirements 6.6
    """

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[str] = None):
        """
        Initialize OAuth error.

        Args:
            message: User-friendly error message
            error_code: Slack error code (e.g., 'invalid_code')
            details: Additional technical details (not shown to user)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details

        logger.error(
            "OAuth error occurred", extra={"error_message": message, "error_code": error_code, "details": details}
        )


@dataclass
class OAuthTokens:
    """
    OAuth token storage.

    Contains all data returned from Slack OAuth token exchange.

    Validates: Requirements 6.3, 6.4
    """

    access_token: str
    bot_user_id: str
    team_id: str
    team_name: str
    scope: str
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None

    def to_metadata(self) -> dict:
        """
        Convert to metadata dictionary for storage.

        Returns:
            Dictionary with bot_user_id, team_name, scope
        """
        return {
            "bot_user_id": self.bot_user_id,
            "team_name": self.team_name,
            "scope": self.scope,
            "expires_at": self.expires_at,
        }


class SlackOAuthHandler:
    """
    Handles Slack OAuth 2.0 authorization flow.

    Implements the complete OAuth flow for Slack workspace installation:
    1. Generate authorization URL
    2. Exchange authorization code for tokens
    3. Store tokens securely in database
    4. Refresh expired tokens

    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
    """

    # Slack OAuth endpoints
    OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    OAUTH_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

    # Required Slack bot scopes (minimum permissions)
    DEFAULT_SCOPES = [
        "commands",  # Slash commands
        "chat:write",  # Send messages
        "app_mentions:read",  # Read mentions
        "im:history",  # Read DMs
        "im:write",  # Send DMs
    ]

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, storage: PluginInstallationStorage):
        """
        Initialize Slack OAuth handler.

        Args:
            client_id: Slack app client ID
            client_secret: Slack app client secret
            redirect_uri: OAuth callback URL
            storage: Plugin installation storage for token persistence

        Validates: Requirements 6.1
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.storage = storage

        logger.info(
            "Initialized SlackOAuthHandler",
            extra={
                "client_id": client_id[:8] + "...",  # Log partial ID only
                "redirect_uri": redirect_uri,
            },
        )

    def get_authorization_url(self, state: str, scopes: Optional[List[str]] = None) -> str:
        """
        Generate OAuth authorization URL for workspace installation.

        Args:
            state: CSRF protection state parameter (should be random and verified)
            scopes: List of Slack permission scopes (uses defaults if not provided)

        Returns:
            Complete authorization URL to redirect user to

        Validates: Requirements 6.1, 6.2, 6.7
        """
        if scopes is None:
            scopes = self.DEFAULT_SCOPES

        scope_string = ",".join(scopes)

        params = {"client_id": self.client_id, "scope": scope_string, "redirect_uri": self.redirect_uri, "state": state}

        auth_url = f"{self.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

        logger.info(
            "Generated OAuth authorization URL",
            extra={"state": state, "scopes": scopes, "redirect_uri": self.redirect_uri},
        )

        return auth_url

    async def exchange_code_for_token(self, code: str) -> OAuthTokens:
        """
        Exchange authorization code for access token.

        Calls Slack's oauth.v2.access endpoint to exchange the authorization
        code for an access token and bot information.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            OAuthTokens with access token and workspace information

        Raises:
            OAuthError: If token exchange fails with user-friendly message

        Validates: Requirements 6.2, 6.3, 6.6
        """
        logger.info("Exchanging authorization code for access token")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.OAUTH_TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                )

                response.raise_for_status()
                data = response.json()

            # Check if Slack returned an error
            if not data.get("ok"):
                error_code = data.get("error", "unknown_error")
                error_msg = self._get_user_friendly_error_message(error_code)

                raise OAuthError(message=error_msg, error_code=error_code, details=data.get("error_description"))

            # Extract token data
            tokens = OAuthTokens(
                access_token=data["access_token"],
                bot_user_id=data["bot_user_id"],
                team_id=data["team"]["id"],
                team_name=data["team"]["name"],
                scope=data["scope"],
                refresh_token=data.get("refresh_token"),
                expires_at=data.get("expires_in"),
            )

            logger.info(
                "Successfully exchanged authorization code",
                extra={"team_id": tokens.team_id, "team_name": tokens.team_name, "bot_user_id": tokens.bot_user_id},
            )

            return tokens

        except OAuthError:
            # Re-raise OAuth errors as-is (they already have proper error codes)
            raise
        except httpx.HTTPError as e:
            logger.error("HTTP error during token exchange", extra={"error": str(e)}, exc_info=True)
            raise OAuthError(message="Failed to connect to Slack. Please try again later.", details=str(e))
        except KeyError as e:
            logger.error(
                "Unexpected response format from Slack", extra={"error": str(e), "response": data}, exc_info=True
            )
            raise OAuthError(
                message="Received unexpected response from Slack. Please contact support.",
                details=f"Missing field: {e}",
            )
        except Exception as e:
            logger.error("Unexpected error during token exchange", extra={"error": str(e)}, exc_info=True)
            raise OAuthError(message="An unexpected error occurred. Please try again.", details=str(e))

    async def store_tokens(self, tokens: OAuthTokens) -> PluginInstallation:
        """
        Store OAuth tokens in database with encryption.

        Creates a new plugin installation record with encrypted tokens.

        Args:
            tokens: OAuth tokens to store

        Returns:
            Created PluginInstallation record

        Raises:
            ValueError: If installation already exists
            OAuthError: If storage fails

        Validates: Requirements 6.4, 6.5
        """
        logger.info("Storing OAuth tokens", extra={"team_id": tokens.team_id, "team_name": tokens.team_name})

        try:
            installation = PluginInstallation(
                plugin_name="slack",
                channel_id=tokens.team_id,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                metadata=tokens.to_metadata(),
                is_active=True,
            )

            created = await self.storage.create_installation(installation)

            logger.info(
                "OAuth tokens stored successfully", extra={"team_id": tokens.team_id, "installation_id": created.id}
            )

            return created

        except ValueError as e:
            # Installation already exists
            logger.warning("Installation already exists", extra={"team_id": tokens.team_id})
            raise OAuthError(
                message=f"TrIAge is already installed in workspace '{tokens.team_name}'. "
                "Please uninstall first if you want to reinstall.",
                error_code="already_installed",
                details=str(e),
            )
        except Exception as e:
            logger.error(
                "Failed to store OAuth tokens", extra={"team_id": tokens.team_id, "error": str(e)}, exc_info=True
            )
            raise OAuthError(message="Failed to complete installation. Please try again.", details=str(e))

    async def refresh_token(self, team_id: str, refresh_token: str) -> OAuthTokens:
        """
        Refresh expired access token using refresh token.

        Note: Slack's OAuth v2 doesn't currently support token refresh for
        bot tokens. This method is implemented for future compatibility.

        Args:
            team_id: Slack team/workspace ID
            refresh_token: Refresh token from initial authorization

        Returns:
            New OAuthTokens with refreshed access token

        Raises:
            OAuthError: If token refresh fails

        Validates: Requirements 6.5
        """
        logger.info("Refreshing access token", extra={"team_id": team_id})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.OAUTH_TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                )

                response.raise_for_status()
                data = response.json()

            if not data.get("ok"):
                error_code = data.get("error", "unknown_error")
                error_msg = self._get_user_friendly_error_message(error_code)

                raise OAuthError(
                    message=f"Failed to refresh token: {error_msg}",
                    error_code=error_code,
                    details=data.get("error_description"),
                )

            # Extract refreshed token data
            tokens = OAuthTokens(
                access_token=data["access_token"],
                bot_user_id=data["bot_user_id"],
                team_id=data["team"]["id"],
                team_name=data["team"]["name"],
                scope=data["scope"],
                refresh_token=data.get("refresh_token", refresh_token),  # May return new refresh token
                expires_at=data.get("expires_in"),
            )

            # Update stored tokens
            await self.storage.update_installation(
                plugin_name="slack",
                channel_id=team_id,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                metadata=tokens.to_metadata(),
            )

            logger.info("Access token refreshed successfully", extra={"team_id": team_id})

            return tokens

        except httpx.HTTPError as e:
            logger.error("HTTP error during token refresh", extra={"team_id": team_id, "error": str(e)}, exc_info=True)
            raise OAuthError(message="Failed to refresh token. Please reinstall the app.", details=str(e))
        except Exception as e:
            logger.error(
                "Unexpected error during token refresh", extra={"team_id": team_id, "error": str(e)}, exc_info=True
            )
            raise OAuthError(message="Failed to refresh token. Please reinstall the app.", details=str(e))

    def _get_user_friendly_error_message(self, error_code: str) -> str:
        """
        Convert Slack error code to user-friendly message.

        Args:
            error_code: Slack API error code

        Returns:
            User-friendly error message

        Validates: Requirements 6.6
        """
        error_messages = {
            "invalid_code": (
                "The authorization code is invalid or has expired. " "Please try installing the app again."
            ),
            "code_already_used": (
                "This authorization code has already been used. " "Please start the installation process again."
            ),
            "invalid_client_id": ("App configuration error. Please contact support."),
            "invalid_client_secret": ("App configuration error. Please contact support."),
            "invalid_redirect_uri": ("App configuration error. Please contact support."),
            "invalid_grant_type": ("App configuration error. Please contact support."),
            "invalid_refresh_token": ("Your session has expired. Please reinstall the app."),
            "token_revoked": ("The app has been uninstalled. Please reinstall to continue using TrIAge."),
            "access_denied": ("Installation was cancelled. Please try again if you want to install TrIAge."),
        }

        return error_messages.get(
            error_code, "An error occurred during installation. Please try again or contact support."
        )
