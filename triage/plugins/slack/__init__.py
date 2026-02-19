# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Slack Plugin Package

Slack connector plugin for TrIAge, implementing OAuth authorization,
workspace installation, and command mapping.
"""

from .oauth_handler import OAuthError, OAuthTokens, SlackOAuthHandler

__all__ = ["SlackOAuthHandler", "OAuthTokens", "OAuthError"]
