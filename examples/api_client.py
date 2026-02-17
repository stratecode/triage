# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Example API client for TrIAge serverless API.

Usage:
    python examples/api_client.py <API_URL> <JWT_TOKEN>
"""

import sys
import json
from datetime import date
from typing import Dict, Any, Optional
import requests


class TriageAPIClient:
    """Client for TrIAge REST API."""
    
    def __init__(self, base_url: str, token: str):
        """
        Initialize API client.
        
        Args:
            base_url: API base URL (e.g., https://xxx.execute-api.eu-south-2.amazonaws.com/dev)
            token: JWT authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        response = requests.get(f'{self.base_url}/api/v1/health')
        response.raise_for_status()
        return response.json()
    
    def generate_plan(
        self, 
        plan_date: Optional[str] = None,
        closure_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate daily plan.
        
        Args:
            plan_date: Date in YYYY-MM-DD format (defaults to today)
            closure_rate: Previous day's closure rate (0.0-1.0)
            
        Returns:
            Generated plan with priorities and admin block
        """
        payload = {}
        if plan_date:
            payload['date'] = plan_date
        if closure_rate is not None:
            payload['closure_rate'] = closure_rate
        
        response = self.session.post(
            f'{self.base_url}/api/v1/plan',
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_plan(self, plan_date: str) -> Dict[str, Any]:
        """
        Get existing plan for a date.
        
        Args:
            plan_date: Date in YYYY-MM-DD format
            
        Returns:
            Plan for the specified date
        """
        response = self.session.get(
            f'{self.base_url}/api/v1/plan/{plan_date}'
        )
        response.raise_for_status()
        return response.json()
    
    def approve_plan(
        self,
        plan_date: str,
        approved: bool,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve or reject a plan.
        
        Args:
            plan_date: Date in YYYY-MM-DD format
            approved: True to approve, False to reject
            feedback: Optional feedback message
            
        Returns:
            Approval confirmation
        """
        payload = {
            'approved': approved
        }
        if feedback:
            payload['feedback'] = feedback
        
        response = self.session.post(
            f'{self.base_url}/api/v1/plan/{plan_date}/approve',
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def decompose_task(
        self,
        task_id: str,
        target_days: int = 1
    ) -> Dict[str, Any]:
        """
        Decompose a long-running task into subtasks.
        
        Args:
            task_id: JIRA task ID (e.g., PROJ-123)
            target_days: Target duration for each subtask
            
        Returns:
            Decomposition proposal with subtasks
        """
        payload = {
            'target_days': target_days
        }
        
        response = self.session.post(
            f'{self.base_url}/api/v1/task/{task_id}/decompose',
            json=payload
        )
        response.raise_for_status()
        return response.json()


def main():
    """Demo usage of the API client."""
    if len(sys.argv) < 3:
        print("Usage: python examples/api_client.py <API_URL> <JWT_TOKEN>")
        print("\nExample:")
        print("  python examples/api_client.py \\")
        print("    https://xxx.execute-api.eu-south-2.amazonaws.com/dev \\")
        print("    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        sys.exit(1)
    
    api_url = sys.argv[1]
    token = sys.argv[2]
    
    print("🚀 TrIAge API Client Demo")
    print(f"API URL: {api_url}")
    print()
    
    # Initialize client
    client = TriageAPIClient(api_url, token)
    
    # 1. Health check
    print("1️⃣ Health Check")
    try:
        health = client.health_check()
        print(f"✅ Status: {health['status']}")
        print(f"   Service: {health['service']}")
        print(f"   Version: {health['version']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # 2. Generate plan
    print("2️⃣ Generate Daily Plan")
    try:
        today = date.today().isoformat()
        plan = client.generate_plan(plan_date=today, closure_rate=0.67)
        
        if plan['success']:
            print(f"✅ Plan generated for {plan['date']}")
            print(f"   Priorities: {len(plan['plan']['priorities'])}")
            
            # Show priorities
            for i, priority in enumerate(plan['plan']['priorities'], 1):
                print(f"   {i}. [{priority['key']}] {priority['summary']}")
                print(f"      Effort: {priority['effort_hours']}h | Priority: {priority['priority']}")
            
            # Show admin block
            if plan['plan']['admin_block']:
                admin = plan['plan']['admin_block']
                print(f"\n   Admin Block ({admin['time_start']}-{admin['time_end']}):")
                for task in admin['tasks']:
                    print(f"   - [{task['key']}] {task['summary']}")
            
            print(f"\n   Other tasks: {plan['plan']['other_tasks_count']}")
        else:
            print(f"❌ Error: {plan.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # 3. Get plan
    print("3️⃣ Get Existing Plan")
    try:
        today = date.today().isoformat()
        plan = client.get_plan(today)
        print(f"✅ Retrieved plan for {today}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    # 4. Approve plan
    print("4️⃣ Approve Plan")
    try:
        today = date.today().isoformat()
        result = client.approve_plan(
            plan_date=today,
            approved=True,
            feedback="Looks great!"
        )
        print(f"✅ Plan approved: {result['message']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()
    
    print("✅ Demo complete!")


if __name__ == '__main__':
    main()
