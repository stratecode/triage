# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for CLI interface."""

import os
from unittest.mock import Mock, patch, MagicMock
from datetime import date

import pytest
from click.testing import CliRunner

from triage.cli import cli, Config
from triage.models import (
    DailyPlan,
    AdminBlock,
    TaskClassification,
    TaskCategory,
    JiraIssue,
)


class TestConfig:
    """Tests for Config class."""
    
    def test_config_loads_from_environment(self):
        """Test that Config loads values from environment variables."""
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
            'ADMIN_TIME_START': '13:00',
            'ADMIN_TIME_END': '14:30',
        }):
            config = Config()
            
            assert config.jira_base_url == 'https://test.atlassian.net'
            assert config.jira_email == 'test@example.com'
            assert config.jira_api_token == 'test-token'
            assert config.admin_time_start == '13:00'
            assert config.admin_time_end == '14:30'
    
    def test_config_uses_defaults_for_optional_values(self):
        """Test that Config uses default values when optional vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            assert config.admin_time_start == '14:00'
            assert config.admin_time_end == '15:30'
    
    def test_config_loads_from_dotenv_file(self):
        """Test that Config loads values from .env file via dotenv."""
        import tempfile
        
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('JIRA_BASE_URL=https://dotenv.atlassian.net\n')
            f.write('JIRA_EMAIL=dotenv@example.com\n')
            f.write('JIRA_API_TOKEN=dotenv-token\n')
            env_file = f.name
        
        try:
            # Load the .env file
            from dotenv import load_dotenv
            load_dotenv(env_file, override=True)
            
            # Create config
            config = Config()
            
            # Verify values were loaded
            assert config.jira_base_url == 'https://dotenv.atlassian.net'
            assert config.jira_email == 'dotenv@example.com'
            assert config.jira_api_token == 'dotenv-token'
        finally:
            # Clean up
            os.unlink(env_file)
    
    def test_validate_success_with_all_required_vars(self):
        """Test that validate returns True when all required vars are set."""
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
        }):
            config = Config()
            is_valid, error = config.validate()
            
            assert is_valid is True
            assert error is None
    
    def test_validate_fails_without_base_url(self):
        """Test that validate fails when JIRA_BASE_URL is missing."""
        with patch.dict(os.environ, {
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
        }, clear=True):
            config = Config()
            is_valid, error = config.validate()
            
            assert is_valid is False
            assert 'JIRA_BASE_URL' in error
    
    def test_validate_fails_without_email(self):
        """Test that validate fails when JIRA_EMAIL is missing."""
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_API_TOKEN': 'test-token',
        }, clear=True):
            config = Config()
            is_valid, error = config.validate()
            
            assert is_valid is False
            assert 'JIRA_EMAIL' in error
    
    def test_validate_fails_without_api_token(self):
        """Test that validate fails when JIRA_API_TOKEN is missing."""
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
        }, clear=True):
            config = Config()
            is_valid, error = config.validate()
            
            assert is_valid is False
            assert 'JIRA_API_TOKEN' in error


class TestCLI:
    """Tests for CLI commands."""
    
    def test_cli_shows_version(self):
        """Test that --version flag shows version."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert '0.1.0' in result.output
    
    def test_cli_shows_help(self):
        """Test that --help flag shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'TrIAge' in result.output
        assert 'generate-plan' in result.output
    
    def test_generate_plan_shows_help(self):
        """Test that generate-plan --help shows command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['generate-plan', '--help'])
        
        assert result.exit_code == 0
        # Check for Spanish text since CLI is now in Spanish
        assert 'Generar un plan diario' in result.output or 'Generate a daily plan' in result.output
        assert 'JIRA_BASE_URL' in result.output
        assert '--output' in result.output
        assert '--closure-rate' in result.output
    
    def test_generate_plan_fails_without_config(self):
        """Test that generate-plan fails when config is missing."""
        runner = CliRunner()
        
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(cli, ['generate-plan'])
            
            assert result.exit_code == 1
            assert 'JIRA_BASE_URL' in result.output
    
    def test_generate_plan_validates_closure_rate(self):
        """Test that generate-plan validates closure rate range."""
        runner = CliRunner()
        
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
        }):
            # Test invalid closure rate > 1.0
            result = runner.invoke(cli, ['generate-plan', '--closure-rate', '1.5'])
            assert result.exit_code == 1
            # Check for Spanish or English text
            assert ('entre 0.0 y 1.0' in result.output or 'between 0.0 and 1.0' in result.output)
            
            # Test invalid closure rate < 0.0
            result = runner.invoke(cli, ['generate-plan', '--closure-rate', '-0.5'])
            assert result.exit_code == 1
            assert ('entre 0.0 y 1.0' in result.output or 'between 0.0 and 1.0' in result.output)
    
    @patch('triage.cli.PlanGenerator')
    @patch('triage.cli.TaskClassifier')
    @patch('triage.cli.JiraClient')
    def test_generate_plan_outputs_to_stdout(self, mock_jira, mock_classifier, mock_generator):
        """Test that generate-plan outputs markdown to stdout."""
        runner = CliRunner()
        
        # Create mock plan
        mock_issue = JiraIssue(
            key='TEST-1',
            summary='Test task',
            description='Test description',
            issue_type='Story',
            priority='High',
            status='To Do',
            assignee='test@example.com'
        )
        
        mock_classification = TaskClassification(
            task=mock_issue,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=0.5
        )
        
        mock_plan = DailyPlan(
            date=date(2026, 1, 23),
            priorities=[mock_classification],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time='14:00-15:30'),
            other_tasks=[]
        )
        
        # Configure mocks
        mock_gen_instance = Mock()
        mock_gen_instance.generate_daily_plan.return_value = mock_plan
        mock_generator.return_value = mock_gen_instance
        
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
        }):
            result = runner.invoke(cli, ['generate-plan'])
            
            assert result.exit_code == 0
            assert '# Daily Plan - 2026-01-23' in result.output
            assert 'TEST-1' in result.output
            assert 'Test task' in result.output
    
    @patch('triage.cli.PlanGenerator')
    @patch('triage.cli.TaskClassifier')
    @patch('triage.cli.JiraClient')
    def test_generate_plan_outputs_to_file(self, mock_jira, mock_classifier, mock_generator):
        """Test that generate-plan outputs markdown to file."""
        runner = CliRunner()
        
        # Create mock plan
        mock_issue = JiraIssue(
            key='TEST-1',
            summary='Test task',
            description='Test description',
            issue_type='Story',
            priority='High',
            status='To Do',
            assignee='test@example.com'
        )
        
        mock_classification = TaskClassification(
            task=mock_issue,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=0.5
        )
        
        mock_plan = DailyPlan(
            date=date(2026, 1, 23),
            priorities=[mock_classification],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time='14:00-15:30'),
            other_tasks=[]
        )
        
        # Configure mocks
        mock_gen_instance = Mock()
        mock_gen_instance.generate_daily_plan.return_value = mock_plan
        mock_generator.return_value = mock_gen_instance
        
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
        }):
            with runner.isolated_filesystem():
                result = runner.invoke(cli, ['generate-plan', '-o', 'plan.md'])
                
                assert result.exit_code == 0
                assert 'plan.md' in result.output
                
                # Verify file was created
                with open('plan.md', 'r') as f:
                    content = f.read()
                    assert '# Daily Plan - 2026-01-23' in content
                    assert 'TEST-1' in content
    
    @patch('triage.cli.PlanGenerator')
    @patch('triage.cli.TaskClassifier')
    @patch('triage.cli.JiraClient')
    def test_generate_plan_passes_closure_rate(self, mock_jira, mock_classifier, mock_generator):
        """Test that generate-plan passes closure rate to plan generator."""
        runner = CliRunner()
        
        # Create mock plan
        mock_plan = DailyPlan(
            date=date(2026, 1, 23),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time='14:00-15:30'),
            other_tasks=[],
            previous_closure_rate=0.67
        )
        
        # Configure mocks
        mock_gen_instance = Mock()
        mock_gen_instance.generate_daily_plan.return_value = mock_plan
        mock_generator.return_value = mock_gen_instance
        
        with patch.dict(os.environ, {
            'JIRA_BASE_URL': 'https://test.atlassian.net',
            'JIRA_EMAIL': 'test@example.com',
            'JIRA_API_TOKEN': 'test-token',
        }):
            result = runner.invoke(cli, ['generate-plan', '--closure-rate', '0.67'])
            
            assert result.exit_code == 0
            mock_gen_instance.generate_daily_plan.assert_called_once_with(previous_closure_rate=0.67)
