# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Data Models

Defines data models for plugin installations, OAuth tokens, and other
plugin-related persistent data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class PluginInstallation:
    """
    Represents a plugin installation (e.g., Slack workspace).

    This model stores the installation data for a plugin in a specific
    channel/workspace. For example, a Slack workspace installation would
    store the workspace ID, OAuth tokens, and metadata.
    """

    id: Optional[int] = None
    plugin_name: str = ""  # 'slack', 'whatsapp', etc.
    channel_id: str = ""  # workspace_id, phone_number, etc.
    access_token: str = ""  # Encrypted
    refresh_token: Optional[str] = None  # Encrypted
    metadata: Dict[str, Any] = field(default_factory=dict)  # Plugin-specific data
    installed_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for database storage.

        Returns:
            Dict[str, Any]: Dictionary representation
        """
        return {
            "id": self.id,
            "plugin_name": self.plugin_name,
            "channel_id": self.channel_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "metadata": self.metadata,
            "installed_at": self.installed_at,
            "last_active": self.last_active,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginInstallation":
        """
        Create instance from dictionary.

        Args:
            data: Dictionary with installation data

        Returns:
            PluginInstallation: New instance
        """
        return cls(
            id=data.get("id"),
            plugin_name=data.get("plugin_name", ""),
            channel_id=data.get("channel_id", ""),
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            metadata=data.get("metadata", {}),
            installed_at=data.get("installed_at"),
            last_active=data.get("last_active"),
            is_active=data.get("is_active", True),
        )
