# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Interface Definition

Defines the abstract base class and data models that all TrIAge channel plugins
must implement. This interface uses channel-agnostic abstractions to maximize
reusability across different communication platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class PluginMessage:
    """
    Channel-agnostic message representation.

    This data structure abstracts messages from any communication channel
    (Slack, WhatsApp, ChatGPT, etc.) into a common format.
    """

    channel_id: str  # Unique identifier for the channel (workspace_id, phone_number, etc.)
    user_id: str  # User identifier within the channel
    content: str  # Message text content
    command: Optional[str] = None  # Parsed command (e.g., "plan", "status")
    parameters: Dict[str, Any] = field(default_factory=dict)  # Command parameters
    metadata: Dict[str, Any] = field(default_factory=dict)  # Channel-specific metadata
    thread_id: Optional[str] = None  # For threaded conversations


@dataclass
class PluginResponse:
    """
    Channel-agnostic response representation.

    Plugins transform this abstract response into channel-specific formats
    (Slack Block Kit, WhatsApp templates, etc.).
    """

    content: str  # Response text (markdown supported)
    response_type: str = "message"  # message, ephemeral, modal, etc.
    attachments: List[Dict[str, Any]] = field(default_factory=list)  # Structured attachments
    actions: List[Dict[str, Any]] = field(default_factory=list)  # Interactive actions (buttons, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Channel-specific response data


class PluginStatus(Enum):
    """Plugin health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


@dataclass
class PluginConfig:
    """
    Plugin configuration schema.

    Contains plugin metadata and configuration parameters loaded from
    environment variables or config files.
    """

    plugin_name: str
    plugin_version: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)  # Plugin-specific configuration


class PluginInterface(ABC):
    """
    Abstract base class for all TrIAge channel plugins.

    All communication channel integrations (Slack, WhatsApp, ChatGPT, etc.)
    must implement this interface to interact with TrIAge Core.

    The interface is designed to be channel-agnostic, using abstract message
    types and responses that plugins adapt to their specific platform.
    """

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the plugin name (e.g., 'slack', 'whatsapp', 'chatgpt').

        Returns:
            str: Unique plugin identifier
        """
        pass

    @abstractmethod
    def get_version(self) -> str:
        """
        Return the plugin version (e.g., '1.0.0').

        Returns:
            str: Semantic version string
        """
        pass

    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for plugin configuration validation.

        The schema is used by the Plugin Registry to validate configuration
        before initializing the plugin.

        Returns:
            Dict[str, Any]: JSON Schema object
        """
        pass

    @abstractmethod
    async def initialize(self, config: PluginConfig, core_api: Any) -> None:
        """
        Initialize the plugin with configuration and core API access.

        This method is called once during plugin loading. Plugins should:
        - Store the configuration
        - Store the core API reference
        - Initialize any clients (Slack SDK, HTTP clients, etc.)
        - Validate credentials

        Args:
            config: Plugin configuration
            core_api: Reference to TrIAge Core Actions API

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        Start the plugin (register webhooks, open connections, etc.).

        Called after initialization to activate the plugin. Plugins should:
        - Register webhook endpoints
        - Open persistent connections if needed
        - Start background tasks

        Raises:
            Exception: If startup fails
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the plugin gracefully.

        Called during shutdown. Plugins should:
        - Close connections
        - Cancel background tasks
        - Clean up resources
        """
        pass

    @abstractmethod
    async def health_check(self) -> PluginStatus:
        """
        Check plugin health status.

        Called periodically by the Plugin Registry to monitor plugin health.
        Plugins should verify:
        - API connectivity
        - Authentication validity
        - Resource availability

        Returns:
            PluginStatus: Current health status
        """
        pass

    @abstractmethod
    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        """
        Handle incoming message from the channel.

        This is the main entry point for processing user interactions.
        Plugins should:
        - Parse the message and extract commands/parameters
        - Invoke appropriate Core Actions
        - Format the response for the channel

        Args:
            message: Channel-agnostic message

        Returns:
            PluginResponse: Response to send back to the channel

        Raises:
            Exception: If message handling fails
        """
        pass

    @abstractmethod
    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        """
        Send a message to the channel.

        Used for proactive notifications (plan generated, task blocked, etc.).
        Plugins should:
        - Convert PluginResponse to channel-specific format
        - Send via channel API
        - Handle rate limiting and retries

        Args:
            channel_id: Target channel identifier
            user_id: Target user identifier
            response: Message to send

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle events from TrIAge Core.

        Called when core events occur (plan generated, task blocked, etc.).
        Plugins should:
        - Check if they're subscribed to this event type
        - Extract relevant data
        - Send notifications to appropriate channels/users

        Args:
            event_type: Type of event (e.g., 'plan_generated', 'task_blocked')
            event_data: Event payload with context
        """
        pass
