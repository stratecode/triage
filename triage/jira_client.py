# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""JIRA REST API client for fetching and managing tasks."""

import base64
from typing import List, Optional
import requests

from triage.models import JiraIssue, IssueLink


class JiraConnectionError(Exception):
    """Raised when JIRA is unavailable or connection fails."""
    pass


class JiraAuthError(Exception):
    """Raised when authentication fails."""
    pass


class JiraClient:
    """
    Handles all communication with JIRA REST API.
    Uses API token authentication for simplicity and security.
    """
    
    def __init__(self, base_url: str, email: str, api_token: str, project: Optional[str] = None):
        """
        Initialize JIRA client with authentication credentials.
        
        Args:
            base_url: JIRA instance URL (e.g., https://company.atlassian.net)
            email: User email for authentication
            api_token: API token generated from JIRA account settings
            project: Optional project key to filter tasks (e.g., "PROJ")
        """
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.api_token = api_token
        self.project = project
        
        # Set up HTTP session with authentication headers
        self.session = requests.Session()
        
        # Create Basic Auth header with email:api_token
        auth_string = f"{email}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        self.session.headers.update({
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def fetch_active_tasks(self) -> List[JiraIssue]:
        """
        Fetch all unresolved tasks assigned to current user.
        
        Returns:
            List of JiraIssue objects with full metadata
            
        Raises:
            JiraConnectionError: If JIRA is unavailable
            JiraAuthError: If authentication fails
        """
        # Build JQL query with optional project filter
        jql_parts = ["assignee = currentUser()", "resolution = Unresolved"]
        
        if self.project:
            jql_parts.append(f"project = {self.project}")
        
        jql = " AND ".join(jql_parts)
        
        # Try API v3 first (Jira Cloud standard)
        try:
            return self._fetch_with_api_version(jql, api_version=3)
        except JiraConnectionError as e:
            # If we get a 410, try API v2 as fallback
            if "410" in str(e):
                try:
                    return self._fetch_with_api_version(jql, api_version=2)
                except Exception:
                    # If v2 also fails, raise the original v3 error
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
        """
        # API v3 uses /search/jql endpoint (new as of 2024)
        # API v2 uses /search endpoint (legacy)
        if api_version == 3:
            endpoint = f"{self.base_url}/rest/api/3/search/jql"
        else:
            endpoint = f"{self.base_url}/rest/api/2/search"
        
        try:
            response = self.session.get(
                endpoint,
                params={
                    'jql': jql,
                    'maxResults': 100,
                    'fields': 'summary,description,issuetype,priority,status,assignee,customfield_10016,timetracking,labels,issuelinks'
                },
                timeout=30
            )
            
            # Handle authentication errors
            if response.status_code == 401 or response.status_code == 403:
                raise JiraAuthError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )
            
            # Handle 410 Gone - API endpoint deprecated or resource deleted
            if response.status_code == 410:
                raise JiraConnectionError(
                    f"JIRA API endpoint no longer available (410 Gone). "
                    f"URL: {response.url}. "
                    f"This may indicate an API version issue or deprecated endpoint. "
                    f"Response: {response.text}"
                )
            
            # Handle connection/server errors
            if response.status_code >= 500:
                raise JiraConnectionError(
                    f"JIRA server error: {response.status_code} - {response.text}"
                )
            
            # Raise for other HTTP errors
            response.raise_for_status()
            
            data = response.json()
            issues = []
            
            for issue_data in data.get('issues', []):
                issues.append(self._parse_issue(issue_data))
            
            return issues
            
        except requests.exceptions.Timeout:
            raise JiraConnectionError("Connection to JIRA timed out")
        except requests.exceptions.ConnectionError as e:
            raise JiraConnectionError(f"Failed to connect to JIRA: {str(e)}")
        except requests.exceptions.RequestException as e:
            if isinstance(e, (JiraConnectionError, JiraAuthError)):
                raise
            raise JiraConnectionError(f"JIRA request failed: {str(e)}")
    
    def _parse_issue(self, issue_data: dict) -> JiraIssue:
        """
        Parse JIRA API response into JiraIssue object.
        
        Args:
            issue_data: Raw issue data from JIRA API
            
        Returns:
            JiraIssue object with parsed data
        """
        fields = issue_data.get('fields', {})
        
        # Extract basic fields
        key = issue_data.get('key', '')
        summary = fields.get('summary', '')
        description = fields.get('description', '')
        
        # Handle description being a complex object in API v3
        if isinstance(description, dict):
            description = self._extract_text_from_adf(description)
        
        issue_type = fields.get('issuetype', {}).get('name', 'Task')
        priority = fields.get('priority', {}).get('name', 'Medium') if fields.get('priority') else 'Medium'
        status = fields.get('status', {}).get('name', 'To Do')
        
        # Extract assignee
        assignee_data = fields.get('assignee', {})
        assignee = assignee_data.get('emailAddress', '') if assignee_data else ''
        
        # Extract story points (customfield_10016 is common for story points in Jira Cloud)
        story_points = fields.get('customfield_10016')
        if story_points is not None:
            try:
                story_points = int(story_points)
            except (ValueError, TypeError):
                story_points = None
        
        # Extract time estimate
        time_tracking = fields.get('timetracking', {})
        time_estimate = time_tracking.get('originalEstimateSeconds')
        
        # Extract labels
        labels = fields.get('labels', [])
        
        # Extract issue links
        issue_links = []
        for link_data in fields.get('issuelinks', []):
            link_type_data = link_data.get('type', {})
            
            # Determine link direction and target
            if 'outwardIssue' in link_data:
                link_type = link_type_data.get('outward', 'relates to')
                target_issue = link_data['outwardIssue']
            elif 'inwardIssue' in link_data:
                link_type = link_type_data.get('inward', 'relates to')
                target_issue = link_data['inwardIssue']
            else:
                continue
            
            target_key = target_issue.get('key', '')
            target_summary = target_issue.get('fields', {}).get('summary', '')
            
            issue_links.append(IssueLink(
                link_type=link_type,
                target_key=target_key,
                target_summary=target_summary
            ))
        
        # Collect custom fields
        custom_fields = {}
        for field_key, field_value in fields.items():
            if field_key.startswith('customfield_') and field_key != 'customfield_10016':
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
            custom_fields=custom_fields
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
                if node.get('type') == 'text':
                    text_parts.append(node.get('text', ''))
                
                # Recurse into content
                if 'content' in node:
                    for child in node['content']:
                        extract_text(child)
            elif isinstance(node, list):
                for item in node:
                    extract_text(item)
        
        extract_text(adf_content)
        return ' '.join(text_parts)
