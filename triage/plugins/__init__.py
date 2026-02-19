# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
TrIAge Plugin System

This package provides the plugin infrastructure for integrating communication
channels (Slack, WhatsApp, ChatGPT, etc.) with TrIAge Core.
"""

from triage.plugins.encryption import TokenEncryption
from triage.plugins.installation_storage import PluginInstallationStorage
from triage.plugins.interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from triage.plugins.models import PluginInstallation
from triage.plugins.registry import PluginRegistry

__all__ = [
    "PluginInterface",
    "PluginMessage",
    "PluginResponse",
    "PluginConfig",
    "PluginStatus",
    "PluginRegistry",
    "PluginInstallation",
    "TokenEncryption",
    "PluginInstallationStorage",
]
