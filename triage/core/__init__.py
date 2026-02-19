# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
TrIAge Core Module

Contains core business logic APIs and event infrastructure for plugin integration.
"""

from triage.core.actions_api import CoreActionResult, CoreActionsAPI
from triage.core.event_bus import Event, EventBus

__all__ = [
    "CoreActionsAPI",
    "CoreActionResult",
    "EventBus",
    "Event",
]
