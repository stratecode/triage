# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for plugin configuration initialization.

Feature: plugin-architecture
"""

import asyncio
from typing import Any, Dict

from hypothesis import given
from hypothesis import strategies as st

from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from triage.plugins.registry import PluginRegistry


# Custom strategies for generating test data
@st.composite
def plugin_config_strategy(draw):
    """Generate random PluginConfig objects."""
    # Generate version string like "1.0.0"
    major = draw(st.integers(min_value=0, max_value=9))
    minor = draw(st.integers(min_value=0, max_value=9))
    patch = draw(st.integers(min_value=0, max_value=9))
    version = f"{major}.{minor}.{patch}"

    # Generate plugin name (alphanumeric, lowercase)
    plugin_name = draw(
        st.text(
            min_size=3,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("Ll",), min_codepoint=97, max_codepoint=122),
        )
    )

    # Generate config dictionary
    config_dict = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))),
            st.one_of(st.text(max_size=50), st.integers(min_value=0, max_value=10000), st.booleans()),
            min_size=0,
            max_size=10,
        )
    )

    return PluginConfig(
        plugin_name=plugin_name, plugin_version=version, enabled=draw(st.booleans()), config=config_dict
    )


class MockCoreActionsAPI:
    """Mock Core Actions API for testing."""

    async def generate_plan(self, user_id: str, **kwargs):
        return {"success": True, "plan": "mock_plan"}

    async def approve_plan(self, user_id: str, **kwargs):
        return {"success": True}

    async def get_status(self, user_id: str, **kwargs):
        return {"success": True, "status": "active"}


class TestPlugin(PluginInterface):
    """Test plugin implementation for property testing."""

    def __init__(self):
        self.initialized_config = None
        self.initialized_core_api = None
        self.started = False
        self.stopped = False

    def get_name(self) -> str:
        return "test_plugin"

    def get_version(self) -> str:
        return "1.0.0"

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "timeout": {"type": "integer"},
                "enabled": {"type": "boolean"},
            },
        }

    async def initialize(self, config: PluginConfig, core_api: "CoreActionsAPI") -> None:
        """Store the config and core API for verification."""
        self.initialized_config = config
        self.initialized_core_api = core_api

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def health_check(self) -> PluginStatus:
        return PluginStatus.HEALTHY

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        return PluginResponse(content="Test response")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        return True

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        pass


# Property 4: Plugin Configuration Initialization
@given(plugin_config_strategy())
def test_property_4_plugin_configuration_initialization(config: PluginConfig):
    """Property 4: Plugin Configuration Initialization

    For any valid plugin and configuration, when the Plugin_Registry initializes
    the plugin, the plugin should receive its complete configuration.

    Feature: plugin-architecture, Property 4: Plugin Configuration Initialization
    Validates: Requirements 3.3
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin instance
    plugin = TestPlugin()

    # Initialize the plugin with the config
    async def run_test():
        await plugin.initialize(config, core_api)

        # Verify plugin received the configuration
        assert plugin.initialized_config is not None, "Plugin should receive configuration during initialization"

        # Verify the configuration matches what was passed
        assert plugin.initialized_config.plugin_name == config.plugin_name, "Plugin should receive correct plugin_name"
        assert (
            plugin.initialized_config.plugin_version == config.plugin_version
        ), "Plugin should receive correct plugin_version"
        assert plugin.initialized_config.enabled == config.enabled, "Plugin should receive correct enabled flag"

        # Verify the config dictionary is complete
        assert plugin.initialized_config.config == config.config, "Plugin should receive complete config dictionary"

        # Verify all config keys are present
        for key in config.config.keys():
            assert key in plugin.initialized_config.config, f"Plugin config should contain key: {key}"
            assert (
                plugin.initialized_config.config[key] == config.config[key]
            ), f"Plugin config value for {key} should match"

        # Verify plugin received the core API
        assert plugin.initialized_core_api is not None, "Plugin should receive core API during initialization"
        assert plugin.initialized_core_api is core_api, "Plugin should receive the same core API instance"

    # Run the async test
    asyncio.run(run_test())


@given(plugin_config_strategy())
def test_property_4_plugin_configuration_initialization_via_registry(config: PluginConfig):
    """Property 4: Plugin Configuration Initialization (via Registry)

    For any valid plugin and configuration, when the Plugin_Registry loads
    the plugin, the plugin should be initialized with its complete configuration.

    Feature: plugin-architecture, Property 4: Plugin Configuration Initialization
    Validates: Requirements 3.3
    """
    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin registry
    registry = PluginRegistry(core_api)

    # Manually add the test plugin to the registry (simulating load)
    plugin = TestPlugin()

    async def run_test():
        # Initialize plugin through the interface
        await plugin.initialize(config, core_api)

        # Store in registry
        registry.plugins[plugin.get_name()] = plugin
        registry.plugin_health[plugin.get_name()] = PluginStatus.HEALTHY

        # Verify plugin is in registry
        loaded_plugin = registry.get_plugin(plugin.get_name())
        assert loaded_plugin is not None, "Plugin should be loaded in registry"

        # Verify the loaded plugin has the configuration
        assert loaded_plugin.initialized_config is not None, "Loaded plugin should have configuration"
        assert (
            loaded_plugin.initialized_config.plugin_name == config.plugin_name
        ), "Loaded plugin should have correct plugin_name"
        assert (
            loaded_plugin.initialized_config.config == config.config
        ), "Loaded plugin should have complete config dictionary"

        # Verify the loaded plugin has access to core API
        assert loaded_plugin.initialized_core_api is not None, "Loaded plugin should have core API access"

    # Run the async test
    asyncio.run(run_test())


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))),
        st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
        min_size=1,
        max_size=10,
    )
)
def test_property_4_plugin_configuration_initialization_config_completeness(config_dict: Dict[str, Any]):
    """Property 4: Plugin Configuration Initialization (Config Completeness)

    For any configuration dictionary, when passed to a plugin during initialization,
    all keys and values should be accessible to the plugin.

    Feature: plugin-architecture, Property 4: Plugin Configuration Initialization
    Validates: Requirements 3.3
    """
    # Create a config with the random dictionary
    config = PluginConfig(plugin_name="test_plugin", plugin_version="1.0.0", enabled=True, config=config_dict)

    # Create mock core API
    core_api = MockCoreActionsAPI()

    # Create plugin instance
    plugin = TestPlugin()

    async def run_test():
        # Initialize the plugin
        await plugin.initialize(config, core_api)

        # Verify all keys from the original config are present
        for key, value in config_dict.items():
            assert key in plugin.initialized_config.config, f"Plugin config should contain key: {key}"
            assert (
                plugin.initialized_config.config[key] == value
            ), f"Plugin config value for {key} should match original value"

        # Verify no extra keys were added
        assert len(plugin.initialized_config.config) == len(
            config_dict
        ), "Plugin config should have same number of keys as original"

    # Run the async test
    asyncio.run(run_test())
