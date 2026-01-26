# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Async event processor for Slack webhook events.

This module handles background processing of webhook events after immediate
acknowledgment, implementing a task queue for long-running operations.

Validates: Requirements 7.1, 7.2
"""

import asyncio
from typing import Optional, Callable, Awaitable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from slack_bot.models import WebhookEvent
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    """Result of event processing."""
    success: bool
    event_id: str
    processing_time_ms: int
    error: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


class EventQueue:
    """
    Async task queue for webhook event processing.
    
    Provides immediate acknowledgment to Slack while processing events
    in the background without blocking the webhook response.
    
    Validates: Requirements 7.1, 7.2
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize event queue.
        
        Args:
            max_workers: Maximum number of concurrent event processors
        """
        self.max_workers = max_workers
        self.queue: asyncio.Queue[WebhookEvent] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.handlers: Dict[str, Callable[[WebhookEvent], Awaitable[ProcessingResult]]] = {}
        self.running = False
        
        logger.info("Event queue initialized", extra={
            'max_workers': max_workers
        })
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[WebhookEvent], Awaitable[ProcessingResult]]
    ) -> None:
        """
        Register a handler for a specific event type.
        
        Args:
            event_type: Type of event to handle (e.g., 'slash_command', 'block_action')
            handler: Async function to process the event
        """
        self.handlers[event_type] = handler
        logger.info("Event handler registered", extra={
            'event_type': event_type,
            'handler': handler.__name__
        })
    
    async def enqueue(self, event: WebhookEvent) -> None:
        """
        Add event to processing queue.
        
        This method returns immediately, allowing the webhook to respond
        within the 3-second timeout while processing happens in background.
        
        Args:
            event: WebhookEvent to process
            
        Validates: Requirements 7.1, 7.2
        """
        await self.queue.put(event)
        logger.debug("Event enqueued", extra={
            'event_id': event.event_id,
            'event_type': event.event_type,
            'queue_size': self.queue.qsize()
        })
    
    async def start(self) -> None:
        """
        Start background workers to process queued events.
        
        Creates worker tasks that continuously process events from the queue.
        """
        if self.running:
            logger.warning("Event queue already running")
            return
        
        self.running = True
        
        # Create worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
        
        logger.info("Event queue started", extra={
            'num_workers': len(self.workers)
        })
    
    async def stop(self) -> None:
        """
        Stop background workers and wait for pending events to complete.
        """
        if not self.running:
            return
        
        self.running = False
        
        # Wait for queue to empty
        await self.queue.join()
        
        # Cancel workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers.clear()
        
        logger.info("Event queue stopped")
    
    async def _worker(self, worker_id: int) -> None:
        """
        Background worker that processes events from the queue.
        
        Args:
            worker_id: Unique identifier for this worker
        """
        logger.info("Worker started", extra={'worker_id': worker_id})
        
        while self.running:
            try:
                # Get event from queue with timeout
                event = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )
                
                # Process event
                await self._process_event(event, worker_id)
                
                # Mark task as done
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                # No events in queue, continue waiting
                continue
            except asyncio.CancelledError:
                # Worker cancelled, exit gracefully
                logger.info("Worker cancelled", extra={'worker_id': worker_id})
                break
            except Exception as e:
                logger.error("Worker error", extra={
                    'worker_id': worker_id,
                    'error': str(e)
                })
        
        logger.info("Worker stopped", extra={'worker_id': worker_id})
    
    async def _process_event(self, event: WebhookEvent, worker_id: int) -> None:
        """
        Process a single event using registered handler.
        
        Args:
            event: WebhookEvent to process
            worker_id: ID of worker processing the event
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Find handler for event type
            handler = self.handlers.get(event.event_type)
            
            if handler is None:
                logger.warning("No handler for event type", extra={
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'worker_id': worker_id
                })
                return
            
            # Process event
            result = await handler(event)
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            if result.success:
                logger.info("Event processed successfully", extra={
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'worker_id': worker_id,
                    'processing_time_ms': int(processing_time)
                })
            else:
                logger.error("Event processing failed", extra={
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'worker_id': worker_id,
                    'error': result.error,
                    'processing_time_ms': int(processing_time)
                })
        
        except Exception as e:
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.error("Event processing exception", extra={
                'event_id': event.event_id,
                'event_type': event.event_type,
                'worker_id': worker_id,
                'error': str(e),
                'processing_time_ms': int(processing_time)
            })


class AsyncEventProcessor:
    """
    High-level async event processor with queue management.
    
    Provides a simple interface for processing webhook events asynchronously
    with immediate acknowledgment and background processing.
    
    Validates: Requirements 7.1, 7.2
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Initialize async event processor.
        
        Args:
            max_workers: Maximum number of concurrent event processors
        """
        self.queue = EventQueue(max_workers=max_workers)
        logger.info("Async event processor initialized")
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[WebhookEvent], Awaitable[ProcessingResult]]
    ) -> None:
        """
        Register a handler for a specific event type.
        
        Args:
            event_type: Type of event to handle
            handler: Async function to process the event
        """
        self.queue.register_handler(event_type, handler)
    
    async def process_async(self, event: WebhookEvent) -> None:
        """
        Process event asynchronously in background.
        
        This method returns immediately after enqueuing the event,
        allowing the webhook to respond within 3 seconds.
        
        Args:
            event: WebhookEvent to process
            
        Validates: Requirements 7.1, 7.2
        """
        await self.queue.enqueue(event)
    
    async def start(self) -> None:
        """Start background event processing."""
        await self.queue.start()
    
    async def stop(self) -> None:
        """Stop background event processing."""
        await self.queue.stop()


# Example handler for demonstration
async def example_slash_command_handler(event: WebhookEvent) -> ProcessingResult:
    """
    Example handler for slash command events.
    
    This is a placeholder that will be replaced with actual command
    handling logic in future tasks.
    
    Args:
        event: WebhookEvent to process
        
    Returns:
        ProcessingResult with success status
    """
    logger.info("Processing slash command", extra={
        'event_id': event.event_id,
        'user_id': event.user_id
    })
    
    # Simulate processing
    await asyncio.sleep(0.1)
    
    return ProcessingResult(
        success=True,
        event_id=event.event_id,
        processing_time_ms=100
    )


# Example handler for block actions
async def example_block_action_handler(event: WebhookEvent) -> ProcessingResult:
    """
    Example handler for block action events (button clicks).
    
    This is a placeholder that will be replaced with actual interaction
    handling logic in future tasks.
    
    Args:
        event: WebhookEvent to process
        
    Returns:
        ProcessingResult with success status
    """
    logger.info("Processing block action", extra={
        'event_id': event.event_id,
        'user_id': event.user_id
    })
    
    # Simulate processing
    await asyncio.sleep(0.1)
    
    return ProcessingResult(
        success=True,
        event_id=event.event_id,
        processing_time_ms=100
    )


async def create_uninstall_handler(oauth_manager) -> Callable[[WebhookEvent], Awaitable[ProcessingResult]]:
    """
    Create an uninstall event handler with OAuth manager dependency.
    
    Args:
        oauth_manager: OAuthManager instance for token revocation
        
    Returns:
        Async handler function for app_uninstalled events
        
    Validates: Requirements 12.5
    """
    async def handle_app_uninstall(event: WebhookEvent) -> ProcessingResult:
        """
        Handle app_uninstalled event from Slack.
        
        When a workspace uninstalls the bot, this handler:
        1. Revokes the OAuth token
        2. Deletes all tokens from storage
        3. Triggers user data deletion
        
        Args:
            event: WebhookEvent with app_uninstalled type
            
        Returns:
            ProcessingResult with success status
            
        Validates: Requirements 12.5
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            team_id = event.team_id
            
            logger.info("Processing app uninstall event", extra={
                'event_id': event.event_id,
                'team_id': team_id
            })
            
            # Handle uninstall (revoke token and delete data)
            success = await oauth_manager.handle_uninstall(team_id)
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            if success:
                logger.info("App uninstall processed successfully", extra={
                    'event_id': event.event_id,
                    'team_id': team_id,
                    'processing_time_ms': int(processing_time)
                })
                
                return ProcessingResult(
                    success=True,
                    event_id=event.event_id,
                    processing_time_ms=int(processing_time),
                    context={'team_id': team_id}
                )
            else:
                logger.warning("App uninstall processing incomplete", extra={
                    'event_id': event.event_id,
                    'team_id': team_id
                })
                
                return ProcessingResult(
                    success=False,
                    event_id=event.event_id,
                    processing_time_ms=int(processing_time),
                    error="Token not found or already deleted"
                )
        
        except Exception as e:
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.error("App uninstall processing failed", extra={
                'event_id': event.event_id,
                'team_id': event.team_id,
                'error': str(e),
                'processing_time_ms': int(processing_time)
            })
            
            return ProcessingResult(
                success=False,
                event_id=event.event_id,
                processing_time_ms=int(processing_time),
                error=str(e)
            )
    
    return handle_app_uninstall
