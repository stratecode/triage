# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Configuration Loader

Loads and validates plugin configurations from multiple sources:
- Environment variables (PLUGIN_<NAME>_<KEY> pattern)
- YAML configuration files
- TOML configuration files

Validates configurations against plugin-declared JSON schemas and applies
default values for optional configuration parameters.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import tomli

    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False

try:
    import jsonschema

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from triage.plugins.interface import PluginConfig

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when plugin configuration is invalid."""

    pass


class ConfigLoader:
    """
    Loads and validates plugin configurations from multiple sources.

    Configuration sources are merged in the following order (later sources override):
    1. Default values from schema
    2. Configuration files (YAML/TOML)
    3. Environment variables
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the configuration loader.

        Args:
            config_dir: Optional directory containing config files
        """
        self.config_dir = Path(config_dir) if config_dir else None
        self.logger = logging.getLogger(__name__)

    def load_plugin_config(self, plugin_name: str, plugin_version: str, config_schema: Dict[str, Any]) -> PluginConfig:
        """
        Load and validate configuration for a plugin.

        Args:
            plugin_name: Name of the plugin
            plugin_version: Version of the plugin
            config_schema: JSON schema for validation

        Returns:
            PluginConfig: Validated plugin configuration

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Start with defaults from schema
        config = self._extract_defaults_from_schema(config_schema)

        # Load from config file if available
        file_config = self._load_from_file(plugin_name)
        if file_config:
            config.update(file_config)

        # Override with environment variables
        env_config = self._load_from_env(plugin_name)
        config.update(env_config)

        # Check if plugin is enabled
        enabled = config.pop("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("true", "1", "yes", "on")

        # Validate against schema
        self._validate_config(plugin_name, config, config_schema)

        return PluginConfig(
            plugin_name=plugin_name, plugin_version=plugin_version, enabled=bool(enabled), config=config
        )

    def _extract_defaults_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract default values from JSON schema.

        Args:
            schema: JSON schema object

        Returns:
            Dict[str, Any]: Default configuration values
        """
        defaults = {}

        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if "default" in prop_schema:
                defaults[key] = prop_schema["default"]

        return defaults

    def _load_from_file(self, plugin_name: str) -> Dict[str, Any]:
        """
        Load configuration from YAML or TOML file.

        Looks for files in the following order:
        1. {config_dir}/{plugin_name}.yaml
        2. {config_dir}/{plugin_name}.yml
        3. {config_dir}/{plugin_name}.toml

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dict[str, Any]: Configuration from file or empty dict
        """
        if not self.config_dir or not self.config_dir.exists():
            return {}

        # Try YAML files
        if YAML_AVAILABLE:
            for ext in [".yaml", ".yml"]:
                config_file = self.config_dir / f"{plugin_name}{ext}"
                if config_file.exists():
                    try:
                        with open(config_file, "r") as f:
                            config = yaml.safe_load(f)
                            self.logger.info(f"Loaded config for {plugin_name} from {config_file}")
                            return config or {}
                    except Exception as e:
                        self.logger.error(f"Failed to load YAML config from {config_file}: {e}")

        # Try TOML file
        if TOML_AVAILABLE:
            config_file = self.config_dir / f"{plugin_name}.toml"
            if config_file.exists():
                try:
                    with open(config_file, "rb") as f:
                        config = tomli.load(f)
                        self.logger.info(f"Loaded config for {plugin_name} from {config_file}")
                        return config or {}
                except Exception as e:
                    self.logger.error(f"Failed to load TOML config from {config_file}: {e}")

        return {}

    def _load_from_env(self, plugin_name: str) -> Dict[str, Any]:
        """
        Load configuration from environment variables.

        Environment variables follow the pattern: PLUGIN_<NAME>_<KEY>
        Example: PLUGIN_SLACK_CLIENT_ID

        Nested keys use double underscores: PLUGIN_SLACK_OAUTH__CLIENT_ID

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dict[str, Any]: Configuration from environment variables
        """
        config = {}
        prefix = f"PLUGIN_{plugin_name.upper()}_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Extract config key (remove prefix)
                config_key = key[len(prefix) :].lower()

                # Handle nested keys (double underscore)
                if "__" in config_key:
                    parts = config_key.split("__")
                    self._set_nested_value(config, parts, value)
                else:
                    config[config_key] = self._parse_env_value(value)

        if config:
            self.logger.info(f"Loaded {len(config)} config values for {plugin_name} from environment")

        return config

    def _set_nested_value(self, config: Dict[str, Any], keys: List[str], value: str) -> None:
        """
        Set a nested configuration value.

        Args:
            config: Configuration dictionary
            keys: List of nested keys
            value: Value to set
        """
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = self._parse_env_value(value)

    def _parse_env_value(self, value: str) -> Any:
        """
        Parse environment variable value to appropriate type.

        Attempts to parse as JSON first, then falls back to string.

        Args:
            value: String value from environment

        Returns:
            Any: Parsed value
        """
        # Try parsing as JSON (handles booleans, numbers, arrays, objects)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            # Return as string
            return value

    def _validate_config(self, plugin_name: str, config: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """
        Validate configuration against JSON schema.

        Args:
            plugin_name: Name of the plugin (for error messages)
            config: Configuration to validate
            schema: JSON schema

        Raises:
            ConfigurationError: If validation fails
        """
        if not JSONSCHEMA_AVAILABLE:
            self.logger.warning(
                "jsonschema not available, skipping config validation. " "Install with: uv pip install jsonschema"
            )
            return

        try:
            jsonschema.validate(instance=config, schema=schema)
            self.logger.info(f"Configuration for {plugin_name} validated successfully")
        except jsonschema.ValidationError as e:
            error_msg = (
                f"Invalid configuration for plugin '{plugin_name}': "
                f"{e.message} at {'.'.join(str(p) for p in e.path)}"
            )
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
        except jsonschema.SchemaError as e:
            error_msg = f"Invalid schema for plugin '{plugin_name}': {e.message}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e


def load_all_plugin_configs(
    plugin_names: List[str],
    plugin_schemas: Dict[str, Dict[str, Any]],
    plugin_versions: Dict[str, str],
    config_dir: Optional[str] = None,
) -> Dict[str, PluginConfig]:
    """
    Load configurations for multiple plugins.

    Args:
        plugin_names: List of plugin names to load
        plugin_schemas: Dictionary mapping plugin names to their schemas
        plugin_versions: Dictionary mapping plugin names to their versions
        config_dir: Optional directory containing config files

    Returns:
        Dict[str, PluginConfig]: Dictionary mapping plugin names to their configs

    Raises:
        ConfigurationError: If any plugin configuration is invalid
    """
    loader = ConfigLoader(config_dir)
    configs = {}

    for plugin_name in plugin_names:
        schema = plugin_schemas.get(plugin_name, {"type": "object", "properties": {}})
        version = plugin_versions.get(plugin_name, "unknown")

        try:
            config = loader.load_plugin_config(plugin_name, version, schema)
            configs[plugin_name] = config
        except ConfigurationError as e:
            logger.error(f"Failed to load config for {plugin_name}: {e}")
            raise

    return configs
