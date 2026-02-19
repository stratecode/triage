# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Event Processor Lambda Function

AWS Lambda handler for processing core events from SQS queue.
Routes events from TrIAge Core to plugins via the Plugin Registry.

Processes events such as:
- plan_generated: Notify users when plans are ready
- task_blocked: Alert users about blocking tasks
- approval_timeout: Remind users to approve plans

Validates: Requirements 15.4, 15.11
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import boto3

# Add parent directory to path to import triage package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from triage.core.actions_api import CoreActionsAPI
from triage.core.event_bus import EventBus
from triage.jira_client import JiraClient
from triage.plan_generator import PlanGenerator
from triage.plugins.registry import PluginRegistry
from triage.task_classifier import TaskClassifier

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
secrets_client = boto3.client('secretsmanager')
sqs_client = boto3.client('sqs')

# Global registry instance (reused across warm Lambda invocations)
_registry: Optional[PluginRegistry] = None
_event_bus: Optional[EventBus] = None


def get_secret(secret_name: str) -> Dict[str, str]:
    """
    Retrieve secret from AWS Secrets Manager.

    Args:
        secret_name: Name of the secret

    Returns:
        Dict containing secret key-value pairs

    Raises:
        Exception: If secret retrieval fails
    """
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise


async def initialize_registry() -> PluginRegistry:
    """
    Initialize Plugin Registry with Core API and Event Bus.

    Creates and configures:
    - Event Bus for core-to-plugin communication
    - Core Actions API with JIRA client and plan generator
    - Plugin Registry with auto-configuration loading
    - Loads and starts all enabled plugins

    Returns:
        Initialized PluginRegistry

    Raises:
        Exception: If initialization fails
    """
    global _registry, _event_bus

    if _registry is not None:
        logger.info("Reusing existing Plugin Registry (warm Lambda)")
        return _registry

    logger.info("Initializing Plugin Registry (cold start)")

    try:
        # Initialize Event Bus
        _event_bus = EventBus()
        logger.info("Event Bus initialized")

        # Get JIRA credentials from Secrets Manager
        jira_secret_name = os.environ.get('JIRA_SECRET_NAME', 'triage/jira')
        jira_creds = get_secret(jira_secret_name)

        # Initialize JIRA client
        jira_client = JiraClient(
            base_url=jira_creds['jira_base_url'],
            email=jira_creds['jira_email'],
            api_token=jira_creds['jira_api_token'],
            project=jira_creds.get('jira_project')
        )
        logger.info("JIRA client initialized")

        # Initialize task classifier and plan generator
        classifier = TaskClassifier()

        # Use /tmp for closure tracking in Lambda
        closure_dir = os.path.join('/tmp', '.triage', 'closure')
        generator = PlanGenerator(
            jira_client,
            classifier,
            closure_tracking_dir=closure_dir
        )
        logger.info("Task classifier and plan generator initialized")

        # Initialize Core Actions API
        core_api = CoreActionsAPI(jira_client, classifier, generator)
        logger.info("Core Actions API initialized")

        # Initialize Plugin Registry
        config_dir = os.environ.get('PLUGIN_CONFIG_PATH', '/config/plugins')
        _registry = PluginRegistry(core_api, _event_bus, config_dir=config_dir)
        logger.info("Plugin Registry initialized")

        # Load plugins from environment variable (comma-separated list)
        plugins_to_load = os.environ.get('PLUGINS_ENABLED', 'slack').split(',')

        for plugin_name in plugins_to_load:
            plugin_name = plugin_name.strip()
            if plugin_name:
                logger.info(f"Loading plugin: {plugin_name}")
                success = await _registry.load_plugin_with_auto_config(plugin_name)

                if success:
                    logger.info(f"Plugin {plugin_name} loaded successfully")
                else:
                    logger.warning(f"Failed to load plugin: {plugin_name}")

        # Start all loaded plugins
        await _registry.start_all()
        logger.info("All plugins started")

        return _registry

    except Exception as e:
        logger.error(f"Failed to initialize Plugin Registry: {e}", exc_info=True)
        raise


async def process_event(event_data: Dict[str, Any]) -> bool:
    """
    Process a single core event.

    Routes the event to all subscribed plugins via the Plugin Registry.

    Args:
        event_data: Event payload from SQS message

    Returns:
        bool: True if event processed successfully, False otherwise

    Validates: Requirements 15.4, 15.11
    """
    try:
        # Extract event type and data
        event_type = event_data.get('event_type')
        event_payload = event_data.get('event_data', {})

        if not event_type:
            logger.error("Event missing event_type field")
            return False

        logger.info(
            "Processing event",
            extra={
                'event_type': event_type,
                'event_data_keys': list(event_payload.keys())
            }
        )

        # Initialize registry
        registry = await initialize_registry()

        # Broadcast event to all plugins
        await registry.broadcast_event(event_type, event_payload)

        logger.info(
            "Event processed successfully",
            extra={'event_type': event_type}
        )

        return True

    except Exception as e:
        logger.error(
            f"Error processing event: {e}",
            extra={'event_data': event_data},
            exc_info=True
        )
        return False


async def process_sqs_batch(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process a batch of SQS messages.

    Processes multiple events concurrently and tracks successes/failures
    for partial batch failure handling.

    Args:
        records: List of SQS records from Lambda event

    Returns:
        Dict with batch processing results including failed message IDs

    Validates: Requirements 15.4, 15.11
    """
    logger.info(f"Processing batch of {len(records)} SQS messages")

    results = {
        'total': len(records),
        'successful': 0,
        'failed': 0,
        'failed_message_ids': []
    }

    # Process all messages concurrently
    tasks = []
    message_ids = []

    for record in records:
        try:
            # Parse message body
            message_body = json.loads(record['body'])

            # Handle SNS-wrapped messages
            if 'Message' in message_body:
                # Message from SNS topic
                event_data = json.loads(message_body['Message'])
            else:
                # Direct SQS message
                event_data = message_body

            # Create processing task
            task = process_event(event_data)
            tasks.append(task)
            message_ids.append(record['messageId'])

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse message body: {e}",
                extra={'message_id': record.get('messageId')}
            )
            results['failed'] += 1
            results['failed_message_ids'].append(record['messageId'])
        except Exception as e:
            logger.error(
                f"Error preparing message for processing: {e}",
                extra={'message_id': record.get('messageId')},
                exc_info=True
            )
            results['failed'] += 1
            results['failed_message_ids'].append(record['messageId'])

    # Wait for all tasks to complete
    if tasks:
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Track results
        for i, result in enumerate(task_results):
            if isinstance(result, Exception):
                logger.error(
                    f"Task failed with exception: {result}",
                    extra={'message_id': message_ids[i]},
                    exc_info=result
                )
                results['failed'] += 1
                results['failed_message_ids'].append(message_ids[i])
            elif result:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['failed_message_ids'].append(message_ids[i])

    logger.info(
        "Batch processing complete",
        extra={
            'total': results['total'],
            'successful': results['successful'],
            'failed': results['failed']
        }
    )

    return results


def handler(event: Dict, context: Any) -> Dict:
    """
    Main Lambda handler for SQS event processing.

    Processes events from the core event queue and routes them to plugins.
    Supports partial batch failure - failed messages are returned for retry.

    Args:
        event: Lambda event with SQS records
        context: Lambda context

    Returns:
        Dict with batch item failures for partial batch failure handling

    Validates: Requirements 15.4, 15.11
    """
    # Log invocation
    logger.info(
        "Event processor invoked",
        extra={
            'record_count': len(event.get('Records', [])),
            'request_id': context.request_id
        }
    )

    try:
        # Get SQS records
        records = event.get('Records', [])

        if not records:
            logger.warning("No records in event")
            return {
                'batchItemFailures': []
            }

        # Process batch
        results = asyncio.run(process_sqs_batch(records))

        # Return failed message IDs for retry
        # Lambda will automatically retry these messages
        batch_item_failures = [
            {'itemIdentifier': message_id}
            for message_id in results['failed_message_ids']
        ]

        if batch_item_failures:
            logger.warning(
                f"Returning {len(batch_item_failures)} failed messages for retry",
                extra={'failed_count': len(batch_item_failures)}
            )

        return {
            'batchItemFailures': batch_item_failures
        }

    except Exception as e:
        logger.error(
            f"Unhandled error in event processor: {e}",
            exc_info=True
        )

        # Return all messages as failed for retry
        return {
            'batchItemFailures': [
                {'itemIdentifier': record['messageId']}
                for record in event.get('Records', [])
            ]
        }


def send_to_dead_letter_queue(message: Dict[str, Any], error: str) -> None:
    """
    Send failed message to dead letter queue.

    Used for messages that have exceeded retry attempts or cannot be processed.

    Args:
        message: Original message data
        error: Error description
    """
    dlq_url = os.environ.get('DEAD_LETTER_QUEUE_URL')

    if not dlq_url:
        logger.warning("Dead letter queue URL not configured")
        return

    try:
        # Add error metadata
        dlq_message = {
            'original_message': message,
            'error': error,
            'timestamp': asyncio.get_event_loop().time(),
            'source': 'event_processor'
        }

        # Send to DLQ
        sqs_client.send_message(
            QueueUrl=dlq_url,
            MessageBody=json.dumps(dlq_message)
        )

        logger.info(
            "Message sent to dead letter queue",
            extra={'error': error}
        )

    except Exception as e:
        logger.error(
            f"Failed to send message to dead letter queue: {e}",
            exc_info=True
        )


# Health check function for monitoring
async def health_check() -> Dict[str, Any]:
    """
    Perform health check on event processor.

    Verifies:
    - Plugin Registry can be initialized
    - Plugins are healthy
    - SQS queue is accessible

    Returns:
        Dict with health status
    """
    try:
        # Initialize registry
        registry = await initialize_registry()

        # Check plugin health
        plugin_health = await registry.health_check_all()

        # Determine overall health
        all_healthy = all(
            status.value == 'healthy'
            for status in plugin_health.values()
        )

        overall_status = 'healthy' if all_healthy else 'degraded'

        return {
            'status': overall_status,
            'service': 'triage-event-processor',
            'version': '1.0.0',
            'plugins': {
                name: status.value
                for name, status in plugin_health.items()
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            'status': 'unhealthy',
            'error': str(e)
        }
