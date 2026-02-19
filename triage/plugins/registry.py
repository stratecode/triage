# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Registry

Manages plugin lifecycle, routing, and health monitoring. The registry is
responsible for discovering, loading, initializing, and coordinating all
channel plugins.
"""

import importlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from triage.plugins.config_loader import ConfigLoader, ConfigurationError
from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)


class PluginRegistry:
    """
    Manages plugin lifecycle and routing.

    The registry provides:
    - Plugin discovery and loading
    - Plugin lifecycle management (start, stop, health checks)
    - Message routing to appropriate plugins
    - Event broadcasting to subscribed plugins
    - Error isolation and recovery
    """

    def __init__(self, core_api: Any, event_bus: Optional[Any] = None, config_dir: Optional[str] = None):
        """
        Initialize the plugin registry.

        Args:
            core_api: Reference to TrIAge Core Actions API
            event_bus: Optional event bus for core-to-plugin communication
            config_dir: Optional directory containing plugin config files
        """
        self.core_api = core_api
        self.event_bus = event_bus
        self.plugins: Dict[str, PluginInterface] = {}
        self.plugin_health: Dict[str, PluginStatus] = {}
        self.config_loader = ConfigLoader(config_dir)
        self.logger = logging.getLogger(__name__)

    async def discover_plugins(self, plugins_dir: str) -> List[str]:
        """
        Discover plugins from directory.

        Scans the plugins directory for Python modules that contain plugin
        implementations. A valid plugin module must contain a class that
        implements PluginInterface.

        Args:
            plugins_dir: Path to plugins directory

        Returns:
            List[str]: List of discovered plugin names
        """
        discovered = []
        plugins_path = Path(plugins_dir)

        if not plugins_path.exists():
            self.logger.warning(f"Plugins directory not found: {plugins_dir}")
            return discovered

        # Scan for subdirectories (each subdirectory is a potential plugin)
        for item in plugins_path.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                # Check if it contains a plugin module
                plugin_file = item / f"{item.name}_plugin.py"
                if plugin_file.exists():
                    discovered.append(item.name)
                    self.logger.info(f"Discovered plugin: {item.name}")

        return discovered

    async def load_plugin(self, plugin_name: str, config: PluginConfig) -> bool:
        """
        Load and initialize a plugin.

        Dynamically imports the plugin module, instantiates the plugin class,
        validates interface implementation, and initializes the plugin.

        Args:
            plugin_name: Name of the plugin to load
            config: Plugin configuration

        Returns:
            bool: True if plugin loaded successfully, False otherwise
        """
        try:
            # Dynamically import plugin module
            module_path = f"triage.plugins.{plugin_name}.{plugin_name}_plugin"
            self.logger.info(f"Loading plugin from: {module_path}")

            module = importlib.import_module(module_path)

            # Get plugin class (convention: {PluginName}Plugin)
            class_name = f"{plugin_name.capitalize()}Plugin"
            plugin_class = getattr(module, class_name)

            # Instantiate plugin
            plugin = plugin_class()

            # Validate interface implementation
            if not isinstance(plugin, PluginInterface):
                raise TypeError(f"Plugin {plugin_name} does not implement PluginInterface")

            # Initialize plugin with config and core API
            await plugin.initialize(config, self.core_api)

            # Store plugin and mark as healthy
            self.plugins[plugin_name] = plugin
            self.plugin_health[plugin_name] = PluginStatus.HEALTHY

            self.logger.info(f"Loaded plugin: {plugin_name} v{plugin.get_version()}")
            return True

        except ImportError as e:
            self.logger.error(f"Failed to import plugin {plugin_name}: {e}", exc_info=True)
            return False
        except AttributeError as e:
            self.logger.error(f"Plugin {plugin_name} missing required class or method: {e}", exc_info=True)
            return False
        except ConfigurationError as e:
            self.logger.error(f"Configuration error for plugin {plugin_name}: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}", exc_info=True)
            return False

    async def load_plugin_with_auto_config(self, plugin_name: str) -> bool:
        """
        Load a plugin with automatic configuration loading.

        This method automatically loads configuration from environment variables
        and config files, validates it against the plugin's schema, and applies
        default values.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            bool: True if plugin loaded successfully, False otherwise
        """
        try:
            # First, import the plugin to get its schema and version
            module_path = f"triage.plugins.{plugin_name}.{plugin_name}_plugin"
            module = importlib.import_module(module_path)

            class_name = f"{plugin_name.capitalize()}Plugin"
            plugin_class = getattr(module, class_name)

            # Create temporary instance to get schema and version
            temp_plugin = plugin_class()
            schema = temp_plugin.get_config_schema()
            version = temp_plugin.get_version()

            # Load configuration using ConfigLoader
            config = self.config_loader.load_plugin_config(
                plugin_name=plugin_name, plugin_version=version, config_schema=schema
            )

            # Check if plugin is enabled
            if not config.enabled:
                self.logger.info(f"Plugin {plugin_name} is disabled, skipping load")
                return False

            # Load the plugin with the configuration
            return await self.load_plugin(plugin_name, config)

        except ImportError as e:
            self.logger.error(f"Failed to import plugin {plugin_name}: {e}", exc_info=True)
            return False
        except ConfigurationError as e:
            self.logger.error(f"Configuration error for plugin {plugin_name}: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name} with auto-config: {e}", exc_info=True)
            return False

    async def start_all(self) -> None:
        """
        Start all loaded plugins.

        Calls the start() method on each plugin. If a plugin fails to start,
        it is marked as unhealthy but other plugins continue starting.
        """
        for name, plugin in self.plugins.items():
            try:
                await plugin.start()
                self.logger.info(f"Started plugin: {name}")
            except Exception as e:
                self.logger.error(f"Failed to start plugin {name}: {e}", exc_info=True)
                self.plugin_health[name] = PluginStatus.UNHEALTHY

    async def stop_all(self) -> None:
        """
        Stop all loaded plugins gracefully.

        Calls the stop() method on each plugin to clean up resources.
        """
        for name, plugin in self.plugins.items():
            try:
                await plugin.stop()
                self.plugin_health[name] = PluginStatus.STOPPED
                self.logger.info(f"Stopped plugin: {name}")
            except Exception as e:
                self.logger.error(f"Error stopping plugin {name}: {e}", exc_info=True)

    async def route_message(self, channel_type: str, message: PluginMessage) -> PluginResponse:
        """
        Route incoming message to appropriate plugin.

        Dispatches the message to the plugin corresponding to the channel type.
        Handles plugin errors gracefully by returning error responses.

        Args:
            channel_type: Type of channel (e.g., 'slack', 'whatsapp')
            message: Channel-agnostic message

        Returns:
            PluginResponse: Response from the plugin or error response
        """
        plugin = self.plugins.get(channel_type)

        if not plugin:
            self.logger.warning(f"Unknown channel type: {channel_type}")
            return PluginResponse(content=f"Unknown channel type: {channel_type}", response_type="error")

        # Check plugin health before routing
        if self.plugin_health.get(channel_type) != PluginStatus.HEALTHY:
            self.logger.warning(
                f"Plugin {channel_type} is not healthy, status: " f"{self.plugin_health.get(channel_type)}"
            )
            return PluginResponse(content="Service temporarily unavailable", response_type="error")

        # Route message to plugin with error isolation
        try:
            response = await plugin.handle_message(message)
            return response
        except Exception as e:
            self.logger.error(f"Plugin {channel_type} error: {e}", exc_info=True)
            # Mark plugin as degraded
            self.plugin_health[channel_type] = PluginStatus.DEGRADED

            # Return generic error response (don't expose internal details)
            return PluginResponse(content="An error occurred processing your request", response_type="error")

    async def broadcast_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Broadcast core event to all subscribed plugins.

        Sends events from TrIAge Core (plan generated, task blocked, etc.)
        to all loaded plugins. Plugin errors are isolated and logged.

        Args:
            event_type: Type of event (e.g., 'plan_generated')
            event_data: Event payload
        """
        self.logger.info(f"Broadcasting event: {event_type}")

        for name, plugin in self.plugins.items():
            try:
                await plugin.handle_event(event_type, event_data)
            except Exception as e:
                self.logger.error(f"Plugin {name} failed to handle event {event_type}: {e}", exc_info=True)
                # Don't mark as unhealthy for event handling failures
                # (plugin may not subscribe to this event type)

    async def health_check_all(self) -> Dict[str, PluginStatus]:
        """
        Check health of all plugins.

        Calls health_check() on each plugin and updates the health status.
        Failed health checks mark the plugin as unhealthy.

        Returns:
            Dict[str, PluginStatus]: Health status for each plugin
        """
        for name, plugin in self.plugins.items():
            try:
                status = await plugin.health_check()
                self.plugin_health[name] = status

                if status != PluginStatus.HEALTHY:
                    self.logger.warning(f"Plugin {name} health check returned: {status.value}")
            except Exception as e:
                self.logger.error(f"Health check failed for {name}: {e}", exc_info=True)
                self.plugin_health[name] = PluginStatus.UNHEALTHY

        return self.plugin_health.copy()

    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """
        Get a loaded plugin by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Optional[PluginInterface]: Plugin instance or None if not found
        """
        return self.plugins.get(plugin_name)

    def get_all_plugins(self) -> Dict[str, PluginInterface]:
        """
        Get all loaded plugins.

        Returns:
            Dict[str, PluginInterface]: Dictionary of plugin name to plugin instance
        """
        return self.plugins.copy()

    def get_plugin_health(self, plugin_name: str) -> Optional[PluginStatus]:
        """
        Get health status of a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Optional[PluginStatus]: Health status or None if plugin not found
        """
        return self.plugin_health.get(plugin_name)
