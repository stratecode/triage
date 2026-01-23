# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Background scheduler for asynchronous operations and polling."""

import threading
import time
import logging
from datetime import datetime, time as dt_time
from typing import Optional, Callable, List
from queue import PriorityQueue, Empty
from enum import Enum
from dataclasses import dataclass, field

from triage.jira_client import JiraClient
from triage.plan_generator import PlanGenerator
from triage.models import JiraIssue, DailyPlan


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OperationPriority(Enum):
    """Priority levels for operations."""
    BLOCKING = 0  # Highest priority - blocking task operations
    NORMAL = 1    # Normal priority - regular operations


@dataclass(order=True)
class Operation:
    """Represents a queued operation."""
    priority: int = field(compare=True)
    operation_type: str = field(compare=False)
    callback: Callable = field(compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)


class BackgroundScheduler:
    """
    Manages asynchronous operations and polling.
    """
    
    def __init__(
        self,
        jira_client: JiraClient,
        plan_generator: PlanGenerator,
        poll_interval_minutes: int = 15,
        notification_callback: Optional[Callable] = None
    ):
        """
        Initialize background scheduler.
        
        Args:
            jira_client: JIRA client for fetching tasks
            plan_generator: Plan generator for creating plans
            poll_interval_minutes: Interval between blocking task polls (default: 15)
            notification_callback: Optional callback for notifications
        """
        self.jira_client = jira_client
        self.plan_generator = plan_generator
        self.poll_interval_minutes = poll_interval_minutes
        self.notification_callback = notification_callback
        
        # Threading control
        self._stop_event = threading.Event()
        self._polling_thread: Optional[threading.Thread] = None
        self._queue_thread: Optional[threading.Thread] = None
        
        # Operation queue with priority ordering
        self._operation_queue: PriorityQueue[Operation] = PriorityQueue()
        
        # Track scheduled daily plan time
        self._daily_plan_time: Optional[dt_time] = None
        self._last_plan_date: Optional[datetime] = None
    
    def start(self) -> None:
        """
        Start background polling for blocking tasks.
        Runs in separate thread.
        """
        if self._polling_thread is not None and self._polling_thread.is_alive():
            logger.warning("Background scheduler already running")
            return
        
        # Clear stop event
        self._stop_event.clear()
        
        # Start polling thread
        self._polling_thread = threading.Thread(
            target=self._polling_loop,
            name="BlockingTaskPoller",
            daemon=True
        )
        self._polling_thread.start()
        
        # Start queue processing thread
        self._queue_thread = threading.Thread(
            target=self._process_queue,
            name="OperationQueueProcessor",
            daemon=True
        )
        self._queue_thread.start()
        
        logger.info(
            f"Background scheduler started (poll interval: {self.poll_interval_minutes} minutes)"
        )
    
    def stop(self) -> None:
        """
        Stop background polling gracefully.
        """
        if self._polling_thread is None or not self._polling_thread.is_alive():
            logger.warning("Background scheduler not running")
            return
        
        # Signal threads to stop
        self._stop_event.set()
        
        # Wait for threads to finish
        if self._polling_thread:
            self._polling_thread.join(timeout=5.0)
        
        if self._queue_thread:
            self._queue_thread.join(timeout=5.0)
        
        logger.info("Background scheduler stopped")
    
    def schedule_daily_plan(self, time_of_day: str) -> None:
        """
        Schedule automatic daily plan generation.
        
        Args:
            time_of_day: Time in HH:MM format (e.g., "08:00")
        """
        try:
            # Parse time string
            hour, minute = map(int, time_of_day.split(':'))
            self._daily_plan_time = dt_time(hour=hour, minute=minute)
            logger.info(f"Daily plan scheduled for {time_of_day}")
        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid time format: {time_of_day}. Expected HH:MM format.")
            raise ValueError(f"Invalid time format: {time_of_day}") from e
    
    def queue_operation(
        self,
        operation_type: str,
        callback: Callable,
        priority: OperationPriority = OperationPriority.NORMAL,
        *args,
        **kwargs
    ) -> None:
        """
        Queue an operation for execution.
        
        Args:
            operation_type: Type of operation (for logging)
            callback: Function to execute
            priority: Operation priority (BLOCKING or NORMAL)
            *args: Positional arguments for callback
            **kwargs: Keyword arguments for callback
        """
        operation = Operation(
            priority=priority.value,
            operation_type=operation_type,
            callback=callback,
            args=args,
            kwargs=kwargs
        )
        
        self._operation_queue.put(operation)
        logger.debug(f"Queued operation: {operation_type} (priority: {priority.name})")
    
    def _polling_loop(self) -> None:
        """
        Main polling loop that runs in background thread.
        Checks for blocking tasks and scheduled daily plans.
        """
        logger.info("Polling loop started")
        
        while not self._stop_event.is_set():
            try:
                # Check for blocking tasks
                self._check_blocking_tasks()
                
                # Check if daily plan should be generated
                self._check_daily_plan_schedule()
                
                # Sleep for poll interval (check stop event periodically)
                for _ in range(self.poll_interval_minutes * 60):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)
                # Continue polling even if there's an error
                time.sleep(60)  # Wait a minute before retrying
        
        logger.info("Polling loop stopped")
    
    def _check_blocking_tasks(self) -> None:
        """
        Check for blocking tasks and queue re-planning if found.
        """
        try:
            blocking_tasks = self.jira_client.fetch_blocking_tasks()
            
            if blocking_tasks:
                logger.info(f"Found {len(blocking_tasks)} blocking task(s)")
                
                # Queue blocking task handling with high priority
                for task in blocking_tasks:
                    self.queue_operation(
                        operation_type="handle_blocking_task",
                        callback=self._handle_blocking_task,
                        priority=OperationPriority.BLOCKING,
                        task=task
                    )
        except Exception as e:
            logger.error(f"Error checking blocking tasks: {e}", exc_info=True)
    
    def _check_daily_plan_schedule(self) -> None:
        """
        Check if it's time to generate the daily plan.
        """
        if self._daily_plan_time is None:
            return
        
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # Check if we've already generated a plan today
        if self._last_plan_date == current_date:
            return
        
        # Check if current time is past the scheduled time
        if current_time >= self._daily_plan_time:
            logger.info("Triggering scheduled daily plan generation")
            
            # Queue plan generation
            self.queue_operation(
                operation_type="generate_daily_plan",
                callback=self._generate_daily_plan,
                priority=OperationPriority.NORMAL
            )
            
            # Update last plan date
            self._last_plan_date = current_date
    
    def _process_queue(self) -> None:
        """
        Process operations from the queue.
        Runs in separate thread.
        """
        logger.info("Queue processor started")
        
        while not self._stop_event.is_set():
            try:
                # Get operation from queue (with timeout to check stop event)
                operation = self._operation_queue.get(timeout=1.0)
                
                logger.info(
                    f"Processing operation: {operation.operation_type} "
                    f"(priority: {operation.priority})"
                )
                
                # Execute operation
                try:
                    result = operation.callback(*operation.args, **operation.kwargs)
                    
                    # Send notification if callback provided
                    if self.notification_callback:
                        self.notification_callback(
                            operation_type=operation.operation_type,
                            status="completed",
                            result=result
                        )
                        
                except Exception as e:
                    logger.error(
                        f"Error executing operation {operation.operation_type}: {e}",
                        exc_info=True
                    )
                    
                    # Send error notification
                    if self.notification_callback:
                        self.notification_callback(
                            operation_type=operation.operation_type,
                            status="failed",
                            error=str(e)
                        )
                
                # Mark task as done
                self._operation_queue.task_done()
                
            except Empty:
                # No operations in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error in queue processor: {e}", exc_info=True)
        
        logger.info("Queue processor stopped")
    
    def _handle_blocking_task(self, task: JiraIssue) -> None:
        """
        Handle a detected blocking task.
        
        Args:
            task: Blocking task that was detected
        """
        logger.info(f"Handling blocking task: {task.key} - {task.summary}")
        
        # In a full implementation, this would:
        # 1. Load current plan
        # 2. Generate re-plan with blocking task
        # 3. Present to user for approval
        # 4. Replace current plan if approved
        
        # For now, just log the detection
        logger.info(f"Blocking task detected: {task.key}")
    
    def _generate_daily_plan(self) -> DailyPlan:
        """
        Generate daily plan.
        
        Returns:
            Generated DailyPlan
        """
        logger.info("Generating daily plan")
        
        plan = self.plan_generator.generate_daily_plan()
        
        logger.info(
            f"Daily plan generated with {len(plan.priorities)} priorities "
            f"and {len(plan.admin_block.tasks)} admin tasks"
        )
        
        return plan
