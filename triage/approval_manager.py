# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Approval management for user interaction and plan validation."""

import logging
import signal
from datetime import datetime
from typing import Any, Dict, List, Optional

from triage.core.event_bus import Event, EventBus
from triage.models import ApprovalResult, DailyPlan, JiraIssue, SubtaskSpec

# Set up logging
logger = logging.getLogger(__name__)


class ApprovalTimeoutError(Exception):
    """Raised when an approval request times out."""

    pass


class ApprovalManager:
    """
    Handles user interaction for approvals and feedback.

    Supports configurable timeouts, feedback collection, and user modifications.
    """

    def __init__(self, timeout_seconds: Optional[int] = None, event_bus: Optional[EventBus] = None):
        """
        Initialize the approval manager.

        Args:
            timeout_seconds: Timeout for approval requests in seconds.
                           If None, no timeout is applied (waits indefinitely).
                           Default is 24 hours (86400 seconds) when not specified.
            event_bus: Event bus for emitting events (optional)
        """
        # Default to 24 hours if not specified
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else 86400
        self.event_bus = event_bus
        self._timeout_handler_set = False

        logger.info(
            f"Approval manager initialized with timeout: {self.timeout_seconds}s ({self.timeout_seconds/3600:.1f} hours)"
        )
        if event_bus:
            logger.info("Approval manager configured with event bus for event emission")

    def _setup_timeout(self):
        """Set up timeout handler using signal alarm."""
        if self.timeout_seconds > 0:

            def timeout_handler(signum, frame):
                raise ApprovalTimeoutError("Approval request timed out")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout_seconds)
            self._timeout_handler_set = True

    def _clear_timeout(self):
        """Clear the timeout handler."""
        if self._timeout_handler_set:
            signal.alarm(0)
            self._timeout_handler_set = False

    def present_plan(self, plan: DailyPlan) -> ApprovalResult:
        """
        Present plan to user and wait for approval.

        This method displays the plan and collects approval with optional timeout.
        If timeout is configured and expires, marks the proposal as expired.

        Args:
            plan: Daily plan to present

        Returns:
            ApprovalResult with approval status

        Raises:
            ApprovalTimeoutError: If approval request times out
        """
        logger.info(f"Presenting daily plan for approval: {plan.date}")
        logger.debug(f"Plan has {len(plan.priorities)} priorities, {len(plan.admin_block.tasks)} admin tasks")

        # Display the plan in markdown format
        print("\n" + "=" * 80)
        print("DAILY PLAN FOR APPROVAL")
        print("=" * 80)
        print()
        print(plan.to_markdown())
        print("=" * 80)
        print()

        if self.timeout_seconds > 0:
            timeout_hours = self.timeout_seconds / 3600
            print(f"⏱️  This approval request will expire in {timeout_hours:.1f} hours")
            print()

        # Set up timeout
        try:
            self._setup_timeout()

            # Collect approval from user
            while True:
                response = input("Do you approve this plan? (yes/no/modify): ").strip().lower()

                if response in ["yes", "y"]:
                    self._clear_timeout()
                    logger.info("Plan approved by user")
                    return ApprovalResult(approved=True)
                elif response in ["no", "n"]:
                    self._clear_timeout()
                    # Collect feedback on rejection
                    feedback = input("Please provide feedback on why you're rejecting this plan: ").strip()
                    logger.info(f"Plan rejected by user. Feedback: {feedback if feedback else 'None'}")
                    return ApprovalResult(approved=False, feedback=feedback if feedback else None)
                elif response in ["modify", "m"]:
                    self._clear_timeout()
                    # Allow user to modify the plan
                    logger.info("User requested plan modifications")
                    modifications = self._collect_plan_modifications(plan)
                    logger.info(f"Plan modifications collected: {modifications}")
                    return ApprovalResult(approved=True, modifications=modifications)
                else:
                    print("Please enter 'yes', 'no', or 'modify'")
        except ApprovalTimeoutError:
            self._clear_timeout()
            logger.warning("Approval request timed out")

            # Emit approval_timeout event if event bus is configured
            if self.event_bus:
                import asyncio

                event = Event(
                    event_type="approval_timeout",
                    event_data={
                        "approval_type": "daily_plan",
                        "plan_date": plan.date.isoformat(),
                        "priority_count": len(plan.priorities),
                        "timeout_at": datetime.now().isoformat(),
                    },
                )
                try:
                    # Use asyncio to run the async publish method
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is already running, schedule the coroutine
                        asyncio.create_task(self.event_bus.publish(event))
                    else:
                        # If no loop is running, run it synchronously
                        loop.run_until_complete(self.event_bus.publish(event))
                    logger.info("Emitted approval_timeout event for daily plan")
                except Exception as e:
                    logger.error(f"Failed to emit approval_timeout event: {e}", exc_info=True)

            print("\n⏱️  Approval request has expired. The proposal is marked as expired.")
            print("A new approval will be needed when you're ready to proceed.")
            raise

    def present_decomposition(self, parent_task: JiraIssue, subtasks: List[SubtaskSpec]) -> ApprovalResult:
        """
        Present task decomposition proposal to user.

        This method displays a proposed decomposition of a long-running task
        into daily-closable subtasks and collects user approval with optional timeout.

        Args:
            parent_task: Original long-running task
            subtasks: Proposed subtasks

        Returns:
            ApprovalResult with approval status and optional modifications

        Raises:
            ApprovalTimeoutError: If approval request times out
        """
        # Display the decomposition proposal
        print("\n" + "=" * 80)
        print("TASK DECOMPOSITION PROPOSAL")
        print("=" * 80)
        print()
        print(f"Parent Task: [{parent_task.key}] {parent_task.summary}")
        print(f"Type: {parent_task.issue_type}")
        print(f"Priority: {parent_task.priority}")
        print()
        print("Proposed Subtasks:")
        print()

        for i, subtask in enumerate(subtasks, 1):
            effort_hours = subtask.estimated_days * 8
            print(f"{i}. {subtask.summary}")
            print(f"   Effort: {effort_hours:.1f} hours ({subtask.estimated_days:.2f} days)")
            print(f"   Order: {subtask.order}")
            print()

        print(f"Total subtasks: {len(subtasks)}")
        print()
        print("=" * 80)
        print()

        if self.timeout_seconds > 0:
            timeout_hours = self.timeout_seconds / 3600
            print(f"⏱️  This approval request will expire in {timeout_hours:.1f} hours")
            print()

        # Set up timeout
        try:
            self._setup_timeout()

            # Collect approval from user
            while True:
                response = input("Do you approve this decomposition? (yes/no/modify): ").strip().lower()

                if response in ["yes", "y"]:
                    self._clear_timeout()
                    return ApprovalResult(approved=True)
                elif response in ["no", "n"]:
                    self._clear_timeout()
                    # Collect feedback on rejection
                    feedback = input("Please provide feedback on why you're rejecting this decomposition: ").strip()
                    return ApprovalResult(approved=False, feedback=feedback if feedback else None)
                elif response in ["modify", "m"]:
                    self._clear_timeout()
                    # Allow user to modify the decomposition
                    modifications = self._collect_decomposition_modifications(subtasks)
                    return ApprovalResult(approved=True, modifications=modifications)
                else:
                    print("Please enter 'yes', 'no', or 'modify'")
        except ApprovalTimeoutError:
            self._clear_timeout()

            # Emit approval_timeout event if event bus is configured
            if self.event_bus:
                import asyncio

                event = Event(
                    event_type="approval_timeout",
                    event_data={
                        "approval_type": "decomposition",
                        "parent_task_key": parent_task.key,
                        "parent_task_summary": parent_task.summary,
                        "subtask_count": len(subtasks),
                        "timeout_at": datetime.now().isoformat(),
                    },
                )
                try:
                    # Use asyncio to run the async publish method
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.event_bus.publish(event))
                    else:
                        loop.run_until_complete(self.event_bus.publish(event))
                    logger.info("Emitted approval_timeout event for decomposition")
                except Exception as e:
                    logger.error(f"Failed to emit approval_timeout event: {e}", exc_info=True)

            print("\n⏱️  Approval request has expired. The proposal is marked as expired.")
            print("A new approval will be needed when you're ready to proceed.")
            raise

    def notify_blocking_task(self, blocking_task: JiraIssue, new_plan: DailyPlan) -> ApprovalResult:
        """
        Notify user of blocking task and present new plan.

        This method is called when a blocking task is detected that requires
        interrupting the current plan. It notifies the user of the interruption
        and presents the new plan for approval with optional timeout.

        Args:
            blocking_task: The blocking task detected
            new_plan: Proposed new plan incorporating the blocking task

        Returns:
            ApprovalResult with approval status

        Raises:
            ApprovalTimeoutError: If approval request times out
        """
        # Display blocking task notification
        print("\n" + "=" * 80)
        print("⚠️  BLOCKING TASK DETECTED - PLAN INTERRUPTION")
        print("=" * 80)
        print()
        print("A blocking task has been detected that requires immediate attention:")
        print()
        print(f"Task: [{blocking_task.key}] {blocking_task.summary}")
        print(f"Type: {blocking_task.issue_type}")
        print(f"Priority: {blocking_task.priority}")
        print(f"Status: {blocking_task.status}")
        print()

        if blocking_task.description:
            # Show first 200 characters of description
            desc_preview = blocking_task.description[:200]
            if len(blocking_task.description) > 200:
                desc_preview += "..."
            print(f"Description: {desc_preview}")
            print()

        print("Your current plan will be interrupted and replaced with a new plan")
        print("that includes this blocking task as a priority.")
        print()
        print("=" * 80)
        print()

        # Display the new plan
        print("PROPOSED NEW PLAN:")
        print()
        print(new_plan.to_markdown())
        print("=" * 80)
        print()

        if self.timeout_seconds > 0:
            timeout_hours = self.timeout_seconds / 3600
            print(f"⏱️  This approval request will expire in {timeout_hours:.1f} hours")
            print()

        # Set up timeout
        try:
            self._setup_timeout()

            # Collect approval from user
            while True:
                response = input("Do you approve this plan replacement? (yes/no/modify): ").strip().lower()

                if response in ["yes", "y"]:
                    self._clear_timeout()
                    return ApprovalResult(approved=True)
                elif response in ["no", "n"]:
                    self._clear_timeout()
                    # Collect feedback on rejection
                    feedback = input("Please provide feedback on why you're rejecting this re-plan: ").strip()
                    return ApprovalResult(approved=False, feedback=feedback if feedback else None)
                elif response in ["modify", "m"]:
                    self._clear_timeout()
                    # Allow user to modify the plan
                    modifications = self._collect_plan_modifications(new_plan)
                    return ApprovalResult(approved=True, modifications=modifications)
                else:
                    print("Please enter 'yes', 'no', or 'modify'")
        except ApprovalTimeoutError:
            self._clear_timeout()

            # Emit approval_timeout event if event bus is configured
            if self.event_bus:
                import asyncio

                event = Event(
                    event_type="approval_timeout",
                    event_data={
                        "approval_type": "blocking_task_replan",
                        "blocking_task_key": blocking_task.key,
                        "blocking_task_summary": blocking_task.summary,
                        "new_plan_date": new_plan.date.isoformat(),
                        "timeout_at": datetime.now().isoformat(),
                    },
                )
                try:
                    # Use asyncio to run the async publish method
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.event_bus.publish(event))
                    else:
                        loop.run_until_complete(self.event_bus.publish(event))
                    logger.info("Emitted approval_timeout event for blocking task replan")
                except Exception as e:
                    logger.error(f"Failed to emit approval_timeout event: {e}", exc_info=True)

            print("\n⏱️  Approval request has expired. The proposal is marked as expired.")
            print("A new approval will be needed when you're ready to proceed.")
            raise

    def _collect_plan_modifications(self, plan: DailyPlan) -> Dict[str, Any]:
        """
        Collect user modifications to a daily plan.

        Args:
            plan: The plan being modified

        Returns:
            Dictionary of modifications
        """
        modifications = {}

        print("\n--- Plan Modification ---")
        print("You can modify the following aspects of the plan:")
        print("1. Remove priority tasks")
        print("2. Reorder priority tasks")
        print("3. Cancel modification")
        print()

        while True:
            choice = input("What would you like to modify? (1-3): ").strip()

            if choice == "1":
                # Remove priority tasks
                if not plan.priorities:
                    print("No priority tasks to remove.")
                    continue

                print("\nCurrent priorities:")
                for i, classification in enumerate(plan.priorities, 1):
                    print(f"{i}. [{classification.task.key}] {classification.task.summary}")

                remove_input = input("\nEnter task numbers to remove (comma-separated, or 'cancel'): ").strip()
                if remove_input.lower() == "cancel":
                    continue

                try:
                    indices_to_remove = [int(x.strip()) - 1 for x in remove_input.split(",")]
                    # Validate indices
                    if all(0 <= i < len(plan.priorities) for i in indices_to_remove):
                        modifications["remove_priority_indices"] = indices_to_remove
                        print(f"✓ Will remove {len(indices_to_remove)} task(s)")
                    else:
                        print("Invalid task numbers. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter numbers separated by commas.")

            elif choice == "2":
                # Reorder priority tasks
                if len(plan.priorities) <= 1:
                    print("Need at least 2 priority tasks to reorder.")
                    continue

                print("\nCurrent priorities:")
                for i, classification in enumerate(plan.priorities, 1):
                    print(f"{i}. [{classification.task.key}] {classification.task.summary}")

                reorder_input = input("\nEnter new order (comma-separated task numbers, or 'cancel'): ").strip()
                if reorder_input.lower() == "cancel":
                    continue

                try:
                    new_order = [int(x.strip()) - 1 for x in reorder_input.split(",")]
                    # Validate: must be a permutation of existing indices
                    if len(new_order) == len(plan.priorities) and set(new_order) == set(range(len(plan.priorities))):
                        modifications["priority_order"] = new_order
                        print("✓ New order recorded")
                    else:
                        print("Invalid order. Must include all tasks exactly once.")
                except ValueError:
                    print("Invalid input. Please enter numbers separated by commas.")

            elif choice == "3":
                print("Modification cancelled.")
                return {}

            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                continue

            # Ask if user wants to make more modifications
            more = input("\nMake more modifications? (yes/no): ").strip().lower()
            if more not in ["yes", "y"]:
                break

        # Validate modifications don't violate constraints
        if "remove_priority_indices" in modifications:
            remaining_count = len(plan.priorities) - len(modifications["remove_priority_indices"])
            if remaining_count < 0:
                print("\n⚠️  Error: Cannot remove more tasks than exist.")
                return {}

        return modifications

    def _collect_decomposition_modifications(self, subtasks: List[SubtaskSpec]) -> Dict[str, Any]:
        """
        Collect user modifications to a decomposition proposal.

        Args:
            subtasks: The proposed subtasks

        Returns:
            Dictionary of modifications
        """
        modifications = {}

        print("\n--- Decomposition Modification ---")
        print("You can modify the following aspects:")
        print("1. Remove subtasks")
        print("2. Adjust subtask effort estimates")
        print("3. Cancel modification")
        print()

        while True:
            choice = input("What would you like to modify? (1-3): ").strip()

            if choice == "1":
                # Remove subtasks
                print("\nProposed subtasks:")
                for i, subtask in enumerate(subtasks, 1):
                    print(f"{i}. {subtask.summary} ({subtask.estimated_days:.2f} days)")

                remove_input = input("\nEnter subtask numbers to remove (comma-separated, or 'cancel'): ").strip()
                if remove_input.lower() == "cancel":
                    continue

                try:
                    indices_to_remove = [int(x.strip()) - 1 for x in remove_input.split(",")]
                    if all(0 <= i < len(subtasks) for i in indices_to_remove):
                        modifications["remove_subtask_indices"] = indices_to_remove
                        print(f"✓ Will remove {len(indices_to_remove)} subtask(s)")
                    else:
                        print("Invalid subtask numbers. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter numbers separated by commas.")

            elif choice == "2":
                # Adjust effort estimates
                print("\nProposed subtasks:")
                for i, subtask in enumerate(subtasks, 1):
                    print(f"{i}. {subtask.summary} ({subtask.estimated_days:.2f} days)")

                adjust_input = input("\nEnter subtask number to adjust (or 'cancel'): ").strip()
                if adjust_input.lower() == "cancel":
                    continue

                try:
                    index = int(adjust_input) - 1
                    if 0 <= index < len(subtasks):
                        new_effort = input(
                            f"Enter new effort in days (current: {subtasks[index].estimated_days:.2f}): "
                        ).strip()
                        new_effort_days = float(new_effort)

                        if new_effort_days <= 0:
                            print("Effort must be positive.")
                            continue
                        if new_effort_days > 1.0:
                            print(
                                "⚠️  Warning: Subtask effort exceeds 1 day. This violates the daily-closable constraint."
                            )
                            confirm = input("Continue anyway? (yes/no): ").strip().lower()
                            if confirm not in ["yes", "y"]:
                                continue

                        if "effort_adjustments" not in modifications:
                            modifications["effort_adjustments"] = {}
                        modifications["effort_adjustments"][index] = new_effort_days
                        print(f"✓ Effort for subtask {index + 1} updated to {new_effort_days:.2f} days")
                    else:
                        print("Invalid subtask number.")
                except ValueError:
                    print("Invalid input. Please enter a valid number.")

            elif choice == "3":
                print("Modification cancelled.")
                return {}

            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                continue

            # Ask if user wants to make more modifications
            more = input("\nMake more modifications? (yes/no): ").strip().lower()
            if more not in ["yes", "y"]:
                break

        return modifications
