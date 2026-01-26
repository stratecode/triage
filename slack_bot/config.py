# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Configuration management for Slack bot service.

Handles environment variables and application settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SlackBotConfig:
    """Configuration for Slack bot service."""
    
    # Slack API credentials (required)
    slack_bot_token: str
    slack_signing_secret: str
    slack_client_id: str
    slack_client_secret: str
    
    # TrIAge API configuration (required)
    triage_api_url: str
    triage_api_token: str
    
    # Redis configuration (required)
    redis_url: str
    
    # Database configuration (required)
    database_url: str
    
    # Encryption configuration (required)
    encryption_key: str
    
    # Redis configuration (optional)
    redis_ttl_seconds: int = 300  # 5 minutes
    
    # Logging configuration (optional)
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Webhook configuration (optional)
    webhook_timeout_seconds: int = 3
    
    # Retry configuration (optional)
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    
    @classmethod
    def from_env(cls) -> "SlackBotConfig":
        """Load configuration from environment variables."""
        return cls(
            slack_bot_token=os.environ["SLACK_BOT_TOKEN"],
            slack_signing_secret=os.environ["SLACK_SIGNING_SECRET"],
            slack_client_id=os.environ["SLACK_CLIENT_ID"],
            slack_client_secret=os.environ["SLACK_CLIENT_SECRET"],
            triage_api_url=os.environ["TRIAGE_API_URL"],
            triage_api_token=os.environ["TRIAGE_API_TOKEN"],
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
            redis_ttl_seconds=int(os.environ.get("REDIS_TTL_SECONDS", "300")),
            database_url=os.environ["DATABASE_URL"],
            encryption_key=os.environ["ENCRYPTION_KEY"],
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            log_format=os.environ.get("LOG_FORMAT", "json"),
            webhook_timeout_seconds=int(os.environ.get("WEBHOOK_TIMEOUT_SECONDS", "3")),
            max_retries=int(os.environ.get("MAX_RETRIES", "3")),
            retry_backoff_base=float(os.environ.get("RETRY_BACKOFF_BASE", "2.0")),
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if not self.slack_bot_token.startswith("xoxb-"):
            raise ValueError("SLACK_BOT_TOKEN must start with 'xoxb-'")
        
        if not self.triage_api_url.startswith("https://"):
            raise ValueError("TRIAGE_API_URL must use HTTPS")
        
        if self.webhook_timeout_seconds < 1 or self.webhook_timeout_seconds > 10:
            raise ValueError("WEBHOOK_TIMEOUT_SECONDS must be between 1 and 10")
        
        if self.max_retries < 0 or self.max_retries > 10:
            raise ValueError("MAX_RETRIES must be between 0 and 10")
        
        if len(self.encryption_key) < 32:
            raise ValueError("ENCRYPTION_KEY must be at least 32 characters")
