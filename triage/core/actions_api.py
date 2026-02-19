# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Core Actions API

Exposes all TrIAge business logic to plugins through a clean, versioned interface.
This API provides access to plan generation, task management, and configuration
without requiring plugins to understand internal implementation details.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class CoreActionResult:
    """
    Standard result wrapper for core actions.

    All core actions return this structure to provide consistent error handling
    and result formatting across all plugins.
    """

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class CoreActionsAPI:
    """
    API for plugins to invoke TrIAge core business logic.

    This class wraps existing TrIAge components (PlanGenerator, TaskClassifier,
    JiraClient) and exposes them through a stable interface that plugins can
    depend on.
    """

    def __init__(self, jira_client=None, task_classifier=None, plan_generator=None, approval_manager=None):
        """
        Initialize the Core Actions API.

        Args:
            jira_client: JIRA client for task operations
            task_classifier: Task classification logic
            plan_generator: Daily plan generation logic
            approval_manager: Approval workflow management
        """
        self.jira_client = jira_client
        self.task_classifier = task_classifier
        self.plan_generator = plan_generator
        self.approval_manager = approval_manager
        self.logger = logging.getLogger(__name__)

    async def generate_plan(
        self, user_id: str, plan_date: Optional[date] = None, closure_rate: Optional[float] = None
    ) -> CoreActionResult:
        """
        Generate a daily plan for the user.

        Fetches active tasks from JIRA, classifies them, and generates a
        structured daily plan with up to 3 priority tasks.

        Args:
            user_id: User identifier
            plan_date: Date for the plan (defaults to today)
            closure_rate: Previous day's closure rate (optional)

        Returns:
            CoreActionResult: Result with plan data or error
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                return CoreActionResult(
                    success=False,
                    error="user_id is required and must be a non-empty string",
                    error_code="INVALID_USER_ID",
                )

            # Validate plan_date if provided
            if plan_date is not None and not isinstance(plan_date, date):
                return CoreActionResult(
                    success=False, error="plan_date must be a valid date object", error_code="INVALID_DATE"
                )

            # Validate closure_rate if provided
            if closure_rate is not None:
                if not isinstance(closure_rate, (int, float)):
                    return CoreActionResult(
                        success=False, error="closure_rate must be a number", error_code="INVALID_CLOSURE_RATE"
                    )
                import math

                if math.isnan(closure_rate) or math.isinf(closure_rate):
                    return CoreActionResult(
                        success=False, error="closure_rate cannot be NaN or infinity", error_code="INVALID_CLOSURE_RATE"
                    )
                if closure_rate < 0.0 or closure_rate > 1.0:
                    return CoreActionResult(
                        success=False,
                        error="closure_rate must be between 0.0 and 1.0",
                        error_code="INVALID_CLOSURE_RATE",
                    )

            if not self.jira_client or not self.task_classifier or not self.plan_generator:
                return CoreActionResult(
                    success=False, error="Core components not initialized", error_code="NOT_INITIALIZED"
                )

            # Use today if no date specified
            if plan_date is None:
                plan_date = date.today()

            # Fetch active tasks from JIRA
            self.logger.info(f"Fetching active tasks for user: {user_id}")
            issues = await self._fetch_user_tasks(user_id)

            # Classify tasks
            self.logger.info(f"Classifying {len(issues)} tasks")
            classified = [self.task_classifier.classify_task(issue) for issue in issues]

            # Generate daily plan
            self.logger.info("Generating daily plan")
            plan = self.plan_generator.generate_daily_plan(
                classified_tasks=classified, plan_date=plan_date, previous_closure_rate=closure_rate
            )

            return CoreActionResult(success=True, data={"plan": plan, "markdown": plan.to_markdown()})

        except Exception as e:
            self.logger.error(f"Plan generation failed: {e}", exc_info=True)
            return CoreActionResult(success=False, error=str(e), error_code="PLAN_GENERATION_FAILED")

    async def approve_plan(
        self, user_id: str, plan_date: date, approved: bool, feedback: Optional[str] = None
    ) -> CoreActionResult:
        """
        Approve or reject a plan.

        Args:
            user_id: User identifier
            plan_date: Date of the plan
            approved: Whether the plan is approved
            feedback: Optional feedback if rejected

        Returns:
            CoreActionResult: Result with approval status
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                return CoreActionResult(
                    success=False,
                    error="user_id is required and must be a non-empty string",
                    error_code="INVALID_USER_ID",
                )

            # Validate plan_date
            if not isinstance(plan_date, date):
                return CoreActionResult(
                    success=False,
                    error="plan_date is required and must be a valid date object",
                    error_code="INVALID_DATE",
                )

            # Validate approved
            if not isinstance(approved, bool):
                return CoreActionResult(
                    success=False, error="approved must be a boolean value", error_code="INVALID_APPROVED"
                )

            if not self.approval_manager:
                return CoreActionResult(
                    success=False, error="Approval manager not initialized", error_code="NOT_INITIALIZED"
                )

            self.logger.info(f"Processing plan approval for {user_id} on {plan_date}: " f"approved={approved}")

            # Process approval through approval manager
            result = await self._process_approval(
                user_id=user_id, plan_date=plan_date, approved=approved, feedback=feedback
            )

            return CoreActionResult(success=True, data=result)

        except Exception as e:
            self.logger.error(f"Approval processing failed: {e}", exc_info=True)
            return CoreActionResult(success=False, error=str(e), error_code="APPROVAL_FAILED")

    async def reject_plan(self, user_id: str, plan_date: date, feedback: str) -> CoreActionResult:
        """
        Reject a plan and trigger re-planning.

        Args:
            user_id: User identifier
            plan_date: Date of the plan
            feedback: User feedback on why plan was rejected

        Returns:
            CoreActionResult: Result with re-planning status
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                return CoreActionResult(
                    success=False,
                    error="user_id is required and must be a non-empty string",
                    error_code="INVALID_USER_ID",
                )

            # Validate plan_date
            if not isinstance(plan_date, date):
                return CoreActionResult(
                    success=False,
                    error="plan_date is required and must be a valid date object",
                    error_code="INVALID_DATE",
                )

            # Validate feedback (required for rejection)
            if not feedback or not isinstance(feedback, str) or not feedback.strip():
                return CoreActionResult(
                    success=False,
                    error="feedback is required when rejecting a plan and must be a non-empty string",
                    error_code="INVALID_FEEDBACK",
                )

            self.logger.info(f"Plan rejected for {user_id} on {plan_date}")

            # Process rejection
            await self.approve_plan(user_id=user_id, plan_date=plan_date, approved=False, feedback=feedback)

            # Trigger re-planning
            self.logger.info("Triggering re-planning")
            replan_result = await self.generate_plan(user_id=user_id, plan_date=plan_date)

            return CoreActionResult(
                success=True,
                data={"rejection_recorded": True, "new_plan": replan_result.data if replan_result.success else None},
            )

        except Exception as e:
            self.logger.error(f"Plan rejection failed: {e}", exc_info=True)
            return CoreActionResult(success=False, error=str(e), error_code="REJECTION_FAILED")

    async def decompose_task(self, user_id: str, task_key: str, target_days: float = 1.0) -> CoreActionResult:
        """
        Decompose a long-running task into subtasks.

        Args:
            user_id: User identifier
            task_key: JIRA key of task to decompose
            target_days: Target effort per subtask (default: 1.0 day)

        Returns:
            CoreActionResult: Result with subtask specifications
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                return CoreActionResult(
                    success=False,
                    error="user_id is required and must be a non-empty string",
                    error_code="INVALID_USER_ID",
                )

            # Validate task_key
            if not task_key or not isinstance(task_key, str) or not task_key.strip():
                return CoreActionResult(
                    success=False,
                    error="task_key is required and must be a non-empty string in format PROJECT-123",
                    error_code="INVALID_TASK_KEY",
                )

            # Validate target_days
            if not isinstance(target_days, (int, float)):
                return CoreActionResult(
                    success=False, error="target_days must be a positive number", error_code="INVALID_TARGET_DAYS"
                )
            import math

            if math.isnan(target_days) or math.isinf(target_days):
                return CoreActionResult(
                    success=False, error="target_days cannot be NaN or infinity", error_code="INVALID_TARGET_DAYS"
                )
            if target_days <= 0:
                return CoreActionResult(
                    success=False, error="target_days must be greater than 0", error_code="INVALID_TARGET_DAYS"
                )

            if not self.jira_client:
                return CoreActionResult(
                    success=False, error="JIRA client not initialized", error_code="NOT_INITIALIZED"
                )

            self.logger.info(f"Decomposing task {task_key} for user {user_id}")

            # Fetch task details
            task = await self._fetch_task(task_key)

            # Generate subtask specifications
            subtasks = await self._generate_subtasks(task=task, target_days=target_days)

            return CoreActionResult(
                success=True, data={"task_key": task_key, "subtasks": subtasks, "count": len(subtasks)}
            )

        except Exception as e:
            self.logger.error(f"Task decomposition failed: {e}", exc_info=True)
            return CoreActionResult(success=False, error=str(e), error_code="DECOMPOSITION_FAILED")

    async def get_status(self, user_id: str, plan_date: Optional[date] = None) -> CoreActionResult:
        """
        Get current plan status and task progress.

        Args:
            user_id: User identifier
            plan_date: Date of the plan (defaults to today)

        Returns:
            CoreActionResult: Result with status information
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                return CoreActionResult(
                    success=False,
                    error="user_id is required and must be a non-empty string",
                    error_code="INVALID_USER_ID",
                )

            # Validate plan_date if provided
            if plan_date is not None and not isinstance(plan_date, date):
                return CoreActionResult(
                    success=False, error="plan_date must be a valid date object", error_code="INVALID_DATE"
                )

            if plan_date is None:
                plan_date = date.today()

            self.logger.info(f"Fetching status for {user_id} on {plan_date}")

            # Fetch current plan and task statuses
            status = await self._fetch_plan_status(user_id, plan_date)

            return CoreActionResult(success=True, data=status)

        except Exception as e:
            self.logger.error(f"Status fetch failed: {e}", exc_info=True)
            return CoreActionResult(success=False, error=str(e), error_code="STATUS_FETCH_FAILED")

    async def configure_settings(self, user_id: str, settings: Dict[str, Any]) -> CoreActionResult:
        """
        Update user preferences and notification settings.

        Args:
            user_id: User identifier
            settings: Dictionary of settings to update

        Returns:
            CoreActionResult: Result with updated settings
        """
        try:
            # Validate user_id
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                return CoreActionResult(
                    success=False,
                    error="user_id is required and must be a non-empty string",
                    error_code="INVALID_USER_ID",
                )

            # Validate settings
            if not isinstance(settings, dict):
                return CoreActionResult(
                    success=False, error="settings must be a dictionary", error_code="INVALID_SETTINGS"
                )

            self.logger.info(f"Updating settings for {user_id}")

            # Validate and apply settings
            updated_settings = await self._update_user_settings(user_id, settings)

            return CoreActionResult(success=True, data=updated_settings)

        except Exception as e:
            self.logger.error(f"Settings update failed: {e}", exc_info=True)
            return CoreActionResult(success=False, error=str(e), error_code="SETTINGS_UPDATE_FAILED")

    # Private helper methods

    async def _fetch_user_tasks(self, user_id: str) -> List[Any]:
        """
        Fetch active tasks for user from JIRA.

        Args:
            user_id: User identifier (currently unused as jira_client uses currentUser())

        Returns:
            List of JiraIssue objects
        """
        # Note: Current implementation uses currentUser() from JIRA client
        # In a multi-user system, this would filter by user_id
        return self.jira_client.fetch_active_tasks()

    async def _fetch_task(self, task_key: str) -> Any:
        """
        Fetch specific task from JIRA.

        Args:
            task_key: JIRA key of the task

        Returns:
            JiraIssue object or None if not found
        """
        return self.jira_client.get_task_by_key(task_key)

    async def _generate_subtasks(self, task: Any, target_days: float) -> List[Dict[str, Any]]:
        """
        Generate subtask specifications.

        Args:
            task: JiraIssue to decompose
            target_days: Target effort per subtask

        Returns:
            List of subtask specifications as dictionaries
        """
        # Use plan generator's decomposition logic
        subtask_specs = self.plan_generator.propose_decomposition(task)

        # Convert SubtaskSpec objects to dictionaries
        return [
            {
                "summary": spec.summary,
                "description": spec.description,
                "estimated_days": spec.estimated_days,
                "order": spec.order,
            }
            for spec in subtask_specs
        ]

    async def _process_approval(
        self, user_id: str, plan_date: date, approved: bool, feedback: Optional[str]
    ) -> Dict[str, Any]:
        """
        Process plan approval.

        Args:
            user_id: User identifier
            plan_date: Date of the plan
            approved: Whether the plan is approved
            feedback: Optional feedback

        Returns:
            Dictionary with approval result
        """
        # In a full implementation, this would:
        # 1. Store approval status in database
        # 2. Trigger notifications
        # 3. Update plan state

        # For now, return the approval information
        result = {
            "user_id": user_id,
            "plan_date": plan_date.isoformat(),
            "approved": approved,
            "timestamp": date.today().isoformat(),
        }

        if feedback:
            result["feedback"] = feedback

        self.logger.info(f"Approval processed: user={user_id}, date={plan_date}, " f"approved={approved}")

        return result

    async def _fetch_plan_status(self, user_id: str, plan_date: date) -> Dict[str, Any]:
        """
        Fetch current plan status.

        Args:
            user_id: User identifier
            plan_date: Date of the plan

        Returns:
            Dictionary with plan status information
        """
        # Load closure record if available
        closure_record = self.plan_generator.load_closure_record(plan_date)

        if closure_record:
            return {
                "user_id": user_id,
                "date": plan_date.isoformat(),
                "status": "completed" if closure_record.closure_rate == 1.0 else "in_progress",
                "total_priorities": closure_record.total_priorities,
                "completed_priorities": closure_record.completed_priorities,
                "closure_rate": closure_record.closure_rate,
                "incomplete_tasks": closure_record.incomplete_tasks,
            }

        # No closure record found - plan may not exist yet
        return {
            "user_id": user_id,
            "date": plan_date.isoformat(),
            "status": "not_found",
            "message": "No plan found for this date",
        }

    async def _update_user_settings(self, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user settings.

        Args:
            user_id: User identifier
            settings: Dictionary of settings to update

        Returns:
            Dictionary with updated settings
        """
        # In a full implementation, this would:
        # 1. Validate settings against schema
        # 2. Persist to database
        # 3. Apply settings to user session

        # For now, validate basic settings structure
        valid_settings = {}

        # Supported settings
        if "notification_enabled" in settings:
            valid_settings["notification_enabled"] = bool(settings["notification_enabled"])

        if "approval_timeout_hours" in settings:
            timeout = settings["approval_timeout_hours"]
            if isinstance(timeout, (int, float)) and timeout > 0:
                valid_settings["approval_timeout_hours"] = timeout

        if "admin_block_time" in settings:
            # Validate time format (HH:MM-HH:MM)
            time_str = settings["admin_block_time"]
            if isinstance(time_str, str) and "-" in time_str:
                valid_settings["admin_block_time"] = time_str

        if "max_priorities" in settings:
            max_pri = settings["max_priorities"]
            if isinstance(max_pri, int) and 1 <= max_pri <= 5:
                valid_settings["max_priorities"] = max_pri

        self.logger.info(f"Settings updated for user {user_id}: {valid_settings}")

        return {"user_id": user_id, "settings": valid_settings, "updated_at": date.today().isoformat()}
