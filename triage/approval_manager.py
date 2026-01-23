# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Approval management for user interaction and plan validation."""

from typing import Optional

from triage.models import DailyPlan, ApprovalResult


class ApprovalManager:
    """
    Handles user interaction for approvals and feedback.
    
    MVP version supports approve/reject only with no timeouts,
    modifications, or feedback loops.
    """
    
    def present_plan(self, plan: DailyPlan) -> ApprovalResult:
        """
        Present plan to user and wait for approval.
        
        This is a simplified MVP implementation that displays the plan
        and collects a simple approve/reject response from the user.
        
        Args:
            plan: Daily plan to present
            
        Returns:
            ApprovalResult with approval status
        """
        # Display the plan in markdown format
        print("\n" + "=" * 80)
        print("DAILY PLAN FOR APPROVAL")
        print("=" * 80)
        print()
        print(plan.to_markdown())
        print("=" * 80)
        print()
        
        # Collect approval from user
        while True:
            response = input("Do you approve this plan? (yes/no): ").strip().lower()
            
            if response in ['yes', 'y']:
                return ApprovalResult(approved=True)
            elif response in ['no', 'n']:
                return ApprovalResult(approved=False)
            else:
                print("Please enter 'yes' or 'no'")
