# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Event Bus

Provides pub/sub event infrastructure for asynchronous communication between
TrIAge Core and plugins. Enables core components to emit events (plan generated,
task blocked, etc.) that plugins can subscribe to and react to.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass
class Event:
    """
    Core event representation.

    Events are emitted by TrIAge Core when significant operations complete
    (plan generation, blocking task detection, approval timeout, etc.).
    """

    event_type: str  # e.g., 'plan_generated', 'task_blocked', 'approval_timeout'
    event_data: Dict[str, Any]  # Event payload with context
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "triage_core"  # Source of the event


# Type alias for event handler functions
EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """
    Pub/sub event bus for core-to-plugin communication.

    The event bus enables loose coupling between TrIAge Core and plugins.
    Core components emit events without knowing which plugins are listening,
    and plugins subscribe to events they care about.

    Features:
    - Asynchronous event processing
    - Multiple subscribers per event type
    - Error isolation (one handler failure doesn't affect others)
    - Queue-based processing for high-volume scenarios
    """

    def __init__(self):
        """Initialize the event bus."""
        self.subscribers: Dict[str, List[EventHandler]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.logger = logging.getLogger(__name__)
        self._processing_task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to an event type.

        Registers a handler function to be called when events of the specified
        type are published. Multiple handlers can subscribe to the same event type.

        Args:
            event_type: Type of event to subscribe to (e.g., 'plan_generated')
            handler: Async function to call when event occurs
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []

        self.subscribers[event_type].append(handler)
        self.logger.info(
            f"Subscribed handler to event type: {event_type} "
            f"(total subscribers: {len(self.subscribers[event_type])})"
        )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove

        Returns:
            bool: True if handler was found and removed, False otherwise
        """
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                self.logger.info(f"Unsubscribed handler from event type: {event_type}")
                return True
            except ValueError:
                pass

        return False

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers synchronously.

        Immediately invokes all registered handlers for the event type.
        Handlers are executed concurrently, and errors are isolated (one
        handler failure doesn't prevent others from executing).

        Args:
            event: Event to publish
        """
        handlers = self.subscribers.get(event.event_type, [])

        if not handlers:
            self.logger.debug(f"No subscribers for event type: {event.event_type}")
            return

        self.logger.info(f"Publishing event: {event.event_type} to {len(handlers)} subscribers")

        # Execute all handlers concurrently
        tasks = [self._safe_invoke_handler(handler, event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Handler {i} failed for event {event.event_type}: {result}", exc_info=result)

    async def publish_async(self, event: Event) -> None:
        """
        Publish event asynchronously via queue.

        Adds the event to a queue for background processing. This is useful
        for high-volume scenarios where you don't want to block the caller
        waiting for all handlers to complete.

        Note: You must call start_processing() to begin processing queued events.

        Args:
            event: Event to publish
        """
        await self.event_queue.put(event)
        self.logger.debug(f"Queued event: {event.event_type} " f"(queue size: {self.event_queue.qsize()})")

    async def _safe_invoke_handler(self, handler: EventHandler, event: Event) -> None:
        """
        Safely invoke an event handler with error isolation.

        Args:
            handler: Handler function to invoke
            event: Event to pass to handler
        """
        try:
            await handler(event)
        except Exception as e:
            self.logger.error(f"Event handler raised exception: {e}", exc_info=True)
            # Don't re-raise - we want to isolate handler errors

    async def process_queue(self) -> None:
        """
        Process events from queue (background task).

        Continuously processes events from the queue until stopped.
        This method is designed to run as a background task.
        """
        self.logger.info("Event queue processing started")

        while True:
            try:
                event = await self.event_queue.get()
                await self.publish(event)
                self.event_queue.task_done()
            except asyncio.CancelledError:
                self.logger.info("Event queue processing cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error processing queued event: {e}", exc_info=True)

    def start_processing(self) -> None:
        """
        Start background processing of queued events.

        Creates a background task that continuously processes events from
        the queue. Call stop_processing() to stop the background task.
        """
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self.process_queue())
            self.logger.info("Started event queue processing task")
        else:
            self.logger.warning("Event queue processing already running")

    def stop_processing(self) -> None:
        """
        Stop background processing of queued events.

        Cancels the background processing task. Any events remaining in the
        queue will not be processed.
        """
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            self.logger.info("Stopped event queue processing task")

    def get_subscriber_count(self, event_type: str) -> int:
        """
        Get number of subscribers for an event type.

        Args:
            event_type: Type of event

        Returns:
            int: Number of registered handlers
        """
        return len(self.subscribers.get(event_type, []))

    def get_all_event_types(self) -> List[str]:
        """
        Get all event types that have subscribers.

        Returns:
            List[str]: List of event types
        """
        return list(self.subscribers.keys())

    def clear_subscribers(self, event_type: Optional[str] = None) -> None:
        """
        Clear subscribers for an event type or all event types.

        Args:
            event_type: Specific event type to clear, or None to clear all
        """
        if event_type:
            if event_type in self.subscribers:
                del self.subscribers[event_type]
                self.logger.info(f"Cleared subscribers for event type: {event_type}")
        else:
            self.subscribers.clear()
            self.logger.info("Cleared all event subscribers")
