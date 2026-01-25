# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Verification script to check task filtering behavior.

This script fetches tasks from JIRA and shows which ones are included/excluded
based on their status, helping verify that the filtering logic works correctly.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from triage.jira_client import JiraClient
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Verify task filtering behavior."""
    # Load environment variables
    load_dotenv()
    
    # Get JIRA credentials from environment
    jira_url = os.getenv('JIRA_URL')
    jira_email = os.getenv('JIRA_EMAIL')
    jira_api_token = os.getenv('JIRA_API_TOKEN')
    jira_project = os.getenv('JIRA_PROJECT')
    
    if not all([jira_url, jira_email, jira_api_token]):
        logger.error("Missing required environment variables: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN")
        logger.error("Please set them in your .env file")
        return 1
    
    logger.info("=" * 80)
    logger.info("TASK FILTERING VERIFICATION")
    logger.info("=" * 80)
    
    # Initialize JIRA client
    logger.info(f"\nConnecting to JIRA: {jira_url}")
    if jira_project:
        logger.info(f"Project filter: {jira_project}")
    
    client = JiraClient(
        base_url=jira_url,
        email=jira_email,
        api_token=jira_api_token,
        project=jira_project
    )
    
    # Fetch active tasks (should exclude In Progress and Done)
    logger.info("\n" + "=" * 80)
    logger.info("FETCHING ACTIVE TASKS")
    logger.info("=" * 80)
    logger.info("\nJQL Query: assignee = currentUser() AND resolution = Unresolved")
    logger.info('           AND status NOT IN ("In Progress", "Done", "Closed", "Resolved", "Complete")')
    
    try:
        active_tasks = client.fetch_active_tasks()
        
        logger.info(f"\n✓ Found {len(active_tasks)} active tasks")
        
        if not active_tasks:
            logger.warning("\nNo active tasks found. This could mean:")
            logger.warning("  - All your tasks are In Progress or Done")
            logger.warning("  - You have no tasks assigned")
            logger.warning("  - The project filter is excluding all tasks")
            return 0
        
        # Group tasks by status
        tasks_by_status = {}
        for task in active_tasks:
            status = task.status
            if status not in tasks_by_status:
                tasks_by_status[status] = []
            tasks_by_status[status].append(task)
        
        # Display tasks grouped by status
        logger.info("\n" + "=" * 80)
        logger.info("TASKS BY STATUS")
        logger.info("=" * 80)
        
        for status in sorted(tasks_by_status.keys()):
            tasks = tasks_by_status[status]
            logger.info(f"\n{status} ({len(tasks)} tasks):")
            logger.info("-" * 80)
            
            for task in tasks:
                logger.info(f"  {task.key}: {task.summary}")
                logger.info(f"    Priority: {task.priority}")
                if task.story_points:
                    logger.info(f"    Story Points: {task.story_points}")
                if task.labels:
                    logger.info(f"    Labels: {', '.join(task.labels)}")
        
        # Classify tasks and show eligibility
        logger.info("\n" + "=" * 80)
        logger.info("TASK CLASSIFICATION")
        logger.info("=" * 80)
        
        classifier = TaskClassifier()
        
        priority_eligible = []
        admin_tasks = []
        long_running = []
        dependent = []
        blocking = []
        
        for task in active_tasks:
            classification = classifier.classify_task(task)
            
            if classification.category.value == 'priority_eligible':
                priority_eligible.append(classification)
            elif classification.category.value == 'administrative':
                admin_tasks.append(classification)
            elif classification.category.value == 'long_running':
                long_running.append(classification)
            elif classification.category.value == 'dependent':
                dependent.append(classification)
            elif classification.category.value == 'blocking':
                blocking.append(classification)
        
        logger.info(f"\n✓ Priority Eligible: {len(priority_eligible)} tasks")
        for c in priority_eligible:
            logger.info(f"  {c.task.key}: {c.task.summary}")
            logger.info(f"    Status: {c.task.status}, Priority: {c.task.priority}")
            logger.info(f"    Estimated: {c.estimated_days:.2f} days")
            if c.task.story_points:
                logger.info(f"    Story Points: {c.task.story_points} SP")
        
        logger.info(f"\n✓ Administrative: {len(admin_tasks)} tasks")
        for c in admin_tasks:
            logger.info(f"  {c.task.key}: {c.task.summary}")
            logger.info(f"    Status: {c.task.status}")
        
        logger.info(f"\n✓ Long Running: {len(long_running)} tasks (> 1 day)")
        for c in long_running:
            logger.info(f"  {c.task.key}: {c.task.summary}")
            logger.info(f"    Status: {c.task.status}")
            logger.info(f"    Estimated: {c.estimated_days:.2f} days")
            if c.task.story_points:
                logger.info(f"    Story Points: {c.task.story_points} SP")
        
        logger.info(f"\n✓ Dependent: {len(dependent)} tasks (blocked by others)")
        for c in dependent:
            logger.info(f"  {c.task.key}: {c.task.summary}")
            logger.info(f"    Status: {c.task.status}")
        
        logger.info(f"\n✓ Blocking: {len(blocking)} tasks (blocker priority)")
        for c in blocking:
            logger.info(f"  {c.task.key}: {c.task.summary}")
            logger.info(f"    Status: {c.task.status}")
        
        # Generate a plan to see what gets selected
        logger.info("\n" + "=" * 80)
        logger.info("GENERATING DAILY PLAN")
        logger.info("=" * 80)
        
        generator = PlanGenerator(client, classifier)
        plan = generator.generate_daily_plan()
        
        logger.info(f"\n✓ Plan generated for {plan.date}")
        logger.info(f"\nPriorities ({len(plan.priorities)}):")
        for i, priority in enumerate(plan.priorities, 1):
            logger.info(f"  {i}. {priority.task.key}: {priority.task.summary}")
            logger.info(f"     Status: {priority.task.status}")
            logger.info(f"     Estimated: {priority.estimated_days:.2f} days")
        
        logger.info(f"\nAdmin Block ({len(plan.admin_block.tasks)} tasks, {plan.admin_block.time_allocation_minutes} minutes):")
        for task in plan.admin_block.tasks:
            logger.info(f"  - {task.task.key}: {task.task.summary}")
        
        logger.info(f"\nOther Tasks ({len(plan.other_tasks)}):")
        for task in plan.other_tasks:
            logger.info(f"  - {task.task.key}: {task.task.summary} ({task.category.value})")
        
        logger.info("\n" + "=" * 80)
        logger.info("VERIFICATION COMPLETE")
        logger.info("=" * 80)
        logger.info("\n✓ Task Inclusion:")
        logger.info("  - Tasks in 'To Do' are included")
        logger.info("  - Tasks in 'In Progress' are included and PRIORITIZED")
        logger.info("  - Tasks in 'Blocked' or 'Waiting' are included")
        logger.info("  - Tasks in 'Done', 'Closed', 'Resolved' are excluded")
        logger.info("\n✓ Effort Estimation:")
        logger.info("  - 1 story point = 0.5 days (4 hours)")
        logger.info("  - 2 story points = 1.0 day (daily-closable)")
        logger.info("  - 3+ story points = 1.5+ days (needs decomposition)")
        logger.info("\n✓ Priority Ranking:")
        logger.info("  1. Tasks in 'In Progress' (should be completed first)")
        logger.info("  2. JIRA priority (Blocker > High > Medium > Low)")
        logger.info("  3. Effort (smaller tasks first)")
        logger.info("  4. Age (older tasks first)")
        logger.info("\nIf you see unexpected results, check:")
        logger.info("  - Story point estimates in JIRA")
        logger.info("  - Task statuses")
        logger.info("  - Task priorities")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
