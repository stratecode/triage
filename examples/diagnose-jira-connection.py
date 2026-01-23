#!/usr/bin/env python3
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Diagnostic script to test JIRA connection and identify issues.

This script helps diagnose connection problems with JIRA by testing:
- Environment variable loading
- Base URL format
- Authentication
- API version compatibility
"""

import os
import sys
import base64
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_env_vars():
    """Test that environment variables are loaded."""
    print("=" * 80)
    print("1. Testing Environment Variables")
    print("=" * 80)
    
    base_url = os.getenv('JIRA_BASE_URL')
    email = os.getenv('JIRA_EMAIL')
    api_token = os.getenv('JIRA_API_TOKEN')
    project = os.getenv('JIRA_PROJECT')
    
    print(f"JIRA_BASE_URL: {base_url or '❌ NOT SET'}")
    print(f"JIRA_EMAIL: {email or '❌ NOT SET'}")
    print(f"JIRA_API_TOKEN: {'✓ SET' if api_token else '❌ NOT SET'}")
    print(f"JIRA_PROJECT: {project or '(not set - will search all projects)'}")
    print()
    
    if not all([base_url, email, api_token]):
        print("❌ Missing required environment variables!")
        print("Please check your .env file.")
        return None, None, None, None
    
    print("✓ All required environment variables are set")
    if project:
        print(f"✓ Project filter: {project}")
    print()
    return base_url, email, api_token, project


def test_base_url_format(base_url):
    """Test that base URL is correctly formatted."""
    print("=" * 80)
    print("2. Testing Base URL Format")
    print("=" * 80)
    
    if not base_url:
        print("❌ Base URL not provided")
        return False
    
    print(f"Base URL: {base_url}")
    
    # Check for common issues
    issues = []
    
    if not base_url.startswith('https://'):
        issues.append("Should start with 'https://'")
    
    if base_url.endswith('/'):
        issues.append("Should not end with '/'")
    
    if '.atlassian.net' not in base_url:
        issues.append("Should contain '.atlassian.net' for Jira Cloud")
    
    if issues:
        print("⚠️  Potential issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print()
    else:
        print("✓ Base URL format looks good")
        print()
    
    return len(issues) == 0


def test_authentication(base_url, email, api_token):
    """Test authentication with JIRA."""
    print("=" * 80)
    print("3. Testing Authentication")
    print("=" * 80)
    
    # Create auth header
    auth_string = f"{email}:{api_token}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Test with /myself endpoint (lightweight)
    base_url = base_url.rstrip('/')
    
    print("Testing API v3...")
    try:
        response = requests.get(
            f"{base_url}/rest/api/3/myself",
            headers=headers,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Authentication successful!")
            print(f"  User: {data.get('displayName', 'Unknown')}")
            print(f"  Email: {data.get('emailAddress', 'Unknown')}")
            print()
            return True
        elif response.status_code == 401:
            print("❌ Authentication failed (401 Unauthorized)")
            print("  Check your email and API token")
            print()
            return False
        elif response.status_code == 403:
            print("❌ Access forbidden (403 Forbidden)")
            print("  Your credentials are valid but you don't have permission")
            print()
            return False
        elif response.status_code == 410:
            print("⚠️  API v3 returned 410 Gone")
            print("  This might indicate API v3 is not available")
            print("  Trying API v2...")
            print()
            return test_api_v2(base_url, headers)
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            print()
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Connection timed out")
        print()
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        print()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print()
        return False


def test_api_v2(base_url, headers):
    """Test with API v2 as fallback."""
    try:
        response = requests.get(
            f"{base_url}/rest/api/2/myself",
            headers=headers,
            timeout=10
        )
        
        print(f"API v2 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API v2 authentication successful!")
            print(f"  User: {data.get('displayName', 'Unknown')}")
            print(f"  Note: Your JIRA instance uses API v2")
            print()
            return True
        else:
            print(f"❌ API v2 also failed with status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            print()
            return False
    except Exception as e:
        print(f"❌ API v2 error: {e}")
        print()
        return False


def test_search_endpoint(base_url, email, api_token, project=None):
    """Test the search endpoint that the application uses."""
    print("=" * 80)
    print("4. Testing Search Endpoint")
    print("=" * 80)
    
    # Create auth header
    auth_string = f"{email}:{api_token}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    base_url = base_url.rstrip('/')
    
    # Build JQL with optional project filter
    jql_parts = ["assignee = currentUser()", "resolution = Unresolved"]
    if project:
        jql_parts.append(f"project = {project}")
    jql = " AND ".join(jql_parts)
    
    if project:
        print(f"Testing search with project filter: {project}")
    else:
        print("Testing search across all projects")
    
    print("Using API v3 (new /search/jql endpoint)...")
    try:
        response = requests.get(
            f"{base_url}/rest/api/3/search/jql",
            params={
                'jql': jql,
                'maxResults': 5,
                'fields': 'summary,status'
            },
            headers=headers,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            print(f"✓ Search successful!")
            print(f"  Found {total} unresolved tasks")
            
            if total > 0:
                print(f"  Sample tasks:")
                for issue in data.get('issues', [])[:3]:
                    print(f"    - {issue['key']}: {issue['fields']['summary'][:50]}")
            print()
            return True
        elif response.status_code == 410:
            print("⚠️  Search endpoint returned 410 Gone")
            print("  Trying API v2...")
            print()
            return test_search_v2(base_url, headers, jql)
        else:
            print(f"❌ Search failed with status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            print()
            return False
            
    except Exception as e:
        print(f"❌ Search error: {e}")
        print()
        return False


def test_search_v2(base_url, headers, jql):
    """Test search with API v2."""
    try:
        response = requests.get(
            f"{base_url}/rest/api/2/search",
            params={
                'jql': jql,
                'maxResults': 5,
                'fields': 'summary,status'
            },
            headers=headers,
            timeout=10
        )
        
        print(f"API v2 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            print(f"✓ API v2 search successful!")
            print(f"  Found {total} unresolved tasks")
            print(f"  Note: Your JIRA instance requires API v2")
            print()
            return True
        else:
            print(f"❌ API v2 search also failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            print()
            return False
    except Exception as e:
        print(f"❌ API v2 search error: {e}")
        print()
        return False


def main():
    """Run all diagnostic tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "JIRA Connection Diagnostic Tool" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Test 1: Environment variables
    base_url, email, api_token, project = test_env_vars()
    if not all([base_url, email, api_token]):
        sys.exit(1)
    
    # Test 2: Base URL format
    test_base_url_format(base_url)
    
    # Test 3: Authentication
    auth_ok = test_authentication(base_url, email, api_token)
    if not auth_ok:
        print("=" * 80)
        print("DIAGNOSIS FAILED")
        print("=" * 80)
        print("Authentication failed. Please check:")
        print("1. Your JIRA_EMAIL is correct")
        print("2. Your JIRA_API_TOKEN is valid")
        print("3. Your JIRA_BASE_URL is correct")
        print()
        sys.exit(1)
    
    # Test 4: Search endpoint
    search_ok = test_search_endpoint(base_url, email, api_token, project)
    
    # Summary
    print("=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    
    if auth_ok and search_ok:
        print("✓ All tests passed!")
        print("  Your JIRA connection is working correctly.")
        if project:
            print(f"  Project filter: {project}")
    elif auth_ok:
        print("⚠️  Authentication works but search endpoint has issues")
        print("  This might be an API version compatibility problem.")
    else:
        print("❌ Connection issues detected")
        print("  Please review the errors above.")
    
    print()


if __name__ == '__main__':
    main()
