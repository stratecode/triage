# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

import json
import os
import sys
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
import boto3

# Add parent directory to path to import triage package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from triage.jira_client import JiraClient
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

secrets_client = boto3.client('secretsmanager')

def get_jira_credentials() -> Dict[str, str]:
    """Retrieve JIRA credentials from Secrets Manager."""
    secret_name = os.environ['JIRA_SECRET_NAME']
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Error retrieving JIRA credentials: {e}")
        raise

def create_response(status_code: int, body: Any, headers: Optional[Dict] = None) -> Dict:
    """Create API Gateway response."""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body) if not isinstance(body, str) else body
    }

def health_check(event: Dict, context: Any) -> Dict:
    """Health check endpoint."""
    return create_response(200, {
        'status': 'healthy',
        'service': 'triage-api',
        'version': '0.1.0',
        'timestamp': datetime.utcnow().isoformat()
    })

def generate_plan(event: Dict, context: Any) -> Dict:
    """
    Generate daily plan.
    
    POST /api/v1/plan
    Body: {
        "date": "2026-02-17" (optional, defaults to today),
        "closure_rate": 0.67 (optional)
    }
    """
    try:
        # Parse request body (handle None body from API Gateway)
        body_str = event.get('body') or '{}'
        body = json.loads(body_str)
        plan_date = body.get('date', date.today().isoformat())
        closure_rate = body.get('closure_rate')
        
        logger.info(f"Generating plan for {plan_date}")
        
        # Get JIRA credentials
        creds = get_jira_credentials()
        
        # Initialize components
        jira_client = JiraClient(
            base_url=creds['jira_base_url'],
            email=creds['jira_email'],
            api_token=creds['jira_api_token'],
            project=creds.get('jira_project')  # Optional project filter
        )
        
        classifier = TaskClassifier()
        
        # Use /tmp for closure tracking in Lambda (only writable directory)
        closure_dir = os.path.join('/tmp', '.triage', 'closure')
        generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=closure_dir)
        
        # Fetch and classify tasks
        issues = jira_client.fetch_active_tasks()
        logger.info(f"Fetched {len(issues)} active issues")
        
        classified_tasks = [classifier.classify_task(issue) for issue in issues]
        
        # Generate plan
        plan = generator.generate_daily_plan(
            previous_closure_rate=closure_rate
        )
        
        # Convert to markdown
        markdown = plan.to_markdown()
        
        return create_response(200, {
            'success': True,
            'date': plan_date,
            'plan': {
                'priorities': [
                    {
                        'key': p.task.key,
                        'summary': p.task.summary,
                        'estimated_days': p.estimated_days,
                        'category': p.category.value
                    }
                    for p in plan.priorities
                ],
                'admin_block': {
                    'tasks': [
                        {
                            'key': t.task.key,
                            'summary': t.task.summary
                        }
                        for t in plan.admin_block.tasks
                    ],
                    'time_allocation_minutes': plan.admin_block.time_allocation_minutes,
                    'scheduled_time': plan.admin_block.scheduled_time
                } if plan.admin_block else None,
                'other_tasks_count': len(plan.other_tasks),
                'markdown': markdown
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating plan: {e}", exc_info=True)
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def get_plan(event: Dict, context: Any) -> Dict:
    """
    Get existing plan for a date.
    
    GET /api/v1/plan/{date}
    """
    try:
        plan_date = event['pathParameters']['date']
        logger.info(f"Retrieving plan for {plan_date}")
        
        # For now, regenerate the plan
        # In future, could cache in DynamoDB or S3
        return generate_plan({
            'body': json.dumps({'date': plan_date})
        }, context)
        
    except Exception as e:
        logger.error(f"Error retrieving plan: {e}", exc_info=True)
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def approve_plan(event: Dict, context: Any) -> Dict:
    """
    Approve or reject a plan.
    
    POST /api/v1/plan/{date}/approve
    Body: {
        "approved": true,
        "feedback": "optional feedback",
        "modifications": {...}
    }
    """
    try:
        plan_date = event['pathParameters']['date']
        body = json.loads(event.get('body', '{}'))
        
        approved = body.get('approved', False)
        feedback = body.get('feedback', '')
        
        logger.info(f"Plan approval for {plan_date}: {approved}")
        
        # Here you would implement the approval logic
        # For now, just acknowledge
        
        return create_response(200, {
            'success': True,
            'date': plan_date,
            'approved': approved,
            'message': 'Plan approval recorded'
        })
        
    except Exception as e:
        logger.error(f"Error approving plan: {e}", exc_info=True)
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def decompose_task(event: Dict, context: Any) -> Dict:
    """
    Decompose a long-running task into subtasks.
    
    POST /api/v1/task/{taskId}/decompose
    Body: {
        "target_days": 1
    }
    """
    try:
        task_id = event['pathParameters']['taskId']
        body = json.loads(event.get('body', '{}'))
        target_days = body.get('target_days', 1)
        
        logger.info(f"Decomposing task {task_id}")
        
        # Get JIRA credentials
        creds = get_jira_credentials()
        
        # Initialize components
        jira_client = JiraClient(
            base_url=creds['jira_base_url'],
            email=creds['jira_email'],
            api_token=creds['jira_api_token'],
            project=creds.get('jira_project')  # Optional project filter
        )
        
        classifier = TaskClassifier()
        
        # Use /tmp for closure tracking in Lambda (only writable directory)
        closure_dir = os.path.join('/tmp', '.triage', 'closure')
        generator = PlanGenerator(jira_client, classifier, closure_tracking_dir=closure_dir)
        
        # Fetch the specific task
        issue = jira_client.get_task_by_key(task_id)
        
        # Generate decomposition (returns List[SubtaskSpec])
        subtasks = generator.propose_decomposition(issue)
        
        return create_response(200, {
            'success': True,
            'task_id': task_id,
            'parent_key': task_id,
            'subtasks': [
                {
                    'summary': st.summary,
                    'description': st.description,
                    'estimated_days': st.estimated_days,
                    'order': st.order
                }
                for st in subtasks
            ]
        })
        
    except Exception as e:
        logger.error(f"Error decomposing task: {e}", exc_info=True)
        return create_response(500, {
            'success': False,
            'error': str(e)
        })
