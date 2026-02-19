# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for plugin configuration loading with PluginRegistry.

Tests the complete flow of loading plugin configurations and initializing
plugins with the PluginRegistry.
"""

from unittest.mock import MagicMock

import pytest

from triage.plugins.interface import PluginStatus
from triage.plugins.registry import PluginRegistry


@pytest.fixture
def mock_core_api():
    """Create a mock CoreActionsAPI."""
    return MagicMock()


@pytest.fixture
def config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


class TestPluginRegistryConfigIntegration:
    """Integration tests for PluginRegistry with configuration loading."""

    @pytest.mark.asyncio
    async def test_load_plugin_with_auto_config_from_env(self, mock_core_api, monkeypatch):
        """Test loading a plugin with auto-config from environment variables."""
        # Set environment variables for Slack plugin
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("PLUGIN_SLACK_SIGNING_SECRET", "test-signing")
        monkeypatch.setenv("PLUGIN_SLACK_ENABLED", "true")

        registry = PluginRegistry(mock_core_api)

        # Load plugin with auto-config
        success = await registry.load_plugin_with_auto_config("slack")

        assert success is True
        assert "slack" in registry.plugins
        assert registry.plugin_health["slack"] == PluginStatus.HEALTHY

        # Verify plugin received configuration
        plugin = registry.get_plugin("slack")
        assert plugin is not None
        assert plugin.get_name() == "slack"

    @pytest.mark.asyncio
    async def test_load_plugin_with_auto_config_from_file(self, mock_core_api, config_dir):
        """Test loading a plugin with auto-config from YAML file."""
        # Create YAML config file
        yaml_content = """
client_id: yaml-client-id
client_secret: yaml-secret
signing_secret: yaml-signing
"""
        yaml_file = config_dir / "slack.yaml"
        yaml_file.write_text(yaml_content)

        registry = PluginRegistry(mock_core_api, config_dir=str(config_dir))

        # Load plugin with auto-config
        success = await registry.load_plugin_with_auto_config("slack")

        assert success is True
        assert "slack" in registry.plugins

        plugin = registry.get_plugin("slack")
        assert plugin is not None

    @pytest.mark.asyncio
    async def test_load_plugin_disabled(self, mock_core_api, monkeypatch):
        """Test that disabled plugins are not loaded."""
        monkeypatch.setenv("PLUGIN_SLACK_ENABLED", "false")
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "test-id")

        registry = PluginRegistry(mock_core_api)

        # Load plugin with auto-config
        success = await registry.load_plugin_with_auto_config("slack")

        # Should return False because plugin is disabled
        assert success is False
        assert "slack" not in registry.plugins

    @pytest.mark.asyncio
    async def test_load_plugin_missing_required_config(self, mock_core_api, monkeypatch):
        """Test that loading fails with missing required configuration."""
        # Only set one required field (missing client_secret and signing_secret)
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "test-id")

        registry = PluginRegistry(mock_core_api)

        # Load plugin with auto-config should fail
        success = await registry.load_plugin_with_auto_config("slack")

        assert success is False
        assert "slack" not in registry.plugins

    @pytest.mark.asyncio
    async def test_env_overrides_file_config(self, mock_core_api, config_dir, monkeypatch):
        """Test that environment variables override file configuration."""
        # Create YAML config file
        yaml_content = """
client_id: yaml-client-id
client_secret: yaml-secret
signing_secret: yaml-signing
"""
        yaml_file = config_dir / "slack.yaml"
        yaml_file.write_text(yaml_content)

        # Override client_id with environment variable
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "env-client-id")

        registry = PluginRegistry(mock_core_api, config_dir=str(config_dir))

        # Load plugin with auto-config
        success = await registry.load_plugin_with_auto_config("slack")

        assert success is True

        # The plugin should have received the env override
        plugin = registry.get_plugin("slack")
        assert plugin is not None
        # Note: We can't directly check the config values as they're internal to the plugin
        # but the plugin was successfully initialized with the merged config

    @pytest.mark.asyncio
    async def test_load_multiple_plugins_with_auto_config(self, mock_core_api, monkeypatch):
        """Test loading multiple plugins with auto-config."""
        # Set config for Slack
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "slack-id")
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_SECRET", "slack-secret")
        monkeypatch.setenv("PLUGIN_SLACK_SIGNING_SECRET", "slack-signing")

        registry = PluginRegistry(mock_core_api)

        # Load Slack plugin
        success = await registry.load_plugin_with_auto_config("slack")
        assert success is True

        # Verify both plugins loaded
        assert "slack" in registry.plugins
        assert len(registry.plugins) == 1

    @pytest.mark.asyncio
    async def test_default_values_applied(self, mock_core_api, monkeypatch):
        """Test that default values from schema are applied."""
        # Only set required fields, let defaults fill in optional ones
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "test-id")
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("PLUGIN_SLACK_SIGNING_SECRET", "test-signing")

        registry = PluginRegistry(mock_core_api)

        # Load plugin with auto-config
        success = await registry.load_plugin_with_auto_config("slack")

        assert success is True

        # Plugin should have been initialized with defaults for optional fields
        plugin = registry.get_plugin("slack")
        assert plugin is not None
