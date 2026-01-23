# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for JIRA Client."""

import pytest
from unittest.mock import Mock, patch
from triage.jira_client import JiraClient, JiraConnectionError, JiraAuthError
from triage.models import JiraIssue


class TestJiraClientInit:
    """Tests for JiraClient initialization."""
    
    def test_init_sets_base_url(self):
        """Test that initialization sets base URL correctly."""
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        assert client.base_url == "https://test.atlassian.net"
    
    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from base URL."""
        client = JiraClient(
            base_url="https://test.atlassian.net/",
            email="test@example.com",
            api_token="test-token"
        )
        assert client.base_url == "https://test.atlassian.net"
    
    def test_init_sets_auth_headers(self):
        """Test that authentication headers are set correctly."""
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        assert 'Authorization' in client.session.headers
        assert client.session.headers['Authorization'].startswith('Basic ')
        assert client.session.headers['Content-Type'] == 'application/json'
        assert client.session.headers['Accept'] == 'application/json'
    
    def test_init_sets_project_filter(self):
        """Test that project filter is set when provided."""
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project="PROJ"
        )
        assert client.project == "PROJ"
    
    def test_init_project_filter_optional(self):
        """Test that project filter is optional."""
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        assert client.project is None


class TestFetchActiveTasks:
    """Tests for fetch_active_tasks method."""
    
    @patch('triage.jira_client.requests.Session.request')
    def test_fetch_active_tasks_success(self, mock_request):
        """Test successful task fetching."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'issues': [
                {
                    'key': 'PROJ-123',
                    'fields': {
                        'summary': 'Test task',
                        'description': 'Test description',
                        'issuetype': {'name': 'Story'},
                        'priority': {'name': 'High'},
                        'status': {'name': 'To Do'},
                        'assignee': {'emailAddress': 'test@example.com'},
                        'labels': ['test'],
                        'issuelinks': []
                    }
                }
            ]
        }
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        issues = client.fetch_active_tasks()
        
        assert len(issues) == 1
        assert isinstance(issues[0], JiraIssue)
        assert issues[0].key == 'PROJ-123'
        assert issues[0].summary == 'Test task'
        assert issues[0].priority == 'High'
    
    @patch('triage.jira_client.requests.Session.request')
    def test_fetch_active_tasks_auth_error(self, mock_request):
        """Test authentication error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="invalid-token"
        )
        
        with pytest.raises(JiraAuthError):
            client.fetch_active_tasks()
    
    @patch('triage.jira_client.requests.Session.request')
    def test_fetch_active_tasks_connection_error(self, mock_request):
        """Test connection error handling."""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        with pytest.raises(JiraConnectionError):
            client.fetch_active_tasks()
    
    @patch('triage.jira_client.requests.Session.get')
    def test_fetch_active_tasks_empty_response(self, mock_get):
        """Test handling of empty task list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'issues': []}
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        issues = client.fetch_active_tasks()
        
        assert len(issues) == 0
        assert isinstance(issues, list)
    
    @patch('triage.jira_client.requests.Session.request')
    def test_fetch_active_tasks_with_project_filter(self, mock_request):
        """Test that project filter is included in JQL query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'issues': []}
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project="MYPROJ"
        )
        
        client.fetch_active_tasks()
        
        # Verify the JQL query includes the project filter
        assert mock_request.called
        call_args = mock_request.call_args
        # The params are in kwargs
        params = call_args.kwargs.get('params', {})
        jql = params.get('jql', '')
        
        assert 'project = MYPROJ' in jql
        assert 'assignee = currentUser()' in jql
        assert 'resolution = Unresolved' in jql


class TestJiraClientErrorHandling:
    """Tests for comprehensive error handling in JIRA Client."""
    
    @patch('triage.jira_client.requests.Session.request')
    def test_rate_limiting_with_retry_after_header(self, mock_request):
        """Test rate limiting with Retry-After header."""
        from triage.jira_client import JiraRateLimitError
        
        # First call returns 429, subsequent calls also return 429
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '0.1'}
        mock_response_429.text = 'Rate limit exceeded'
        
        mock_request.return_value = mock_response_429
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=2
        )
        
        with pytest.raises(JiraRateLimitError) as exc_info:
            client.fetch_active_tasks()
        
        assert "rate limit exceeded" in str(exc_info.value).lower()
        # Should have tried max_retries + 1 times
        assert mock_request.call_count == 3
    
    @patch('triage.jira_client.requests.Session.request')
    @patch('time.sleep')
    def test_rate_limiting_exponential_backoff(self, mock_sleep, mock_request):
        """Test exponential backoff for rate limiting."""
        from triage.jira_client import JiraRateLimitError
        
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {}
        mock_response_429.text = 'Rate limit exceeded'
        
        mock_request.return_value = mock_response_429
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=2,
            initial_backoff=1.0
        )
        
        with pytest.raises(JiraRateLimitError):
            client.fetch_active_tasks()
        
        # Verify exponential backoff was used
        assert mock_sleep.call_count == 2
        # First backoff should be around 1.0 seconds (with jitter)
        first_sleep = mock_sleep.call_args_list[0][0][0]
        assert 1.0 <= first_sleep <= 1.2
        # Second backoff should be around 2.0 seconds (with jitter)
        second_sleep = mock_sleep.call_args_list[1][0][0]
        assert 2.0 <= second_sleep <= 2.4
    
    @patch('triage.jira_client.requests.Session.request')
    def test_invalid_jql_query_error(self, mock_request):
        """Test handling of invalid JQL queries (400 response)."""
        from triage.jira_client import JiraInvalidQueryError
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid JQL query'
        mock_response.json.return_value = {
            'errorMessages': ['Field "invalid_field" does not exist']
        }
        
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        with pytest.raises(JiraInvalidQueryError) as exc_info:
            client.fetch_active_tasks()
        
        assert "invalid" in str(exc_info.value).lower()
        assert "does not exist" in str(exc_info.value)
    
    @patch('triage.jira_client.requests.Session.request')
    @patch('time.sleep')
    def test_server_error_retry_logic(self, mock_sleep, mock_request):
        """Test retry logic for server errors (500+)."""
        # First two calls return 500, third call succeeds
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.text = 'Internal server error'
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'issues': []}
        
        mock_request.side_effect = [mock_response_500, mock_response_500, mock_response_200]
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=3,
            initial_backoff=0.1
        )
        
        issues = client.fetch_active_tasks()
        
        # Should succeed after retries
        assert isinstance(issues, list)
        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('triage.jira_client.requests.Session.request')
    def test_server_error_exhausted_retries(self, mock_request):
        """Test server error after exhausting all retries."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = 'Service unavailable'
        
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=2
        )
        
        with pytest.raises(JiraConnectionError) as exc_info:
            client.fetch_active_tasks()
        
        assert "server error" in str(exc_info.value).lower()
        assert "503" in str(exc_info.value)
    
    @patch('triage.jira_client.requests.Session.request')
    @patch('time.sleep')
    def test_timeout_retry_logic(self, mock_sleep, mock_request):
        """Test retry logic for timeout errors."""
        import requests
        
        # First call times out, second succeeds
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'issues': []}
        
        mock_request.side_effect = [
            requests.exceptions.Timeout("Request timed out"),
            mock_response_200
        ]
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=2,
            initial_backoff=0.1
        )
        
        issues = client.fetch_active_tasks()
        
        # Should succeed after retry
        assert isinstance(issues, list)
        assert mock_request.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('triage.jira_client.requests.Session.request')
    def test_timeout_exhausted_retries(self, mock_request):
        """Test timeout error after exhausting all retries."""
        import requests
        
        mock_request.side_effect = requests.exceptions.Timeout("Request timed out")
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=2
        )
        
        with pytest.raises(JiraConnectionError) as exc_info:
            client.fetch_active_tasks()
        
        assert "timed out" in str(exc_info.value).lower()
    
    @patch('triage.jira_client.requests.Session.request')
    @patch('time.sleep')
    def test_connection_error_retry_logic(self, mock_sleep, mock_request):
        """Test retry logic for connection errors."""
        import requests
        
        # First call fails with connection error, second succeeds
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'issues': []}
        
        mock_request.side_effect = [
            requests.exceptions.ConnectionError("Failed to connect"),
            mock_response_200
        ]
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            max_retries=2,
            initial_backoff=0.1
        )
        
        issues = client.fetch_active_tasks()
        
        # Should succeed after retry
        assert isinstance(issues, list)
        assert mock_request.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('triage.jira_client.requests.Session.request')
    def test_auth_error_no_retry(self, mock_request):
        """Test that authentication errors are not retried."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="invalid-token",
            max_retries=3
        )
        
        with pytest.raises(JiraAuthError):
            client.fetch_active_tasks()
        
        # Should not retry auth errors
        assert mock_request.call_count == 1
    
    @patch('triage.jira_client.requests.Session.request')
    def test_forbidden_error_handling(self, mock_request):
        """Test handling of 403 Forbidden errors."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = 'Forbidden'
        
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        with pytest.raises(JiraAuthError) as exc_info:
            client.fetch_active_tasks()
        
        assert "authentication failed" in str(exc_info.value).lower()
        assert "403" in str(exc_info.value)
    
    @patch('triage.jira_client.requests.Session.request')
    def test_410_gone_error_handling(self, mock_request):
        """Test handling of 410 Gone errors (deprecated endpoints)."""
        mock_response = Mock()
        mock_response.status_code = 410
        mock_response.url = "https://test.atlassian.net/rest/api/3/search/jql"
        mock_response.text = 'Endpoint no longer available'
        
        mock_request.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        with pytest.raises(JiraConnectionError) as exc_info:
            client.fetch_active_tasks()
        
        assert "410" in str(exc_info.value)
        assert "no longer available" in str(exc_info.value).lower()
