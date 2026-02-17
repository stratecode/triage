# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Test script for Docker local stack.
Validates that all endpoints work correctly.
"""

import sys
import httpx
from datetime import date, timedelta
from typing import Optional

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def print_success(msg: str):
    print(f"{GREEN}✓ {msg}{NC}")

def print_error(msg: str):
    print(f"{RED}✗ {msg}{NC}")

def print_info(msg: str):
    print(f"{BLUE}ℹ {msg}{NC}")

def print_warning(msg: str):
    print(f"{YELLOW}⚠ {msg}{NC}")

class LocalStackTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.client = httpx.Client(timeout=30.0)
    
    def test_health(self) -> bool:
        """Test health check endpoint."""
        print_info("Testing health check...")
        try:
            response = self.client.get(f"{self.base_url}/api/v1/health")
            if response.status_code == 200:
                data = response.json()
                print_success(f"Health check passed: {data.get('status')}")
                return True
            else:
                print_error(f"Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Health check error: {e}")
            return False
    
    def generate_token(self, user_id: str = "admin", expiry_days: int = 1) -> bool:
        """Generate JWT token."""
        print_info("Generating JWT token...")
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/auth/token",
                params={"user_id": user_id, "expiry_days": expiry_days}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                print_success(f"Token generated for user: {user_id}")
                print_info(f"Token: {self.token[:20]}...")
                return True
            else:
                print_error(f"Token generation failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Token generation error: {e}")
            return False
    
    def test_generate_plan(self) -> bool:
        """Test plan generation."""
        print_info("Testing plan generation...")
        if not self.token:
            print_error("No token available")
            return False
        
        try:
            today = date.today().isoformat()
            response = self.client.post(
                f"{self.base_url}/api/v1/plan",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"date": today}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    plan = data.get('plan', {})
                    priorities = plan.get('priorities', [])
                    print_success(f"Plan generated with {len(priorities)} priorities")
                    
                    for i, p in enumerate(priorities, 1):
                        print_info(f"  {i}. {p.get('key')}: {p.get('summary')}")
                    
                    return True
                else:
                    print_error(f"Plan generation failed: {data.get('error')}")
                    return False
            else:
                print_error(f"Plan generation failed: {response.status_code}")
                print_error(f"Response: {response.text}")
                return False
        except Exception as e:
            print_error(f"Plan generation error: {e}")
            return False
    
    def test_get_plan(self) -> bool:
        """Test getting a plan."""
        print_info("Testing get plan...")
        if not self.token:
            print_error("No token available")
            return False
        
        try:
            today = date.today().isoformat()
            response = self.client.get(
                f"{self.base_url}/api/v1/plan/{today}",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print_success("Plan retrieved successfully")
                    return True
                else:
                    print_error(f"Get plan failed: {data.get('error')}")
                    return False
            else:
                print_error(f"Get plan failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Get plan error: {e}")
            return False
    
    def test_approve_plan(self) -> bool:
        """Test plan approval."""
        print_info("Testing plan approval...")
        if not self.token:
            print_error("No token available")
            return False
        
        try:
            today = date.today().isoformat()
            response = self.client.post(
                f"{self.base_url}/api/v1/plan/{today}/approve",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"approved": True, "feedback": "Test approval"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print_success("Plan approved successfully")
                    return True
                else:
                    print_error(f"Approve plan failed: {data.get('error')}")
                    return False
            else:
                print_error(f"Approve plan failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Approve plan error: {e}")
            return False
    
    def test_unauthorized_access(self) -> bool:
        """Test that endpoints require authentication."""
        print_info("Testing unauthorized access...")
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/plan",
                json={"date": date.today().isoformat()}
            )
            
            if response.status_code == 401:
                print_success("Unauthorized access correctly blocked")
                return True
            else:
                print_error(f"Expected 401, got {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Unauthorized access test error: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tests."""
        print("\n" + "="*60)
        print("TrIAge Local Stack Test Suite")
        print("="*60 + "\n")
        
        results = []
        
        # Test 1: Health check
        results.append(("Health Check", self.test_health()))
        print()
        
        # Test 2: Unauthorized access
        results.append(("Unauthorized Access", self.test_unauthorized_access()))
        print()
        
        # Test 3: Generate token
        results.append(("Generate Token", self.generate_token()))
        print()
        
        # Test 4: Generate plan
        results.append(("Generate Plan", self.test_generate_plan()))
        print()
        
        # Test 5: Get plan
        results.append(("Get Plan", self.test_get_plan()))
        print()
        
        # Test 6: Approve plan
        results.append(("Approve Plan", self.test_approve_plan()))
        print()
        
        # Summary
        print("="*60)
        print("Test Summary")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = f"{GREEN}PASS{NC}" if result else f"{RED}FAIL{NC}"
            print(f"{test_name:.<40} {status}")
        
        print()
        print(f"Total: {passed}/{total} tests passed")
        
        if passed == total:
            print_success("All tests passed! 🎉")
            return True
        else:
            print_error(f"{total - passed} test(s) failed")
            return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test TrIAge local stack")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    tester = LocalStackTester(base_url=args.url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
