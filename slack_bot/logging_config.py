# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Structured logging configuration for Slack bot service.

Provides JSON-formatted logging with context and security features.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import re


class SensitiveDataFilter(logging.Filter):
    """
    Filter to redact sensitive data from log records.
    
    Ensures JIRA credentials, OAuth tokens, API keys, and other sensitive
    data never appear in logs or messages.
    
    Validates: Requirements 12.3
    """
    
    # Patterns for sensitive data
    PATTERNS = [
        # Slack tokens
        (re.compile(r'(xoxb-[a-zA-Z0-9-]+)'), 'REDACTED_BOT_TOKEN'),
        (re.compile(r'(xoxp-[a-zA-Z0-9-]+)'), 'REDACTED_USER_TOKEN'),
        (re.compile(r'(xoxa-[a-zA-Z0-9-]+)'), 'REDACTED_ACCESS_TOKEN'),
        (re.compile(r'(xoxr-[a-zA-Z0-9-]+)'), 'REDACTED_REFRESH_TOKEN'),
        
        # Bearer tokens
        (re.compile(r'(Bearer\s+[a-zA-Z0-9._-]+)'), 'Bearer REDACTED_TOKEN'),
        (re.compile(r'(Authorization:\s*Bearer\s+)[a-zA-Z0-9._-]+', re.IGNORECASE), r'\1REDACTED_TOKEN'),
        
        # JSON field patterns
        (re.compile(r'("password"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("api_token"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("api_key"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("secret"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("access_token"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("refresh_token"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("client_secret"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("signing_secret"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("encryption_key"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        
        # JIRA credentials
        (re.compile(r'("jira_token"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("jira_password"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        (re.compile(r'("jira_api_token"\s*:\s*")[^"]*(")', re.IGNORECASE), r'\1REDACTED\2'),
        
        # Basic auth patterns
        (re.compile(r'(Basic\s+[a-zA-Z0-9+/=]+)'), 'Basic REDACTED_CREDENTIALS'),
        
        # Email:password patterns (common in JIRA auth)
        (re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]+'), r'\1:REDACTED_PASSWORD'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log message."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        
        # Also redact from args if present
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, dict):
                record.args = self._redact_dict(record.args)
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    self._redact_value(arg) for arg in record.args
                )
        
        return True
    
    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redact sensitive keys in dictionary.
        
        Ensures JIRA credentials and other sensitive data are never logged.
        
        Validates: Requirements 12.3
        """
        sensitive_keys = {
            'password', 'token', 'secret', 'api_key', 'api_token',
            'access_token', 'refresh_token', 'authorization',
            'client_secret', 'signing_secret', 'encryption_key',
            'jira_token', 'jira_password', 'jira_api_token',
            'bearer', 'credentials', 'auth'
        }
        
        result = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                result[key] = 'REDACTED'
            elif isinstance(value, dict):
                result[key] = self._redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self._redact_dict(item) if isinstance(item, dict) else self._redact_value(item)
                    for item in value
                ]
            elif isinstance(value, str):
                result[key] = self._redact_value(value)
            else:
                result[key] = value
        
        return result
    
    def _redact_value(self, value: Any) -> Any:
        """Redact sensitive patterns from string values."""
        if not isinstance(value, str):
            return value
        
        for pattern, replacement in self.PATTERNS:
            value = pattern.sub(replacement, value)
        
        return value


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    # Reserved LogRecord attributes that should not be included as extra fields
    RESERVED_ATTRS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
        'levelno', 'lineno', 'module', 'msecs', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
        'exc_text', 'stack_info', 'getMessage', 'message', 'asctime', 'taskName'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            log_data['exception_type'] = record.exc_info[0].__name__ if record.exc_info[0] else None
        
        # Add stack trace for errors
        if record.levelno >= logging.ERROR and record.exc_info:
            log_data['stack_trace'] = self.formatException(record.exc_info)
        
        # Add all extra fields dynamically
        # This includes any fields added via extra={} parameter
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith('_'):
                # Skip if already added
                if key not in log_data:
                    log_data[key] = value
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('json' or 'text')
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Set formatter
    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    
    # Add sensitive data filter
    console_handler.addFilter(SensitiveDataFilter())
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Set third-party library log levels
    logging.getLogger('slack_sdk').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)



class LogContext:
    """
    Context manager for adding structured context to log records.
    
    Usage:
        with LogContext(user_id="U123", team_id="T456"):
            logger.info("Processing request")
    
    Validates: Requirements 11.5
    """
    
    def __init__(self, **context):
        """
        Initialize log context.
        
        Args:
            **context: Key-value pairs to add to log records
        """
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        """Enter context manager."""
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def log_error_with_context(
    logger: logging.Logger,
    message: str,
    error: Exception,
    **context
) -> None:
    """
    Log an error with full context and stack trace.
    
    Args:
        logger: Logger instance
        message: Error message
        error: Exception that occurred
        **context: Additional context fields
        
    Validates: Requirements 11.5
    """
    extra = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        **context
    }
    
    # Add specific error attributes if available
    if hasattr(error, 'status_code'):
        extra['status_code'] = error.status_code
    if hasattr(error, 'response_body'):
        extra['response_body'] = str(error.response_body)[:500]  # Truncate
    if hasattr(error, 'attempts'):
        extra['retry_attempts'] = error.attempts
    
    logger.error(
        message,
        extra=extra,
        exc_info=True
    )


def log_api_call(
    logger: logging.Logger,
    api_name: str,
    method: str,
    endpoint: str,
    duration_ms: float,
    status_code: Optional[int] = None,
    success: bool = True,
    **context
) -> None:
    """
    Log an API call with timing and status information.
    
    Args:
        logger: Logger instance
        api_name: Name of the API (e.g., "TrIAge", "Slack")
        method: HTTP method
        endpoint: API endpoint
        duration_ms: Request duration in milliseconds
        status_code: HTTP status code
        success: Whether the call succeeded
        **context: Additional context fields
        
    Validates: Requirements 11.5
    """
    extra = {
        'api_name': api_name,
        'method': method,
        'endpoint': endpoint,
        'duration_ms': duration_ms,
        'success': success,
        **context
    }
    
    if status_code is not None:
        extra['status_code'] = status_code
    
    level = logging.INFO if success else logging.ERROR
    message = f"{api_name} API call: {method} {endpoint} - {'success' if success else 'failed'}"
    
    logger.log(level, message, extra=extra)
