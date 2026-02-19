# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Event Processor Worker for Docker/Local Environment

Polls SQS queue and processes events using the Lambda handler.
Simulates AWS Lambda + SQS integration locally.
"""

import os
import sys
import time
import json
import logging
import asyncio
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path
sys.path.insert(0, '/app')

from lambda.event_processor import process_sqs_batch

# Configure logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_sqs_client():
    """Create SQS client with LocalStack endpoint if configured."""
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
    
    return boto3.client(
        'sqs',
        endpoint_url=endpoint_url,
        region_name=os.environ.get('AWS_REGION', 'eu-south-2'),
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )


async def poll_and_process():
    """
    Poll SQS queue and process messages.
    
    Continuously polls the queue, processes messages in batches,
    and deletes successfully processed messages.
    """
    sqs = get_sqs_client()
    queue_url = os.environ.get('CORE_EVENT_QUEUE_URL')
    
    if not queue_url:
        logger.error("CORE_EVENT_QUEUE_URL not configured")
        return
    
    logger.info(f"Starting event processor worker, polling queue: {queue_url}")
    
    while True:
        try:
            # Receive messages from queue
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,  # Long polling
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if not messages:
                logger.debug("No messages received, continuing to poll...")
                continue
            
            logger.info(f"Received {len(messages)} messages from queue")
            
            # Convert to Lambda event format
            records = []
            for msg in messages:
                records.append({
                    'messageId': msg['MessageId'],
                    'receiptHandle': msg['ReceiptHandle'],
                    'body': msg['Body'],
                    'attributes': msg.get('Attributes', {}),
                    'messageAttributes': msg.get('MessageAttributes', {}),
                    'md5OfBody': msg.get('MD5OfBody', ''),
                    'eventSource': 'aws:sqs',
                    'eventSourceARN': f"arn:aws:sqs:eu-south-2:000000000000:triage-core-events",
                    'awsRegion': 'eu-south-2'
                })
            
            # Process batch
            results = await process_sqs_batch(records)
            
            # Delete successfully processed messages
            successful_count = 0
            failed_count = 0
            
            for i, msg in enumerate(messages):
                message_id = msg['MessageId']
                
                if message_id not in results['failed_message_ids']:
                    # Delete message from queue
                    try:
                        sqs.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=msg['ReceiptHandle']
                        )
                        successful_count += 1
                        logger.debug(f"Deleted message {message_id} from queue")
                    except ClientError as e:
                        logger.error(f"Failed to delete message {message_id}: {e}")
                        failed_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"Message {message_id} failed processing, will be retried")
            
            logger.info(
                f"Batch complete: {successful_count} successful, {failed_count} failed"
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'AWS.SimpleQueueService.NonExistentQueue':
                logger.error(f"Queue does not exist: {queue_url}")
                logger.info("Waiting 30 seconds before retry...")
                await asyncio.sleep(30)
            else:
                logger.error(f"SQS error: {e}", exc_info=True)
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"Unexpected error in polling loop: {e}", exc_info=True)
            await asyncio.sleep(5)


def main():
    """Main entry point."""
    logger.info("TrIAge Event Processor Worker starting...")
    logger.info(f"AWS Endpoint: {os.environ.get('AWS_ENDPOINT_URL', 'default')}")
    logger.info(f"AWS Region: {os.environ.get('AWS_REGION', 'eu-south-2')}")
    logger.info(f"Queue URL: {os.environ.get('CORE_EVENT_QUEUE_URL', 'not set')}")
    
    try:
        asyncio.run(poll_and_process())
    except KeyboardInterrupt:
        logger.info("Shutting down event processor worker...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
