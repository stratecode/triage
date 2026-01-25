# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Command-line interface for AI Secretary."""

import os
import sys
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from triage.jira_client import JiraClient, JiraConnectionError, JiraAuthError
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


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
@click.version_option(version='0.1.0', prog_name='TrIAge')
@click.pass_context
def cli(ctx):
    """TrIAge - Execution support system for technical professionals.
    
    TrIAge reduces cognitive load by generating focused daily plans with
    a maximum of 3 real priorities. It treats JIRA as the single source of
    truth and operates asynchronously.
    
    \b
    Key Features:
      • Automatic daily plan generation
      • Intelligent task classification
      • Dependency detection
      • Administrative task grouping
      • Closure rate tracking
      • Long-running task decomposition
      • Automatic re-planning
    
    \b
    Configuration:
      Credentials are automatically loaded from the .env file
      in the project root. See .env.example for reference.
    
    \b
    Examples:
      triage generate-plan              # Generate daily plan
      triage generate-plan -o plan.md   # Save to file
      triage generate-plan --debug      # Debug mode
      triage --help                     # View help
    
    \b
    Documentation:
      https://github.com/your-org/triage
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    metavar='PATH',
    help='Save plan to file (default: stdout)'
)
@click.option(
    '--closure-rate',
    type=float,
    metavar='FLOAT',
    help='Previous day closure rate (0.0-1.0, e.g., 0.67 for 67%%)'
)
@click.option(
    '--debug',
    is_flag=True,
    help='Enable detailed logging for debugging'
)
@click.pass_context
def generate_plan(ctx, output: Optional[str], closure_rate: Optional[float], debug: bool):
    """Generate a daily plan from current JIRA tasks.
    
    This command fetches your active JIRA tasks, classifies them, and generates
    a structured daily plan with up to 3 priority tasks and grouped
    administrative tasks.
    
    \b
    The plan includes:
      • Up to 3 priority tasks (closable same day)
      • Administrative block (maximum 90 minutes)
      • Other active tasks (for reference)
      • Previous day closure rate (if provided)
    
    \b
    Configuration (environment variables in .env):
    
    \b
    Required:
      JIRA_BASE_URL     Your JIRA instance URL
                        Example: https://company.atlassian.net
      
      JIRA_EMAIL        Your JIRA account email
                        Example: user@company.com
      
      JIRA_API_TOKEN    Your JIRA API token
                        Generate at: https://id.atlassian.com/manage-profile/security/api-tokens
    
    \b
    Optional:
      JIRA_PROJECT      Filter tasks by project (e.g., PROJ)
                        Leave empty to see all projects
      
      ADMIN_TIME_START  Admin block start time (default: 14:00)
      ADMIN_TIME_END    Admin block end time (default: 15:30)
    
    \b
    Priority selection criteria:
      ✓ No third-party dependencies
      ✓ Estimated effort ≤ 1 day
      ✓ Not administrative tasks
      ✓ Not blocking tasks (handled by re-planning flow)
    
    \b
    Examples:
    
    \b
      # Generate plan to console
      $ triage generate-plan
    
    \b
      # Save plan to file
      $ triage generate-plan -o daily-plan.md
      $ triage generate-plan --output plan-2026-01-23.md
    
    \b
      # Include previous day closure rate
      $ triage generate-plan --closure-rate 0.67
      # (2 out of 3 tasks completed = 67%)
    
    \b
      # Debug mode with detailed logging
      $ triage generate-plan --debug
      $ triage generate-plan --debug 2> debug.log
    
    \b
      # Combination of options
      $ triage generate-plan --debug -o plan.md --closure-rate 0.75
    
    \b
    Output:
      The plan is generated in Markdown format with:
      - Header with date
      - Previous day closure rate (if available)
      - Priorities section (maximum 3)
      - Administrative block with schedule
      - Other active tasks for reference
    
    \b
    Troubleshooting:
      • Authentication error: Verify JIRA_EMAIL and JIRA_API_TOKEN
      • No eligible tasks: Use --debug to see filtering criteria
      • Connection error: Verify JIRA_BASE_URL and connectivity
      • View logs: Use --debug and redirect stderr to file
    
    \b
    See also:
      • Logging guide: docs/LOGGING_GUIDE.md
      • JIRA diagnostics: python examples/diagnose-jira-connection.py
      • MVP validation: python examples/validate_mvp.py
    """
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info("Starting TrIAge plan generation")
    
    # Load configuration
    config = Config()
    
    # Validate configuration
    is_valid, error_message = config.validate()
    if not is_valid:
        logger.error(f"Configuration validation failed: {error_message}")
        click.echo("❌ " + click.style("Configuration Error", fg='red', bold=True), err=True)
        click.echo(f"   {error_message}", err=True)
        click.echo("\n" + click.style("Required Configuration:", fg='yellow', bold=True), err=True)
        click.echo("   Create a .env file in the project root with:", err=True)
        click.echo("", err=True)
        click.echo("   " + click.style("JIRA_BASE_URL", fg='cyan') + "='https://your-company.atlassian.net'", err=True)
        click.echo("   " + click.style("JIRA_EMAIL", fg='cyan') + "='your-email@company.com'", err=True)
        click.echo("   " + click.style("JIRA_API_TOKEN", fg='cyan') + "='your-token-here'", err=True)
        click.echo("", err=True)
        click.echo("   See .env.example for more options.", err=True)
        click.echo("", err=True)
        click.echo("   " + click.style("Generate token:", fg='yellow'), err=True)
        click.echo("   https://id.atlassian.com/manage-profile/security/api-tokens", err=True)
        sys.exit(1)
    
    # Validate closure rate if provided
    if closure_rate is not None:
        if not 0.0 <= closure_rate <= 1.0:
            logger.error(f"Invalid closure rate: {closure_rate}")
            click.echo("❌ " + click.style("Error", fg='red', bold=True) + ": Invalid closure rate", err=True)
            click.echo(f"   Value must be between 0.0 and 1.0 (received: {closure_rate})", err=True)
            click.echo("", err=True)
            click.echo("   " + click.style("Examples:", fg='yellow'), err=True)
            click.echo("   --closure-rate 0.67  (2 out of 3 tasks = 67%)", err=True)
            click.echo("   --closure-rate 1.0   (3 out of 3 tasks = 100%)", err=True)
            click.echo("   --closure-rate 0.33  (1 out of 3 tasks = 33%)", err=True)
            sys.exit(1)
    
    try:
        # Initialize components
        click.echo("🔄 " + click.style("Connecting to JIRA...", fg='cyan'), err=True)
        logger.info(f"Initializing JIRA client for {config.jira_base_url}")
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
            click.echo(f"📋 Fetching tasks from project " + click.style(config.jira_project, fg='green', bold=True) + "...", err=True)
            logger.info(f"Generating plan for project: {config.jira_project}")
        else:
            click.echo("📋 " + click.style("Fetching and classifying tasks...", fg='cyan'), err=True)
            logger.info("Generating plan for all projects")
        
        plan = plan_generator.generate_daily_plan(previous_closure_rate=closure_rate)
        
        # Format as markdown
        markdown_output = plan.to_markdown()
        
        # Output to file or stdout
        if output:
            output_path = Path(output)
            output_path.write_text(markdown_output)
            click.echo("", err=True)
            click.echo("✅ " + click.style("Plan saved to:", fg='green', bold=True) + f" {output_path}", err=True)
            logger.info(f"Plan written to file: {output_path}")
        else:
            click.echo()  # Blank line before output
            click.echo(markdown_output)
            logger.debug("Plan written to stdout")
        
        # Print summary to stderr
        click.echo("", err=True)
        click.echo("📊 " + click.style("Plan Summary", fg='blue', bold=True) + f" - {plan.date}", err=True)
        click.echo(f"   • Priorities: " + click.style(str(len(plan.priorities)), fg='green', bold=True) + " tasks", err=True)
        click.echo(f"   • Admin: " + click.style(str(len(plan.admin_block.tasks)), fg='yellow') + f" tasks ({plan.admin_block.time_allocation_minutes} min)", err=True)
        click.echo(f"   • Other: " + click.style(str(len(plan.other_tasks)), fg='white') + " tasks", err=True)
        
        if plan.previous_closure_rate is not None:
            rate_pct = int(plan.previous_closure_rate * 100)
            rate_color = 'green' if rate_pct >= 67 else 'yellow' if rate_pct >= 33 else 'red'
            click.echo(f"   • Previous closure: " + click.style(f"{rate_pct}%", fg=rate_color, bold=True), err=True)
        
        click.echo("", err=True)
        
        logger.info("Plan generation completed successfully")
        
    except JiraAuthError as e:
        logger.error(f"Authentication error: {e}")
        click.echo("", err=True)
        click.echo("❌ " + click.style("Authentication Error", fg='red', bold=True), err=True)
        click.echo(f"   {str(e)}", err=True)
        click.echo("", err=True)
        click.echo(click.style("Verify:", fg='yellow', bold=True), err=True)
        click.echo("   • JIRA_EMAIL is correct", err=True)
        click.echo("   • JIRA_API_TOKEN is valid", err=True)
        click.echo("   • Token has necessary permissions", err=True)
        click.echo("", err=True)
        click.echo(click.style("Generate new token:", fg='yellow'), err=True)
        click.echo("   https://id.atlassian.com/manage-profile/security/api-tokens", err=True)
        sys.exit(1)
    
    except JiraConnectionError as e:
        logger.error(f"Connection error: {e}")
        click.echo("", err=True)
        click.echo("❌ " + click.style("Connection Error", fg='red', bold=True), err=True)
        click.echo(f"   {str(e)}", err=True)
        click.echo("", err=True)
        click.echo(click.style("Verify:", fg='yellow', bold=True), err=True)
        click.echo("   • Your internet connection", err=True)
        click.echo("   • JIRA_BASE_URL is correct", err=True)
        click.echo("   • JIRA service is available", err=True)
        click.echo("", err=True)
        click.echo(click.style("Diagnostics:", fg='yellow'), err=True)
        click.echo("   python examples/diagnose-jira-connection.py", err=True)
        sys.exit(1)
    
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        click.echo("", err=True)
        click.echo("❌ " + click.style("Unexpected Error", fg='red', bold=True), err=True)
        click.echo(f"   {str(e)}", err=True)
        click.echo("", err=True)
        click.echo(click.style("For more information:", fg='yellow'), err=True)
        click.echo("   • Run with --debug to see detailed logs", err=True)
        click.echo("   • Report the issue with complete logs", err=True)
        click.echo("", err=True)
        if not debug:
            click.echo(click.style("Tip:", fg='cyan') + " Run with --debug for more details", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
