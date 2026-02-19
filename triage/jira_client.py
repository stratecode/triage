# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""JIRA REST API client for fetching and managing tasks."""

import base64
import logging
import random
import time
from typing import List, Optional

import requests

from triage.models import IssueLink, JiraIssue, SubtaskSpec

# Set up logging
logger = logging.getLogger(__name__)


class JiraConnectionError(Exception):
    """Raised when JIRA is unavailable or connection fails."""

    pass


class JiraAuthError(Exception):
    """Raised when authentication fails."""

    pass


class JiraRateLimitError(Exception):
    """Raised when JIRA rate limit is exceeded."""

    pass


class JiraInvalidQueryError(Exception):
    """Raised when JQL query is invalid."""

    pass


class JiraClient:
    """
    Handles all communication with JIRA REST API.
    Uses API token authentication for simplicity and security.
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project: Optional[str] = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
    ):
        """
        Initialize JIRA client with authentication credentials.

        Args:
            base_url: JIRA instance URL (e.g., https://company.atlassian.net)
            email: User email for authentication
            api_token: API token generated from JIRA account settings
            project: Optional project key to filter tasks (e.g., "PROJ")
            max_retries: Maximum number of retries for rate-limited requests (default: 3)
            initial_backoff: Initial backoff time in seconds for exponential backoff (default: 1.0)
        """
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project = project
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

        logger.info(f"Initializing JIRA client for {self.base_url}")
        if self.project:
            logger.info(f"Project filter: {self.project}")
        logger.debug(f"Max retries: {self.max_retries}, Initial backoff: {self.initial_backoff}s")

        # Set up HTTP session with authentication headers
        self.session = requests.Session()

        # Create Basic Auth header with email:api_token
        auth_string = f"{email}:{api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        self.session.headers.update(
            {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/json", "Accept": "application/json"}
        )

        logger.debug("JIRA client initialized successfully")

    def _make_request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with exponential backoff retry logic for rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            JiraRateLimitError: If rate limit exceeded after all retries
            JiraAuthError: If authentication fails
            JiraConnectionError: If connection fails
            JiraInvalidQueryError: If JQL query is invalid
        """
        last_exception = None

        logger.debug(f"Making {method} request to {url}")

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{self.max_retries} for {method} {url}")

                response = self.session.request(method, url, **kwargs)

                # Handle authentication errors (401/403)
                if response.status_code in (401, 403):
                    error_msg = (
                        f"Authentication failed: {response.status_code} - {response.text}. "
                        f"Please verify your JIRA credentials (email and API token)."
                    )
                    logger.error(error_msg)
                    raise JiraAuthError(error_msg)

                # Handle invalid JQL queries (400)
                if response.status_code == 400:
                    error_message = response.text
                    try:
                        error_data = response.json()
                        if "errorMessages" in error_data:
                            error_message = "; ".join(error_data["errorMessages"])
                    except Exception:
                        pass

                    error_msg = (
                        f"Invalid JIRA request: {error_message}. "
                        f"This may indicate an invalid JQL query or malformed request."
                    )
                    logger.error(error_msg)
                    raise JiraInvalidQueryError(error_msg)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    # Check for Retry-After header
                    retry_after = response.headers.get("Retry-After")

                    if attempt < self.max_retries:
                        # Calculate backoff time
                        if retry_after:
                            try:
                                wait_time = float(retry_after)
                                logger.warning(f"Rate limited. Retry-After header: {wait_time}s")
                            except ValueError:
                                # Retry-After might be a date, use exponential backoff
                                wait_time = self.initial_backoff * (2**attempt)
                                logger.warning(f"Rate limited. Using exponential backoff: {wait_time}s")
                        else:
                            # Exponential backoff with jitter
                            wait_time = self.initial_backoff * (2**attempt)
                            jitter = random.uniform(0, wait_time * 0.1)
                            wait_time += jitter
                            logger.warning(f"Rate limited. Exponential backoff with jitter: {wait_time:.2f}s")

                        logger.info(f"Waiting {wait_time:.2f}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = (
                            f"JIRA rate limit exceeded after {self.max_retries} retries. "
                            f"Please wait before making more requests."
                        )
                        logger.error(error_msg)
                        raise JiraRateLimitError(error_msg)

                # Handle 410 Gone - API endpoint deprecated
                if response.status_code == 410:
                    error_msg = (
                        f"JIRA API endpoint no longer available (410 Gone). "
                        f"URL: {response.url}. "
                        f"This may indicate an API version issue or deprecated endpoint. "
                        f"Response: {response.text}"
                    )
                    logger.error(error_msg)
                    raise JiraConnectionError(error_msg)

                # Handle server errors (500+)
                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        # Retry server errors with exponential backoff
                        wait_time = self.initial_backoff * (2**attempt)
                        logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = (
                            f"JIRA server error: {response.status_code} - {response.text}. "
                            f"The JIRA server may be experiencing issues."
                        )
                        logger.error(error_msg)
                        raise JiraConnectionError(error_msg)

                # Raise for other HTTP errors
                response.raise_for_status()

                logger.debug(f"Request successful: {method} {url} -> {response.status_code}")
                return response

            except requests.exceptions.Timeout as e:
                last_exception = JiraConnectionError(
                    f"Connection to JIRA timed out after {kwargs.get('timeout', 'default')} seconds. "
                    f"Please check your network connection and JIRA availability."
                )
                logger.error(f"Request timeout: {e}")
                if attempt < self.max_retries:
                    wait_time = self.initial_backoff * (2**attempt)
                    logger.info(f"Retrying after timeout in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

            except requests.exceptions.ConnectionError as e:
                last_exception = JiraConnectionError(
                    f"Failed to connect to JIRA: {str(e)}. "
                    f"Please verify the JIRA URL ({self.base_url}) and your network connection."
                )
                logger.error(f"Connection error: {e}")
                if attempt < self.max_retries:
                    wait_time = self.initial_backoff * (2**attempt)
                    logger.info(f"Retrying after connection error in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

            except requests.exceptions.RequestException as e:
                # Re-raise our custom exceptions
                if isinstance(e, (JiraConnectionError, JiraAuthError, JiraRateLimitError, JiraInvalidQueryError)):
                    raise
                last_exception = JiraConnectionError(f"JIRA request failed: {str(e)}")
                logger.error(f"Request exception: {e}")
                if attempt < self.max_retries:
                    wait_time = self.initial_backoff * (2**attempt)
                    logger.info(f"Retrying after request exception in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

        # If we exhausted all retries, raise the last exception
        if last_exception:
            logger.error(f"All retry attempts exhausted. Last error: {last_exception}")
            raise last_exception

        error_msg = "Request failed after all retries"
        logger.error(error_msg)
        raise JiraConnectionError(error_msg)

    def fetch_active_tasks(self) -> List[JiraIssue]:
        """
        Fetch all unresolved tasks assigned to current user.

        Includes tasks in any state except completed (Done, Closed, Resolved).
        This includes "To Do", "In Progress", "Blocked", "Waiting", etc.

        Returns:
            List of JiraIssue objects with full metadata

        Raises:
            JiraConnectionError: If JIRA is unavailable
            JiraAuthError: If authentication fails
        """
        logger.info("Fetching active tasks from JIRA")

        # Build JQL query with optional project filter
        # Only exclude completed tasks
        jql_parts = [
            "assignee = currentUser()",
            "resolution = Unresolved",
            'status NOT IN ("Done", "Closed", "Resolved", "Complete", "Billed")',
        ]

        if self.project:
            jql_parts.append(f"project = {self.project}")

        jql = " AND ".join(jql_parts)
        logger.debug(f"JQL query: {jql}")

        # Try API v3 first (Jira Cloud standard)
        try:
            tasks = self._fetch_with_api_version(jql, api_version=3)
            logger.info(f"Successfully fetched {len(tasks)} active tasks")
            return tasks
        except JiraConnectionError as e:
            # If we get a 410, try API v2 as fallback
            if "410" in str(e):
                logger.warning("API v3 returned 410, falling back to API v2")
                try:
                    tasks = self._fetch_with_api_version(jql, api_version=2)
                    logger.info(f"Successfully fetched {len(tasks)} active tasks using API v2")
                    return tasks
                except Exception as fallback_error:
                    # If v2 also fails, raise the original v3 error
                    logger.error(f"API v2 fallback also failed: {fallback_error}")
                    raise e
            raise

    def _fetch_with_api_version(self, jql: str, api_version: int = 3) -> List[JiraIssue]:
        """
        Fetch tasks using specified API version.

        Args:
            jql: JQL query string
            api_version: JIRA API version (2 or 3)

        Returns:
            List of JiraIssue objects

        Raises:
            JiraConnectionError: If JIRA is unavailable
            JiraAuthError: If authentication fails
            JiraRateLimitError: If rate limit exceeded
            JiraInvalidQueryError: If JQL query is invalid
        """
        logger.debug(f"Fetching tasks using API v{api_version}")

        # API v3 uses /search/jql endpoint (new as of 2024)
        # API v2 uses /search endpoint (legacy)
        if api_version == 3:
            endpoint = f"{self.base_url}/rest/api/3/search/jql"
        else:
            endpoint = f"{self.base_url}/rest/api/2/search"

        logger.debug(f"Endpoint: {endpoint}")

        response = self._make_request_with_retry(
            "GET",
            endpoint,
            params={
                "jql": jql,
                "maxResults": 100,
                "fields": "summary,description,issuetype,priority,status,assignee,customfield_10142,timetracking,labels,issuelinks",
            },
            timeout=30,
        )

        data = response.json()
        issues = []

        for issue_data in data.get("issues", []):
            issues.append(self._parse_issue(issue_data))

        logger.debug(f"Parsed {len(issues)} issues from response")
        return issues

    def _parse_issue(self, issue_data: dict) -> JiraIssue:
        """
        Parse JIRA API response into JiraIssue object.

        Args:
            issue_data: Raw issue data from JIRA API

        Returns:
            JiraIssue object with parsed data
        """
        fields = issue_data.get("fields", {})

        # Extract basic fields
        key = issue_data.get("key", "")
        logger.debug(f"Parsing issue: {key}")

        summary = fields.get("summary", "")
        description = fields.get("description", "")

        # Handle description being a complex object in API v3
        if isinstance(description, dict):
            description = self._extract_text_from_adf(description)

        issue_type = fields.get("issuetype", {}).get("name", "Task")
        priority = fields.get("priority", {}).get("name", "Medium") if fields.get("priority") else "Medium"
        status = fields.get("status", {}).get("name", "To Do")

        # Extract assignee
        assignee_data = fields.get("assignee", {})
        assignee = assignee_data.get("emailAddress", "") if assignee_data else ""

        # Extract story points (customfield_10016 is common for story points in Jira Cloud)
        story_points = fields.get("customfield_10016")
        if story_points is not None:
            try:
                story_points = int(story_points)
                logger.debug(f"  Story points: {story_points}")
            except (ValueError, TypeError):
                logger.warning(f"  Invalid story points value: {story_points}")
                story_points = None

        # Extract time estimate
        time_tracking = fields.get("timetracking", {})
        time_estimate = time_tracking.get("originalEstimateSeconds")
        if time_estimate:
            logger.debug(f"  Time estimate: {time_estimate}s")

        # Extract labels
        labels = fields.get("labels", [])
        if labels:
            logger.debug(f"  Labels: {', '.join(labels)}")

        # Extract issue links
        issue_links = []
        for link_data in fields.get("issuelinks", []):
            link_type_data = link_data.get("type", {})

            # Determine link direction and target
            if "outwardIssue" in link_data:
                link_type = link_type_data.get("outward", "relates to")
                target_issue = link_data["outwardIssue"]
            elif "inwardIssue" in link_data:
                link_type = link_type_data.get("inward", "relates to")
                target_issue = link_data["inwardIssue"]
            else:
                continue

            target_key = target_issue.get("key", "")
            target_summary = target_issue.get("fields", {}).get("summary", "")

            issue_links.append(IssueLink(link_type=link_type, target_key=target_key, target_summary=target_summary))

        if issue_links:
            logger.debug(f"  Issue links: {len(issue_links)}")

        # Collect custom fields
        custom_fields = {}
        for field_key, field_value in fields.items():
            if field_key.startswith("customfield_") and field_key != "customfield_10016":
                custom_fields[field_key] = field_value

        return JiraIssue(
            key=key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            status=status,
            assignee=assignee,
            story_points=story_points,
            time_estimate=time_estimate,
            labels=labels,
            issue_links=issue_links,
            custom_fields=custom_fields,
        )

    def _extract_text_from_adf(self, adf_content: dict) -> str:
        """
        Extract plain text from Atlassian Document Format (ADF).

        Args:
            adf_content: ADF content object

        Returns:
            Plain text representation
        """
        if not isinstance(adf_content, dict):
            return str(adf_content)

        text_parts = []

        def extract_text(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    text_parts.append(node.get("text", ""))

                # Recurse into content
                if "content" in node:
                    for child in node["content"]:
                        extract_text(child)
            elif isinstance(node, list):
                for item in node:
                    extract_text(item)

        extract_text(adf_content)
        return " ".join(text_parts)

    def fetch_blocking_tasks(self) -> List[JiraIssue]:
        """
        Fetch tasks marked with blocking priority.

        Uses JQL: assignee = currentUser() AND priority = Blocker AND resolution = Unresolved

        Returns:
            List of blocking JiraIssue objects

        Raises:
            JiraConnectionError: If JIRA is unavailable
            JiraAuthError: If authentication fails
        """
        logger.info("Fetching blocking tasks from JIRA")

        # Build JQL query for blocking tasks
        jql_parts = ["assignee = currentUser()", "priority = Blocker", "resolution = Unresolved"]

        if self.project:
            jql_parts.append(f"project = {self.project}")

        jql = " AND ".join(jql_parts)
        logger.debug(f"JQL query: {jql}")

        # Try API v3 first (Jira Cloud standard)
        try:
            tasks = self._fetch_with_api_version(jql, api_version=3)
            logger.info(f"Successfully fetched {len(tasks)} blocking tasks")
            return tasks
        except JiraConnectionError as e:
            # If we get a 410, try API v2 as fallback
            if "410" in str(e):
                logger.warning("API v3 returned 410, falling back to API v2")
                try:
                    tasks = self._fetch_with_api_version(jql, api_version=2)
                    logger.info(f"Successfully fetched {len(tasks)} blocking tasks using API v2")
                    return tasks
                except Exception as fallback_error:
                    # If v2 also fails, raise the original v3 error
                    logger.error(f"API v2 fallback also failed: {fallback_error}")
                    raise e
            raise

    def create_subtask(self, parent_key: str, subtask: SubtaskSpec) -> str:
        """
        Create a subtask under a parent issue.

        Args:
            parent_key: JIRA key of parent issue (e.g., PROJ-123)
            subtask: Subtask specification with title, description, estimate

        Returns:
            JIRA key of created subtask

        Raises:
            JiraConnectionError: If JIRA is unavailable
            JiraAuthError: If authentication fails
            JiraRateLimitError: If rate limit exceeded
        """
        logger.info(f"Creating subtask for parent {parent_key}: {subtask.summary}")
        logger.debug(f"Subtask effort: {subtask.estimated_days} days, order: {subtask.order}")

        # First, fetch the parent issue to get project and issue type information
        logger.debug(f"Fetching parent issue {parent_key}")
        parent_response = self._make_request_with_retry(
            "GET", f"{self.base_url}/rest/api/3/issue/{parent_key}", timeout=30
        )

        # Handle 410 Gone - try API v2
        if parent_response.status_code == 410:
            logger.warning("API v3 returned 410, falling back to API v2")
            parent_response = self._make_request_with_retry(
                "GET", f"{self.base_url}/rest/api/2/issue/{parent_key}", timeout=30
            )

        parent_data = parent_response.json()

        # Extract project key and subtask issue type
        project_key = parent_data["fields"]["project"]["key"]
        logger.debug(f"Parent project: {project_key}")

        # Get available issue types for the project to find subtask type
        logger.debug("Fetching issue types for project")
        issue_types_response = self._make_request_with_retry(
            "GET",
            f"{self.base_url}/rest/api/3/issue/createmeta",
            params={"projectKeys": project_key, "expand": "projects.issuetypes.fields"},
            timeout=30,
        )

        # Handle 410 Gone - try API v2
        if issue_types_response.status_code == 410:
            logger.warning("API v3 returned 410, falling back to API v2")
            issue_types_response = self._make_request_with_retry(
                "GET",
                f"{self.base_url}/rest/api/2/issue/createmeta",
                params={"projectKeys": project_key, "expand": "projects.issuetypes.fields"},
                timeout=30,
            )

        issue_types_data = issue_types_response.json()

        # Find the subtask issue type
        subtask_type_id = None
        for project in issue_types_data.get("projects", []):
            for issue_type in project.get("issuetypes", []):
                if issue_type.get("subtask", False):
                    subtask_type_id = issue_type["id"]
                    logger.debug(f"Found subtask type ID: {subtask_type_id}")
                    break
            if subtask_type_id:
                break

        if not subtask_type_id:
            error_msg = "Could not find subtask issue type for project"
            logger.error(error_msg)
            raise JiraConnectionError(error_msg)

        # Prepare subtask creation payload
        # Convert estimated days to story points (1.25 days per story point)
        story_points = max(1, int(subtask.estimated_days / 1.25))
        logger.debug(f"Calculated story points: {story_points}")

        payload = {
            "fields": {
                "project": {"key": project_key},
                "parent": {"key": parent_key},
                "summary": subtask.summary,
                "description": subtask.description,
                "issuetype": {"id": subtask_type_id},
            }
        }

        # Add story points if the field exists (customfield_10016 is common)
        # We'll try to add it, but won't fail if it's not available
        if story_points:
            payload["fields"]["customfield_10016"] = story_points

        # Create the subtask
        logger.debug("Creating subtask in JIRA")
        create_response = self._make_request_with_retry(
            "POST", f"{self.base_url}/rest/api/3/issue", json=payload, timeout=30
        )

        # Handle 410 Gone - try API v2
        if create_response.status_code == 410:
            logger.warning("API v3 returned 410, falling back to API v2")
            create_response = self._make_request_with_retry(
                "POST", f"{self.base_url}/rest/api/2/issue", json=payload, timeout=30
            )

        # Extract and return the created subtask key
        result = create_response.json()
        subtask_key = result["key"]
        logger.info(f"Successfully created subtask: {subtask_key}")
        return subtask_key

    def get_task_by_key(self, task_key: str) -> Optional[JiraIssue]:
        """
        Fetch a single task by its key.

        Args:
            task_key: JIRA key of the task (e.g., PROJ-123)

        Returns:
            JiraIssue object if found, None if not found

        Raises:
            JiraConnectionError: If JIRA is unavailable
            JiraAuthError: If authentication fails
        """
        try:
            response = self._make_request_with_retry(
                "GET",
                f"{self.base_url}/rest/api/3/issue/{task_key}",
                params={
                    "fields": "summary,description,issuetype,priority,status,assignee,customfield_10142,timetracking,labels,issuelinks"
                },
                timeout=30,
            )

            # Handle 410 Gone - try API v2
            if response.status_code == 410:
                response = self._make_request_with_retry(
                    "GET",
                    f"{self.base_url}/rest/api/2/issue/{task_key}",
                    params={
                        "fields": "summary,description,issuetype,priority,status,assignee,customfield_10142,timetracking,labels,issuelinks"
                    },
                    timeout=30,
                )

            # Handle 404 - task not found
            if response.status_code == 404:
                return None

            issue_data = response.json()
            return self._parse_issue(issue_data)

        except JiraInvalidQueryError:
            # Task key is invalid
            return None

    def detect_status_changes(self, previous_tasks: List[JiraIssue]) -> dict:
        """
        Detect status changes in tasks since the previous fetch.

        Args:
            previous_tasks: List of tasks from previous fetch

        Returns:
            Dictionary mapping task keys to status change information:
            {
                'task_key': {
                    'old_status': 'In Progress',
                    'new_status': 'Done',
                    'completed': True/False
                }
            }
        """
        changes = {}

        # Create a map of previous task states
        previous_map = {task.key: task for task in previous_tasks}

        # Fetch current tasks
        current_tasks = self.fetch_active_tasks()
        current_map = {task.key: task for task in current_tasks}

        # Check for status changes in existing tasks
        for key, prev_task in previous_map.items():
            if key in current_map:
                curr_task = current_map[key]
                if prev_task.status != curr_task.status:
                    changes[key] = {
                        "old_status": prev_task.status,
                        "new_status": curr_task.status,
                        "completed": curr_task.status.lower() in ("done", "closed", "resolved"),
                    }
            else:
                # Task no longer in active tasks - likely completed or moved
                changes[key] = {"old_status": prev_task.status, "new_status": "Completed/Removed", "completed": True}

        return changes

    def detect_metadata_changes(self, previous_tasks: List[JiraIssue]) -> dict:
        """
        Detect metadata changes in tasks (priority, labels, estimates, etc.).

        Args:
            previous_tasks: List of tasks from previous fetch

        Returns:
            Dictionary mapping task keys to changed fields:
            {
                'task_key': {
                    'priority': {'old': 'Medium', 'new': 'High'},
                    'story_points': {'old': 3, 'new': 5},
                    ...
                }
            }
        """
        changes = {}

        # Create a map of previous task states
        previous_map = {task.key: task for task in previous_tasks}

        # Fetch current tasks
        current_tasks = self.fetch_active_tasks()
        current_map = {task.key: task for task in current_tasks}

        # Check for metadata changes
        for key, prev_task in previous_map.items():
            if key not in current_map:
                continue

            curr_task = current_map[key]
            task_changes = {}

            # Check priority changes
            if prev_task.priority != curr_task.priority:
                task_changes["priority"] = {"old": prev_task.priority, "new": curr_task.priority}

            # Check story points changes
            if prev_task.story_points != curr_task.story_points:
                task_changes["story_points"] = {"old": prev_task.story_points, "new": curr_task.story_points}

            # Check time estimate changes
            if prev_task.time_estimate != curr_task.time_estimate:
                task_changes["time_estimate"] = {"old": prev_task.time_estimate, "new": curr_task.time_estimate}

            # Check label changes
            prev_labels = set(prev_task.labels)
            curr_labels = set(curr_task.labels)
            if prev_labels != curr_labels:
                task_changes["labels"] = {
                    "added": list(curr_labels - prev_labels),
                    "removed": list(prev_labels - curr_labels),
                }

            # Check summary changes
            if prev_task.summary != curr_task.summary:
                task_changes["summary"] = {"old": prev_task.summary, "new": curr_task.summary}

            if task_changes:
                changes[key] = task_changes

        return changes

    def detect_dependency_changes(self, previous_tasks: List[JiraIssue]) -> dict:
        """
        Detect changes in task dependencies (issue links).

        Args:
            previous_tasks: List of tasks from previous fetch

        Returns:
            Dictionary mapping task keys to dependency changes:
            {
                'task_key': {
                    'added': [IssueLink, ...],
                    'removed': [IssueLink, ...],
                    'resolved': [task_key, ...]  # Dependencies that are now resolved
                }
            }
        """
        changes = {}

        # Create a map of previous task states
        previous_map = {task.key: task for task in previous_tasks}

        # Fetch current tasks
        current_tasks = self.fetch_active_tasks()
        current_map = {task.key: task for task in current_tasks}

        # Check for dependency changes
        for key, prev_task in previous_map.items():
            if key not in current_map:
                continue

            curr_task = current_map[key]

            # Create sets of link identifiers for comparison
            prev_links = {(link.link_type, link.target_key) for link in prev_task.issue_links}
            curr_links = {(link.link_type, link.target_key) for link in curr_task.issue_links}

            # Find added and removed links
            added_link_ids = curr_links - prev_links
            removed_link_ids = prev_links - curr_links

            if added_link_ids or removed_link_ids:
                task_changes = {}

                # Get full IssueLink objects for added links
                if added_link_ids:
                    added_links = [
                        link for link in curr_task.issue_links if (link.link_type, link.target_key) in added_link_ids
                    ]
                    task_changes["added"] = added_links

                # Get full IssueLink objects for removed links
                if removed_link_ids:
                    removed_links = [
                        link for link in prev_task.issue_links if (link.link_type, link.target_key) in removed_link_ids
                    ]
                    task_changes["removed"] = removed_links

                # Check if any blocking dependencies were resolved
                # (removed from issue links means they might be resolved)
                resolved_dependencies = []
                for link in task_changes.get("removed", []):
                    if "blocked" in link.link_type.lower() or "depends" in link.link_type.lower():
                        # Check if the linked task is now resolved
                        linked_task = self.get_task_by_key(link.target_key)
                        if linked_task is None or linked_task.status.lower() in ("done", "closed", "resolved"):
                            resolved_dependencies.append(link.target_key)

                if resolved_dependencies:
                    task_changes["resolved"] = resolved_dependencies

                changes[key] = task_changes

        return changes
