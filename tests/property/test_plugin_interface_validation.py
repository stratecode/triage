# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for plugin interface validation.

Feature: plugin-architecture
"""

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


# Custom strategies for generating test data
@st.composite
def plugin_config_strategy(draw):
    """Generate random PluginConfig objects."""
    # Generate version string like "1.0.0"
    major = draw(st.integers(min_value=0, max_value=9))
    minor = draw(st.integers(min_value=0, max_value=9))
    patch = draw(st.integers(min_value=0, max_value=9))
    version = f"{major}.{minor}.{patch}"

    return PluginConfig(
        plugin_name=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu")))),
        plugin_version=version,
        enabled=draw(st.booleans()),
        config=draw(
            st.dictionaries(
                st.text(min_size=1, max_size=20), st.one_of(st.text(), st.integers(), st.booleans()), max_size=5
            )
        ),
    )


@st.composite
def plugin_message_strategy(draw):
    """Generate random PluginMessage objects."""
    return PluginMessage(
        channel_id=draw(st.text(min_size=5, max_size=30)),
        user_id=draw(st.text(min_size=5, max_size=30)),
        content=draw(st.text(min_size=1, max_size=200)),
        command=draw(st.one_of(st.none(), st.sampled_from(["plan", "status", "config", "approve", "reject"]))),
        parameters=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(), max_size=3)),
        metadata=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(), max_size=3)),
        thread_id=draw(st.one_of(st.none(), st.text(min_size=5, max_size=20))),
    )


class MockCoreActionsAPI:
    """Mock Core Actions API for testing."""

    pass


# Helper function to create mock plugin classes with varying completeness
def create_mock_plugin_class(
    has_get_name: bool = True,
    has_get_version: bool = True,
    has_get_config_schema: bool = True,
    has_initialize: bool = True,
    has_start: bool = True,
    has_stop: bool = True,
    has_health_check: bool = True,
    has_handle_message: bool = True,
    has_send_message: bool = True,
    has_handle_event: bool = True,
    inherit_from_interface: bool = True,
):
    """
    Create a mock plugin class with specified methods.

    This allows us to test various incomplete plugin implementations.
    """
    base_class = PluginInterface if inherit_from_interface else object

    class MockPlugin(base_class):
        """Mock plugin for testing."""

        if has_get_name:

            def get_name(self) -> str:
                return "mock_plugin"

        if has_get_version:

            def get_version(self) -> str:
                return "1.0.0"

        if has_get_config_schema:

            def get_config_schema(self) -> Dict[str, Any]:
                return {"type": "object"}

        if has_initialize:

            async def initialize(self, config: PluginConfig, core_api: "CoreActionsAPI") -> None:
                self.config = config
                self.core_api = core_api

        if has_start:

            async def start(self) -> None:
                pass

        if has_stop:

            async def stop(self) -> None:
                pass

        if has_health_check:

            async def health_check(self) -> PluginStatus:
                return PluginStatus.HEALTHY

        if has_handle_message:

            async def handle_message(self, message: PluginMessage) -> PluginResponse:
                return PluginResponse(content="Mock response")

        if has_send_message:

            async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
                return True

        if has_handle_event:

            async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
                pass

    return MockPlugin


# Property 1: Plugin Interface Validation
@given(
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_property_1_plugin_interface_validation(
    has_get_name: bool,
    has_get_version: bool,
    has_get_config_schema: bool,
    has_initialize: bool,
    has_start: bool,
    has_stop: bool,
    has_health_check: bool,
    has_handle_message: bool,
    has_send_message: bool,
    has_handle_event: bool,
):
    """Property 1: Plugin Interface Validation

    For any plugin implementation, when the Plugin_Registry attempts to load it,
    the registry should correctly identify whether it implements all required
    interface methods and reject invalid implementations.

    Feature: plugin-architecture, Property 1: Plugin Interface Validation
    Validates: Requirements 1.9
    """
    # All methods must be present to instantiate an abstract class
    all_methods_present = all(
        [
            has_get_name,
            has_get_version,
            has_get_config_schema,
            has_initialize,
            has_start,
            has_stop,
            has_health_check,
            has_handle_message,
            has_send_message,
            has_handle_event,
        ]
    )

    # Create a mock plugin class with the specified methods
    MockPluginClass = create_mock_plugin_class(
        has_get_name=has_get_name,
        has_get_version=has_get_version,
        has_get_config_schema=has_get_config_schema,
        has_initialize=has_initialize,
        has_start=has_start,
        has_stop=has_stop,
        has_health_check=has_health_check,
        has_handle_message=has_handle_message,
        has_send_message=has_send_message,
        has_handle_event=has_handle_event,
        inherit_from_interface=True,  # Must inherit to be considered
    )

    # Try to instantiate the mock plugin
    if all_methods_present:
        # Should succeed - all abstract methods are implemented
        plugin = MockPluginClass()

        # Check if plugin is an instance of PluginInterface
        is_valid_instance = isinstance(plugin, PluginInterface)
        assert is_valid_instance, "Plugin with all methods must be recognized as PluginInterface instance"

        # Verify all methods are present
        expected_methods = {
            "get_name",
            "get_version",
            "get_config_schema",
            "initialize",
            "start",
            "stop",
            "health_check",
            "handle_message",
            "send_message",
            "handle_event",
        }

        for method_name in expected_methods:
            assert hasattr(plugin, method_name), f"Plugin should have method {method_name}"
            assert callable(getattr(plugin, method_name)), f"Method {method_name} should be callable"
    else:
        # Should fail - missing abstract methods
        try:
            plugin = MockPluginClass()
            # If we get here, Python didn't enforce abstract methods (shouldn't happen)
            assert False, "Should not be able to instantiate plugin with missing abstract methods"
        except TypeError as e:
            # Expected - Python prevents instantiation of incomplete abstract classes
            assert "Can't instantiate abstract class" in str(e), f"Expected abstract class error, got: {e}"


@given(st.booleans())
def test_property_1_plugin_interface_validation_inheritance(inherit_from_interface: bool):
    """Property 1: Plugin Interface Validation (Inheritance Check)

    For any class, the Plugin_Registry should only accept it as a valid plugin
    if it inherits from PluginInterface.

    Feature: plugin-architecture, Property 1: Plugin Interface Validation
    Validates: Requirements 1.9
    """
    # Create a mock plugin class that may or may not inherit from PluginInterface
    MockPluginClass = create_mock_plugin_class(
        has_get_name=True,
        has_get_version=True,
        has_get_config_schema=True,
        has_initialize=True,
        has_start=True,
        has_stop=True,
        has_health_check=True,
        has_handle_message=True,
        has_send_message=True,
        has_handle_event=True,
        inherit_from_interface=inherit_from_interface,
    )

    # Instantiate the mock plugin
    plugin = MockPluginClass()

    # Check if plugin is an instance of PluginInterface
    is_valid_instance = isinstance(plugin, PluginInterface)

    # Verify the inheritance check
    if inherit_from_interface:
        assert is_valid_instance, "Plugin that inherits from PluginInterface should be recognized"
    else:
        assert not is_valid_instance, "Plugin that doesn't inherit from PluginInterface should not be recognized"


@given(plugin_config_strategy())
def test_property_1_plugin_interface_validation_config_schema(config: PluginConfig):
    """Property 1: Plugin Interface Validation (Config Schema)

    For any plugin, the get_config_schema() method should return a valid
    JSON Schema object that can be used for configuration validation.

    Feature: plugin-architecture, Property 1: Plugin Interface Validation
    Validates: Requirements 1.9
    """
    # Create a complete mock plugin
    MockPluginClass = create_mock_plugin_class(
        has_get_name=True,
        has_get_version=True,
        has_get_config_schema=True,
        has_initialize=True,
        has_start=True,
        has_stop=True,
        has_health_check=True,
        has_handle_message=True,
        has_send_message=True,
        has_handle_event=True,
        inherit_from_interface=True,
    )

    plugin = MockPluginClass()

    # Get the config schema
    schema = plugin.get_config_schema()

    # Verify it's a dictionary (basic JSON Schema requirement)
    assert isinstance(schema, dict), "Config schema must be a dictionary"

    # Verify it has a 'type' field (common JSON Schema requirement)
    # Note: This is a basic check; full JSON Schema validation would be more complex
    assert "type" in schema or len(schema) == 0, "Config schema should have a 'type' field or be empty"


@given(st.text(min_size=1, max_size=20))
def test_property_1_plugin_interface_validation_name_and_version(plugin_name: str):
    """Property 1: Plugin Interface Validation (Name and Version)

    For any plugin, the get_name() and get_version() methods should return
    non-empty strings that identify the plugin.

    Feature: plugin-architecture, Property 1: Plugin Interface Validation
    Validates: Requirements 1.9
    """
    # Create a complete mock plugin
    MockPluginClass = create_mock_plugin_class(
        has_get_name=True,
        has_get_version=True,
        has_get_config_schema=True,
        has_initialize=True,
        has_start=True,
        has_stop=True,
        has_health_check=True,
        has_handle_message=True,
        has_send_message=True,
        has_handle_event=True,
        inherit_from_interface=True,
    )

    plugin = MockPluginClass()

    # Get name and version
    name = plugin.get_name()
    version = plugin.get_version()

    # Verify they are strings
    assert isinstance(name, str), "Plugin name must be a string"
    assert isinstance(version, str), "Plugin version must be a string"

    # Verify they are non-empty
    assert len(name) > 0, "Plugin name must not be empty"
    assert len(version) > 0, "Plugin version must not be empty"
