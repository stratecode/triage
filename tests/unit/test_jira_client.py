# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for JIRA Client."""

import pytest
from unittest.mock import Mock, patch
from ai_secretary.jira_client import JiraClient, JiraConnectionError, JiraAuthError
from ai_secretary.models import JiraIssue


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
    
    @patch('ai_secretary.jira_client.requests.Session.get')
    def test_fetch_active_tasks_success(self, mock_get):
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
        mock_get.return_value = mock_response
        
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
    
    @patch('ai_secretary.jira_client.requests.Session.get')
    def test_fetch_active_tasks_auth_error(self, mock_get):
        """Test authentication error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="invalid-token"
        )
        
        with pytest.raises(JiraAuthError):
            client.fetch_active_tasks()
    
    @patch('ai_secretary.jira_client.requests.Session.get')
    def test_fetch_active_tasks_connection_error(self, mock_get):
        """Test connection error handling."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )
        
        with pytest.raises(JiraConnectionError):
            client.fetch_active_tasks()
    
    @patch('ai_secretary.jira_client.requests.Session.get')
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
    
    @patch('ai_secretary.jira_client.requests.Session.get')
    def test_fetch_active_tasks_with_project_filter(self, mock_get):
        """Test that project filter is included in JQL query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'issues': []}
        mock_get.return_value = mock_response
        
        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            project="MYPROJ"
        )
        
        client.fetch_active_tasks()
        
        # Verify the JQL query includes the project filter
        call_args = mock_get.call_args
        params = call_args[1]['params']
        jql = params['jql']
        
        assert 'project = MYPROJ' in jql
        assert 'assignee = currentUser()' in jql
        assert 'resolution = Unresolved' in jql
