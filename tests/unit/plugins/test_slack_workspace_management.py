# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit Tests for Slack Workspace Installation Management

Tests the workspace installation storage, verification, uninstall cleanup,
and data isolation methods in the Slack plugin.

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from triage.plugins.interface import PluginConfig, PluginMessage
from triage.plugins.models import PluginInstallation
from triage.plugins.slack.slack_plugin import SlackPlugin


@pytest.fixture
def slack_plugin():
    """Create a SlackPlugin instance for testing."""
    plugin = SlackPlugin()
    return plugin


@pytest.fixture
def mock_storage():
    """Create a mock PluginInstallationStorage."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def mock_core_api():
    """Create a mock CoreActionsAPI."""
    api = AsyncMock()
    return api


@pytest_asyncio.fixture
async def initialized_plugin(slack_plugin, mock_storage, mock_core_api):
    """Create an initialized SlackPlugin with mocked dependencies."""
    config = PluginConfig(
        plugin_name="slack",
        plugin_version="1.0.0",
        enabled=True,
        config={
            "signing_secret": "test_signing_secret",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        },
    )

    # Set storage before initialization
    slack_plugin.storage = mock_storage

    await slack_plugin.initialize(config, mock_core_api)

    return slack_plugin


class TestStoreInstallation:
    """Test workspace installation storage."""

    @pytest.mark.asyncio
    async def test_store_installation_success(self, initialized_plugin, mock_storage):
        """Test successful workspace installation storage."""
        # Arrange
        team_id = "T12345"
        access_token = "xoxb-test-token"
        bot_user_id = "U12345"
        team_name = "Test Workspace"

        expected_installation = PluginInstallation(
            id=1,
            plugin_name="slack",
            channel_id=team_id,
            access_token=access_token,
            metadata={"bot_user_id": bot_user_id, "team_name": team_name},
            is_active=True,
            installed_at=datetime.now(),
        )

        mock_storage.create_installation = AsyncMock(return_value=expected_installation)

        # Act
        result = await initialized_plugin.store_installation(
            team_id=team_id, access_token=access_token, bot_user_id=bot_user_id, team_name=team_name
        )

        # Assert
        assert result.id == 1
        assert result.channel_id == team_id
        assert result.plugin_name == "slack"
        assert result.is_active is True

        # Verify create_installation was called
        mock_storage.create_installation.assert_called_once()
        call_args = mock_storage.create_installation.call_args[0][0]
        assert call_args.channel_id == team_id
        assert call_args.access_token == access_token
        assert call_args.metadata["bot_user_id"] == bot_user_id

    @pytest.mark.asyncio
    async def test_store_installation_with_refresh_token(self, initialized_plugin, mock_storage):
        """Test storing installation with refresh token."""
        # Arrange
        team_id = "T12345"
        access_token = "xoxb-test-token"
        bot_user_id = "U12345"
        refresh_token = "xoxe-refresh-token"

        expected_installation = PluginInstallation(
            id=1,
            plugin_name="slack",
            channel_id=team_id,
            access_token=access_token,
            refresh_token=refresh_token,
            metadata={"bot_user_id": bot_user_id},
            is_active=True,
        )

        mock_storage.create_installation = AsyncMock(return_value=expected_installation)

        # Act
        result = await initialized_plugin.store_installation(
            team_id=team_id, access_token=access_token, bot_user_id=bot_user_id, refresh_token=refresh_token
        )

        # Assert
        assert result.refresh_token == refresh_token

    @pytest.mark.asyncio
    async def test_store_installation_already_exists(self, initialized_plugin, mock_storage):
        """Test storing installation when it already exists."""
        # Arrange
        team_id = "T12345"
        mock_storage.create_installation = AsyncMock(side_effect=ValueError("Installation already exists"))

        # Act & Assert
        with pytest.raises(ValueError, match="Installation already exists"):
            await initialized_plugin.store_installation(
                team_id=team_id, access_token="xoxb-test-token", bot_user_id="U12345"
            )

    @pytest.mark.asyncio
    async def test_store_installation_no_storage(self, slack_plugin):
        """Test storing installation when storage not initialized."""
        # Arrange
        slack_plugin.storage = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Installation storage not initialized"):
            await slack_plugin.store_installation(
                team_id="T12345", access_token="xoxb-test-token", bot_user_id="U12345"
            )


class TestVerifyInstallation:
    """Test workspace installation verification."""

    @pytest.mark.asyncio
    async def test_verify_installation_success(self, initialized_plugin, mock_storage):
        """Test successful workspace installation verification."""
        # Arrange
        team_id = "T12345"
        installation = PluginInstallation(
            id=1, plugin_name="slack", channel_id=team_id, access_token="xoxb-test-token", is_active=True
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        # Act
        result = await initialized_plugin.verify_installation(team_id)

        # Assert
        assert result is not None
        assert result.channel_id == team_id
        assert result.is_active is True
        mock_storage.get_installation.assert_called_once_with("slack", team_id)

    @pytest.mark.asyncio
    async def test_verify_installation_not_found(self, initialized_plugin, mock_storage):
        """Test verification when installation not found."""
        # Arrange
        team_id = "T12345"
        mock_storage.get_installation = AsyncMock(return_value=None)

        # Act
        result = await initialized_plugin.verify_installation(team_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_installation_inactive(self, initialized_plugin, mock_storage):
        """Test verification when installation is inactive."""
        # Arrange
        team_id = "T12345"
        installation = PluginInstallation(
            id=1,
            plugin_name="slack",
            channel_id=team_id,
            access_token="xoxb-test-token",
            is_active=False,  # Inactive
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        # Act
        result = await initialized_plugin.verify_installation(team_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_installation_no_storage(self, slack_plugin):
        """Test verification when storage not initialized."""
        # Arrange
        slack_plugin.storage = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Installation storage not initialized"):
            await slack_plugin.verify_installation("T12345")


class TestUninstallWorkspace:
    """Test workspace uninstall cleanup."""

    @pytest.mark.asyncio
    async def test_uninstall_workspace_success(self, initialized_plugin, mock_storage):
        """Test successful workspace uninstall."""
        # Arrange
        team_id = "T12345"
        mock_storage.delete_installation = AsyncMock(return_value=True)

        # Act
        result = await initialized_plugin.uninstall_workspace(team_id)

        # Assert
        assert result is True
        mock_storage.delete_installation.assert_called_once_with("slack", team_id)

    @pytest.mark.asyncio
    async def test_uninstall_workspace_not_found(self, initialized_plugin, mock_storage):
        """Test uninstall when installation not found."""
        # Arrange
        team_id = "T12345"
        mock_storage.delete_installation = AsyncMock(return_value=False)

        # Act
        result = await initialized_plugin.uninstall_workspace(team_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_uninstall_workspace_no_storage(self, slack_plugin):
        """Test uninstall when storage not initialized."""
        # Arrange
        slack_plugin.storage = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Installation storage not initialized"):
            await slack_plugin.uninstall_workspace("T12345")


class TestEnsureWorkspaceIsolation:
    """Test workspace data isolation."""

    @pytest.mark.asyncio
    async def test_ensure_workspace_isolation_success(self, initialized_plugin, mock_storage):
        """Test successful workspace isolation verification."""
        # Arrange
        team_id = "T12345"
        user_id = "U67890"

        installation = PluginInstallation(
            id=1, plugin_name="slack", channel_id=team_id, access_token="xoxb-test-token", is_active=True
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        # Act
        result = await initialized_plugin.ensure_workspace_isolation(team_id, user_id)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_workspace_isolation_no_installation(self, initialized_plugin, mock_storage):
        """Test isolation check when installation not found."""
        # Arrange
        team_id = "T12345"
        user_id = "U67890"
        mock_storage.get_installation = AsyncMock(return_value=None)

        # Act
        result = await initialized_plugin.ensure_workspace_isolation(team_id, user_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_workspace_isolation_invalid_user_id(self, initialized_plugin, mock_storage):
        """Test isolation check with invalid user ID format."""
        # Arrange
        team_id = "T12345"
        user_id = "INVALID"  # Should start with U or W

        installation = PluginInstallation(
            id=1, plugin_name="slack", channel_id=team_id, access_token="xoxb-test-token", is_active=True
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        # Act
        result = await initialized_plugin.ensure_workspace_isolation(team_id, user_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_workspace_isolation_valid_user_formats(self, initialized_plugin, mock_storage):
        """Test isolation check with valid user ID formats."""
        # Arrange
        team_id = "T12345"

        installation = PluginInstallation(
            id=1, plugin_name="slack", channel_id=team_id, access_token="xoxb-test-token", is_active=True
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        # Test with U prefix (regular user)
        result1 = await initialized_plugin.ensure_workspace_isolation(team_id, "U12345")
        assert result1 is True

        # Test with W prefix (workspace user)
        result2 = await initialized_plugin.ensure_workspace_isolation(team_id, "W12345")
        assert result2 is True


class TestUpdateInstallationToken:
    """Test OAuth token updates."""

    @pytest.mark.asyncio
    async def test_update_installation_token_success(self, initialized_plugin, mock_storage):
        """Test successful token update."""
        # Arrange
        team_id = "T12345"
        new_access_token = "xoxb-new-token"
        new_refresh_token = "xoxe-new-refresh"

        updated_installation = PluginInstallation(
            id=1,
            plugin_name="slack",
            channel_id=team_id,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            is_active=True,
        )

        mock_storage.update_installation = AsyncMock(return_value=updated_installation)

        # Act
        result = await initialized_plugin.update_installation_token(
            team_id=team_id, access_token=new_access_token, refresh_token=new_refresh_token
        )

        # Assert
        assert result is not None
        assert result.access_token == new_access_token
        assert result.refresh_token == new_refresh_token

        mock_storage.update_installation.assert_called_once_with(
            plugin_name="slack", channel_id=team_id, access_token=new_access_token, refresh_token=new_refresh_token
        )

    @pytest.mark.asyncio
    async def test_update_installation_token_not_found(self, initialized_plugin, mock_storage):
        """Test token update when installation not found."""
        # Arrange
        team_id = "T12345"
        mock_storage.update_installation = AsyncMock(return_value=None)

        # Act
        result = await initialized_plugin.update_installation_token(team_id=team_id, access_token="xoxb-new-token")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_update_installation_token_no_storage(self, slack_plugin):
        """Test token update when storage not initialized."""
        # Arrange
        slack_plugin.storage = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Installation storage not initialized"):
            await slack_plugin.update_installation_token(team_id="T12345", access_token="xoxb-new-token")


class TestListWorkspaceInstallations:
    """Test listing workspace installations."""

    @pytest.mark.asyncio
    async def test_list_workspace_installations_active_only(self, initialized_plugin, mock_storage):
        """Test listing active workspace installations."""
        # Arrange
        installations = [
            PluginInstallation(
                id=1, plugin_name="slack", channel_id="T12345", access_token="xoxb-token-1", is_active=True
            ),
            PluginInstallation(
                id=2, plugin_name="slack", channel_id="T67890", access_token="xoxb-token-2", is_active=True
            ),
        ]

        mock_storage.list_plugin_installations = AsyncMock(return_value=installations)

        # Act
        result = await initialized_plugin.list_workspace_installations(active_only=True)

        # Assert
        assert len(result) == 2
        assert all(inst.is_active for inst in result)

        mock_storage.list_plugin_installations.assert_called_once_with(plugin_name="slack", active_only=True)

    @pytest.mark.asyncio
    async def test_list_workspace_installations_all(self, initialized_plugin, mock_storage):
        """Test listing all workspace installations."""
        # Arrange
        installations = [
            PluginInstallation(
                id=1, plugin_name="slack", channel_id="T12345", access_token="xoxb-token-1", is_active=True
            ),
            PluginInstallation(
                id=2, plugin_name="slack", channel_id="T67890", access_token="xoxb-token-2", is_active=False
            ),
        ]

        mock_storage.list_plugin_installations = AsyncMock(return_value=installations)

        # Act
        result = await initialized_plugin.list_workspace_installations(active_only=False)

        # Assert
        assert len(result) == 2

        mock_storage.list_plugin_installations.assert_called_once_with(plugin_name="slack", active_only=False)

    @pytest.mark.asyncio
    async def test_list_workspace_installations_no_storage(self, slack_plugin):
        """Test listing when storage not initialized."""
        # Arrange
        slack_plugin.storage = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Installation storage not initialized"):
            await slack_plugin.list_workspace_installations()


class TestHandleMessageWithVerification:
    """Test handle_message with workspace verification."""

    @pytest.mark.asyncio
    async def test_handle_message_verifies_installation(self, initialized_plugin, mock_storage, mock_core_api):
        """Test that handle_message verifies workspace installation."""
        # Arrange
        installation = PluginInstallation(
            id=1, plugin_name="slack", channel_id="T12345", access_token="xoxb-test-token", is_active=True
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        # Mock core API response
        from triage.core.actions_api import CoreActionResult

        mock_core_api.get_status = AsyncMock(return_value=CoreActionResult(success=True, data={"status": "not_found"}))

        message = PluginMessage(channel_id="T12345", user_id="U67890", content="", command="status")

        # Act
        response = await initialized_plugin.handle_message(message)

        # Assert
        # get_installation is called twice: once in verify_installation and once in ensure_workspace_isolation
        assert mock_storage.get_installation.call_count == 2
        mock_storage.get_installation.assert_called_with("slack", "T12345")
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_handle_message_rejects_uninstalled_workspace(self, initialized_plugin, mock_storage):
        """Test that handle_message rejects requests from uninstalled workspaces."""
        # Arrange
        mock_storage.get_installation = AsyncMock(return_value=None)

        message = PluginMessage(channel_id="T12345", user_id="U67890", content="", command="status")

        # Act
        response = await initialized_plugin.handle_message(message)

        # Assert
        assert "not installed" in response.content.lower()
        assert response.response_type == "ephemeral"

    @pytest.mark.asyncio
    async def test_handle_message_rejects_isolation_failure(self, initialized_plugin, mock_storage):
        """Test that handle_message rejects requests that fail isolation check."""
        # Arrange
        installation = PluginInstallation(
            id=1, plugin_name="slack", channel_id="T12345", access_token="xoxb-test-token", is_active=True
        )

        mock_storage.get_installation = AsyncMock(return_value=installation)

        message = PluginMessage(
            channel_id="T12345",
            user_id="INVALID",  # Invalid user ID format
            content="",
            command="status",
        )

        # Act
        response = await initialized_plugin.handle_message(message)

        # Assert
        assert "unable to process" in response.content.lower()
        assert response.response_type == "ephemeral"
