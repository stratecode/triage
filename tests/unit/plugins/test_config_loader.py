# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for plugin configuration loader.

Tests configuration loading from environment variables, YAML/TOML files,
schema validation, and default value application.
"""

import pytest

from triage.plugins.config_loader import ConfigLoader, ConfigurationError, load_all_plugin_configs


class TestConfigLoader:
    """Test suite for ConfigLoader."""

    def test_load_from_env_simple(self, monkeypatch):
        """Test loading simple configuration from environment variables."""
        # Set environment variables
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("PLUGIN_SLACK_ENABLED", "true")

        schema = {
            "type": "object",
            "properties": {"client_id": {"type": "string"}, "client_secret": {"type": "string"}},
        }

        loader = ConfigLoader()
        config = loader.load_plugin_config("slack", "1.0.0", schema)

        assert config.plugin_name == "slack"
        assert config.plugin_version == "1.0.0"
        assert config.enabled is True
        assert config.config["client_id"] == "test-client-id"
        assert config.config["client_secret"] == "test-secret"

    def test_load_from_env_nested(self, monkeypatch):
        """Test loading nested configuration from environment variables."""
        monkeypatch.setenv("PLUGIN_SLACK_OAUTH__CLIENT_ID", "nested-id")
        monkeypatch.setenv("PLUGIN_SLACK_OAUTH__CLIENT_SECRET", "nested-secret")

        schema = {
            "type": "object",
            "properties": {
                "oauth": {
                    "type": "object",
                    "properties": {"client_id": {"type": "string"}, "client_secret": {"type": "string"}},
                }
            },
        }

        loader = ConfigLoader()
        config = loader.load_plugin_config("slack", "1.0.0", schema)

        assert config.config["oauth"]["client_id"] == "nested-id"
        assert config.config["oauth"]["client_secret"] == "nested-secret"

    def test_load_from_env_type_parsing(self, monkeypatch):
        """Test parsing of different types from environment variables."""
        monkeypatch.setenv("PLUGIN_TEST_PORT", "8080")
        monkeypatch.setenv("PLUGIN_TEST_DEBUG", "true")
        monkeypatch.setenv("PLUGIN_TEST_TIMEOUT", "30.5")
        monkeypatch.setenv("PLUGIN_TEST_TAGS", '["tag1", "tag2"]')

        schema = {
            "type": "object",
            "properties": {
                "port": {"type": "integer"},
                "debug": {"type": "boolean"},
                "timeout": {"type": "number"},
                "tags": {"type": "array"},
            },
        }

        loader = ConfigLoader()
        config = loader.load_plugin_config("test", "1.0.0", schema)

        assert config.config["port"] == 8080
        assert config.config["debug"] is True
        assert config.config["timeout"] == 30.5
        assert config.config["tags"] == ["tag1", "tag2"]

    def test_load_from_yaml_file(self, tmp_path):
        """Test loading configuration from YAML file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        yaml_content = """
client_id: yaml-client-id
client_secret: yaml-secret
signing_secret: yaml-signing
"""
        yaml_file = config_dir / "slack.yaml"
        yaml_file.write_text(yaml_content)

        schema = {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "client_secret": {"type": "string"},
                "signing_secret": {"type": "string"},
            },
        }

        loader = ConfigLoader(str(config_dir))
        config = loader.load_plugin_config("slack", "1.0.0", schema)

        assert config.config["client_id"] == "yaml-client-id"
        assert config.config["client_secret"] == "yaml-secret"
        assert config.config["signing_secret"] == "yaml-signing"

    def test_load_from_toml_file(self, tmp_path):
        """Test loading configuration from TOML file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        toml_content = """
client_id = "toml-client-id"
client_secret = "toml-secret"
port = 9000
"""
        toml_file = config_dir / "slack.toml"
        toml_file.write_text(toml_content)

        schema = {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "client_secret": {"type": "string"},
                "port": {"type": "integer"},
            },
        }

        loader = ConfigLoader(str(config_dir))
        config = loader.load_plugin_config("slack", "1.0.0", schema)

        assert config.config["client_id"] == "toml-client-id"
        assert config.config["client_secret"] == "toml-secret"
        assert config.config["port"] == 9000

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        """Test that environment variables override file configuration."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        yaml_content = """
client_id: yaml-id
client_secret: yaml-secret
"""
        yaml_file = config_dir / "slack.yaml"
        yaml_file.write_text(yaml_content)

        # Environment variable should override file
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "env-id")

        schema = {
            "type": "object",
            "properties": {"client_id": {"type": "string"}, "client_secret": {"type": "string"}},
        }

        loader = ConfigLoader(str(config_dir))
        config = loader.load_plugin_config("slack", "1.0.0", schema)

        assert config.config["client_id"] == "env-id"
        assert config.config["client_secret"] == "yaml-secret"

    def test_default_values_from_schema(self):
        """Test that default values are applied from schema."""
        schema = {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "default": 30},
                "retries": {"type": "integer", "default": 3},
                "debug": {"type": "boolean", "default": False},
            },
        }

        loader = ConfigLoader()
        config = loader.load_plugin_config("test", "1.0.0", schema)

        assert config.config["timeout"] == 30
        assert config.config["retries"] == 3
        assert config.config["debug"] is False

    def test_validation_success(self):
        """Test successful schema validation."""
        schema = {
            "type": "object",
            "required": ["client_id", "client_secret"],
            "properties": {"client_id": {"type": "string"}, "client_secret": {"type": "string"}},
        }

        loader = ConfigLoader()
        # This should not raise an exception
        loader._validate_config("test", {"client_id": "test-id", "client_secret": "test-secret"}, schema)

    def test_validation_missing_required(self, monkeypatch):
        """Test validation failure for missing required fields."""
        schema = {
            "type": "object",
            "required": ["client_id", "client_secret"],
            "properties": {"client_id": {"type": "string"}, "client_secret": {"type": "string"}},
        }

        # Only set one required field
        monkeypatch.setenv("PLUGIN_TEST_CLIENT_ID", "test-id")

        loader = ConfigLoader()

        with pytest.raises(ConfigurationError) as exc_info:
            loader.load_plugin_config("test", "1.0.0", schema)

        assert "client_secret" in str(exc_info.value).lower()

    def test_validation_wrong_type(self, monkeypatch):
        """Test validation failure for wrong type."""
        schema = {"type": "object", "properties": {"port": {"type": "integer"}}}

        # Set port as string that can't be parsed as integer
        monkeypatch.setenv("PLUGIN_TEST_PORT", "not-a-number")

        loader = ConfigLoader()

        with pytest.raises(ConfigurationError):
            loader.load_plugin_config("test", "1.0.0", schema)

    def test_plugin_disabled(self, monkeypatch):
        """Test that disabled plugins are marked correctly."""
        monkeypatch.setenv("PLUGIN_TEST_ENABLED", "false")

        schema = {"type": "object", "properties": {}}

        loader = ConfigLoader()
        config = loader.load_plugin_config("test", "1.0.0", schema)

        assert config.enabled is False

    def test_plugin_enabled_variations(self, monkeypatch):
        """Test various ways to enable a plugin."""
        schema = {"type": "object", "properties": {}}
        loader = ConfigLoader()

        # Test different true values
        for value in ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]:
            monkeypatch.setenv("PLUGIN_TEST_ENABLED", value)
            config = loader.load_plugin_config("test", "1.0.0", schema)
            assert config.enabled is True, f"Failed for value: {value}"

        # Test false values
        for value in ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]:
            monkeypatch.setenv("PLUGIN_TEST_ENABLED", value)
            config = loader.load_plugin_config("test", "1.0.0", schema)
            assert config.enabled is False, f"Failed for value: {value}"


class TestLoadAllPluginConfigs:
    """Test suite for load_all_plugin_configs function."""

    def test_load_multiple_plugins(self, monkeypatch):
        """Test loading configurations for multiple plugins."""
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "slack-id")
        monkeypatch.setenv("PLUGIN_WHATSAPP_API_KEY", "whatsapp-key")

        schemas = {
            "slack": {"type": "object", "properties": {"client_id": {"type": "string"}}},
            "whatsapp": {"type": "object", "properties": {"api_key": {"type": "string"}}},
        }

        versions = {"slack": "1.0.0", "whatsapp": "1.0.0"}

        configs = load_all_plugin_configs(["slack", "whatsapp"], schemas, versions)

        assert "slack" in configs
        assert "whatsapp" in configs
        assert configs["slack"].config["client_id"] == "slack-id"
        assert configs["whatsapp"].config["api_key"] == "whatsapp-key"

    def test_load_fails_on_invalid_config(self, monkeypatch):
        """Test that loading fails if any plugin has invalid config."""
        monkeypatch.setenv("PLUGIN_SLACK_CLIENT_ID", "slack-id")
        # Missing required field for whatsapp

        schemas = {
            "slack": {"type": "object", "properties": {"client_id": {"type": "string"}}},
            "whatsapp": {"type": "object", "required": ["api_key"], "properties": {"api_key": {"type": "string"}}},
        }

        versions = {"slack": "1.0.0", "whatsapp": "1.0.0"}

        with pytest.raises(ConfigurationError):
            load_all_plugin_configs(["slack", "whatsapp"], schemas, versions)
