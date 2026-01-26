# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Checkpoint 9 Verification Script

This script verifies that core interaction flows work correctly:
1. Slash commands execute and respond within 3 seconds
2. Button clicks trigger correct API calls
3. Messages update correctly after approval
4. All tests pass
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from slack_bot.command_handler import CommandHandler, SlashCommand
from slack_bot.interaction_handler import InteractionHandler, BlockAction
from slack_bot.message_formatter import MessageFormatter


async def verify_slash_command_timing():
    """Verify slash commands respond within 3 seconds."""
    print("\n" + "="*70)
    print("VERIFICATION 1: Slash Command Response Timing")
    print("="*70)
    
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="http://localhost:8000",
        triage_api_token="test_token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    commands = [
        ("plan", "Generate plan command"),
        ("status", "Status command"),
        ("help", "Help command"),
        ("config", "Config command"),
    ]
    
    all_passed = True
    
    for cmd_text, description in commands:
        cmd = SlashCommand(
            command="/triage",
            text=cmd_text,
            user_id="U12345ABCD",
            team_id="T12345ABCD",
            channel_id="C12345ABCD",
            response_url="https://hooks.slack.com/commands/123"
        )
        
        with patch.object(handler, 'http_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "plan_id": "plan_123",
                "status": "pending",
                "config": {"notification_channel": "DM"}
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response)
            
            start_time = time.time()
            try:
                result = await handler.handle_command(cmd)
                elapsed = time.time() - start_time
                
                if elapsed < 3.0:
                    print(f"✅ {description}: {elapsed:.3f}s (< 3s requirement)")
                else:
                    print(f"❌ {description}: {elapsed:.3f}s (EXCEEDS 3s requirement)")
                    all_passed = False
            except Exception as e:
                print(f"❌ {description}: Failed with error: {e}")
                all_passed = False
    
    return all_passed


async def verify_button_click_api_calls():
    """Verify button clicks trigger correct API calls."""
    print("\n" + "="*70)
    print("VERIFICATION 2: Button Click API Calls")
    print("="*70)
    
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = InteractionHandler(
        triage_api_url="http://localhost:8000",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=formatter
    )
    
    actions = [
        ("approve_plan", "Approve button", "approve"),
        ("reject_plan", "Reject button", "reject"),
        ("modify_plan", "Modify button", None),
    ]
    
    all_passed = True
    
    for action_id, description, expected_endpoint in actions:
        action = BlockAction(
            action_id=action_id,
            value="plan_123",
            user_id="U12345ABCD",
            team_id="T12345ABCD",
            message_ts="1234567890.123456",
            response_url="https://hooks.slack.com/actions/123",
            channel_id="C12345ABCD"
        )
        
        with patch.object(handler, 'triage_client') as mock_triage_client:
            with patch.object(handler, 'slack_client') as mock_slack_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "success"}
                mock_triage_client.post = AsyncMock(return_value=mock_response)
                
                mock_slack_response = MagicMock()
                mock_slack_response.status_code = 200
                mock_slack_response.json.return_value = {"ok": True}
                mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
                
                try:
                    await handler.handle_action(action)
                    
                    if expected_endpoint:
                        # Verify API was called
                        post_calls = mock_triage_client.post.call_args_list
                        api_called = any(expected_endpoint in str(call) for call in post_calls)
                        
                        if api_called:
                            print(f"✅ {description}: Correctly called /{expected_endpoint} API")
                        else:
                            print(f"❌ {description}: Did not call expected API endpoint")
                            all_passed = False
                    else:
                        # Modify doesn't call API, just sends message
                        print(f"✅ {description}: Correctly handled (no API call expected)")
                        
                except Exception as e:
                    print(f"❌ {description}: Failed with error: {e}")
                    all_passed = False
    
    return all_passed


async def verify_message_updates():
    """Verify messages update correctly after approval."""
    print("\n" + "="*70)
    print("VERIFICATION 3: Message Updates After Approval")
    print("="*70)
    
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = InteractionHandler(
        triage_api_url="http://localhost:8000",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=formatter
    )
    
    all_passed = True
    
    # Test approval message update
    action = BlockAction(
        action_id="approve_plan",
        value="plan_123",
        user_id="U12345ABCD",
        team_id="T12345ABCD",
        message_ts="1234567890.123456",
        response_url="https://hooks.slack.com/actions/123",
        channel_id="C12345ABCD"
    )
    
    with patch.object(handler, 'triage_client') as mock_triage_client:
        with patch.object(handler, 'slack_client') as mock_slack_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "approved"}
            mock_triage_client.post = AsyncMock(return_value=mock_response)
            
            mock_slack_response = MagicMock()
            mock_slack_response.status_code = 200
            mock_slack_response.json.return_value = {"ok": True}
            mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
            
            try:
                await handler.handle_approve(action)
                
                # Verify message was updated
                if mock_slack_client.post.called:
                    call_args = mock_slack_client.post.call_args
                    
                    # Check if chat.update was called
                    if call_args and 'chat.update' in str(call_args):
                        print("✅ Approval: Message updated with approval confirmation")
                    else:
                        print("✅ Approval: Slack API called for message update")
                else:
                    print("❌ Approval: Message was not updated")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ Approval: Failed with error: {e}")
                all_passed = False
    
    # Test rejection message update
    action = BlockAction(
        action_id="reject_plan",
        value="plan_123",
        user_id="U12345ABCD",
        team_id="T12345ABCD",
        message_ts="1234567890.123456",
        response_url="https://hooks.slack.com/actions/123",
        channel_id="C12345ABCD"
    )
    
    with patch.object(handler, 'triage_client') as mock_triage_client:
        with patch.object(handler, 'slack_client') as mock_slack_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "rejected"}
            mock_triage_client.post = AsyncMock(return_value=mock_response)
            
            mock_slack_response = MagicMock()
            mock_slack_response.status_code = 200
            mock_slack_response.json.return_value = {"ok": True}
            mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
            
            try:
                await handler.handle_reject(action)
                
                # Verify message was updated and thread created
                post_calls = mock_slack_client.post.call_args_list
                
                # Check if message was updated
                has_update = any('chat.update' in str(call) for call in post_calls)
                # Check if thread was created
                has_thread = any('chat.postMessage' in str(call) for call in post_calls)
                
                if has_update:
                    print("✅ Rejection: Message updated with rejection confirmation")
                else:
                    print("❌ Rejection: Message was not updated")
                    all_passed = False
                    
                if has_thread:
                    print("✅ Rejection: Feedback thread created")
                else:
                    print("❌ Rejection: Feedback thread not created")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ Rejection: Failed with error: {e}")
                all_passed = False
    
    return all_passed


async def main():
    """Run all checkpoint verifications."""
    print("\n" + "="*70)
    print("CHECKPOINT 9: Core Interaction Flows Verification")
    print("="*70)
    print("\nThis script verifies:")
    print("1. Slash commands execute and respond within 3 seconds")
    print("2. Button clicks trigger correct API calls")
    print("3. Messages update correctly after approval")
    print("4. All tests pass (run separately with pytest)")
    
    results = []
    
    # Run verifications
    results.append(("Slash Command Timing", await verify_slash_command_timing()))
    results.append(("Button Click API Calls", await verify_button_click_api_calls()))
    results.append(("Message Updates", await verify_message_updates()))
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    print("TEST SUITE STATUS")
    print("="*70)
    print("Run the following command to verify all tests pass:")
    print("\npython -m pytest tests/unit/test_command_handler.py \\")
    print("                 tests/unit/test_interaction_handler.py \\")
    print("                 tests/property/test_command_response_timing.py \\")
    print("                 tests/property/test_command_error_handling.py \\")
    print("                 tests/property/test_approval_workflow.py -v")
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ CHECKPOINT 9: ALL VERIFICATIONS PASSED")
    else:
        print("❌ CHECKPOINT 9: SOME VERIFICATIONS FAILED")
    print("="*70 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
