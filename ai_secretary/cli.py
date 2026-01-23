# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Command-line interface for AI Secretary."""

import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from ai_secretary.jira_client import JiraClient, JiraConnectionError, JiraAuthError
from ai_secretary.task_classifier import TaskClassifier
from ai_secretary.plan_generator import PlanGenerator

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for AI Secretary."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.jira_base_url = os.environ.get('JIRA_BASE_URL', '')
        self.jira_email = os.environ.get('JIRA_EMAIL', '')
        self.jira_api_token = os.environ.get('JIRA_API_TOKEN', '')
        self.jira_project = os.environ.get('JIRA_PROJECT', '')  # Optional project filter
        self.admin_time_start = os.environ.get('ADMIN_TIME_START', '14:00')
        self.admin_time_end = os.environ.get('ADMIN_TIME_END', '15:30')
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate that required configuration is present.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.jira_base_url:
            return False, "JIRA_BASE_URL environment variable is required"
        
        if not self.jira_email:
            return False, "JIRA_EMAIL environment variable is required"
        
        if not self.jira_api_token:
            return False, "JIRA_API_TOKEN environment variable is required"
        
        return True, None


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """AI Secretary - Execution support system for senior technical professionals.
    
    Generate focused daily plans with up to 3 priorities from your JIRA tasks.
    """
    pass


@cli.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file path (default: stdout)'
)
@click.option(
    '--closure-rate',
    type=float,
    help='Previous day closure rate (0.0-1.0)'
)
def generate_plan(output: Optional[str], closure_rate: Optional[float]):
    """Generate a daily plan from current JIRA tasks.
    
    This command fetches your active JIRA tasks, classifies them, and generates
    a structured daily plan with up to 3 priority tasks and grouped administrative
    tasks.
    
    Configuration is read from environment variables:
    
    \b
    Required:
      JIRA_BASE_URL     - Your JIRA instance URL (e.g., https://company.atlassian.net)
      JIRA_EMAIL        - Your JIRA account email
      JIRA_API_TOKEN    - Your JIRA API token
    
    \b
    Optional:
      JIRA_PROJECT      - Filter tasks by project key (e.g., PROJ)
      ADMIN_TIME_START  - Admin block start time (default: 14:00)
      ADMIN_TIME_END    - Admin block end time (default: 15:30)
    
    Examples:
    
    \b
      # Generate plan to stdout
      $ ai-secretary generate-plan
    
    \b
      # Generate plan to file
      $ ai-secretary generate-plan -o daily-plan.md
    
    \b
      # Generate plan with previous day's closure rate
      $ ai-secretary generate-plan --closure-rate 0.67
    """
    # Load configuration
    config = Config()
    
    # Validate configuration
    is_valid, error_message = config.validate()
    if not is_valid:
        click.echo(f"Error: {error_message}", err=True)
        click.echo("\nPlease set the required environment variables:", err=True)
        click.echo("  export JIRA_BASE_URL='https://your-company.atlassian.net'", err=True)
        click.echo("  export JIRA_EMAIL='your-email@company.com'", err=True)
        click.echo("  export JIRA_API_TOKEN='your-api-token'", err=True)
        sys.exit(1)
    
    # Validate closure rate if provided
    if closure_rate is not None:
        if not 0.0 <= closure_rate <= 1.0:
            click.echo("Error: Closure rate must be between 0.0 and 1.0", err=True)
            sys.exit(1)
    
    try:
        # Initialize components
        click.echo("Connecting to JIRA...", err=True)
        jira_client = JiraClient(
            base_url=config.jira_base_url,
            email=config.jira_email,
            api_token=config.jira_api_token,
            project=config.jira_project if config.jira_project else None
        )
        
        classifier = TaskClassifier()
        
        # Update admin time if configured
        admin_time = f"{config.admin_time_start}-{config.admin_time_end}"
        plan_generator = PlanGenerator(jira_client, classifier)
        plan_generator.DEFAULT_ADMIN_TIME = admin_time
        
        # Generate plan
        if config.jira_project:
            click.echo(f"Fetching and classifying tasks from project {config.jira_project}...", err=True)
        else:
            click.echo("Fetching and classifying tasks...", err=True)
        plan = plan_generator.generate_daily_plan(previous_closure_rate=closure_rate)
        
        # Format as markdown
        markdown_output = plan.to_markdown()
        
        # Output to file or stdout
        if output:
            output_path = Path(output)
            output_path.write_text(markdown_output)
            click.echo(f"\nDaily plan written to: {output_path}", err=True)
        else:
            click.echo()  # Blank line before output
            click.echo(markdown_output)
        
        # Print summary to stderr
        click.echo(f"\n✓ Generated plan for {plan.date}", err=True)
        click.echo(f"  Priorities: {len(plan.priorities)}", err=True)
        click.echo(f"  Admin tasks: {len(plan.admin_block.tasks)}", err=True)
        click.echo(f"  Other tasks: {len(plan.other_tasks)}", err=True)
        
    except JiraAuthError as e:
        click.echo(f"\nAuthentication Error: {e}", err=True)
        click.echo("\nPlease check your JIRA credentials:", err=True)
        click.echo("  - Verify JIRA_EMAIL is correct", err=True)
        click.echo("  - Verify JIRA_API_TOKEN is valid", err=True)
        click.echo("  - Generate a new API token at: https://id.atlassian.com/manage-profile/security/api-tokens", err=True)
        sys.exit(1)
    
    except JiraConnectionError as e:
        click.echo(f"\nConnection Error: {e}", err=True)
        click.echo("\nPlease check:", err=True)
        click.echo("  - Your internet connection", err=True)
        click.echo("  - JIRA_BASE_URL is correct", err=True)
        click.echo("  - JIRA service is available", err=True)
        sys.exit(1)
    
    except Exception as e:
        click.echo(f"\nUnexpected Error: {e}", err=True)
        click.echo("\nPlease report this issue with the full error message.", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
