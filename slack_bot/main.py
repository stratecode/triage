# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Main entry point for Slack bot service.

Initializes the application and starts the server.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

try:
    from slack_bot.config import SlackBotConfig
    from slack_bot.logging_config import setup_logging, get_logger
except ModuleNotFoundError:
    # Allow running from the package folder with `python -m main`.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import SlackBotConfig
    from logging_config import setup_logging, get_logger


logger = get_logger(__name__)


async def main() -> None:
    """Main application entry point."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)

    # Load configuration
    try:
        config = SlackBotConfig.from_env()
        config.validate()
    except KeyError as e:
        logger.error(f"Missing required environment variable: {e}")
        raise
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        raise
    
    # Setup logging
    setup_logging(log_level=config.log_level, log_format=config.log_format)
    
    logger.info("Starting Slack bot service", extra={
        'triage_api_url': config.triage_api_url,
        'redis_url': config.redis_url,
    })
    
    # TODO: Initialize Slack app and handlers
    # TODO: Start webhook server
    
    logger.info("Slack bot service started successfully")


if __name__ == "__main__":
    asyncio.run(main())
