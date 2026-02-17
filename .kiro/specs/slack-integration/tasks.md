# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Implementation Plan: Slack Integration

## Overview

This implementation plan breaks down the Slack integration into incremental, testable steps. Each task builds on previous work and focuses on delivering working functionality that can be validated early. The plan follows an MVP-first approach, implementing core features before advanced capabilities.

## Tasks

- [x] 1. Set up Slack bot project structure and dependencies
  - Create `slack_bot/` directory with proper Python package structure
  - Add `slack-sdk`, `slack-bolt`, `httpx`, `pydantic` to dependencies using uv
  - Create configuration management for environment variables
  - Set up logging infrastructure with structured JSON logging
  - Create Docker configuration for local development
  - _Requirements: 12.1, 12.2_

- [x] 2. Implement core data models for Slack integration
  - [x] 2.1 Create Slack-specific data models
    - Implement `SlackUser`, `SlackConfig`, `WebhookEvent`, `SlackMessage` models
    - Add validation using Pydantic v2
    - _Requirements: 8.1, 10.2_
  
  - [x] 2.2 Write property test for data model validation
    - **Property: For any Slack user model with valid fields, serialization then deserialization produces equivalent object**
    - **Validates: Requirements 8.1**
  
  - [x] 2.3 Create message template models
    - Implement `MessageTemplate` protocol and concrete templates
    - Add `DailyPlanTemplate`, `BlockingTaskTemplate`, `ErrorTemplate`
    - _Requirements: 2.2, 5.2, 11.3_

- [x] 3. Implement OAuth installation flow
  - [x] 3.1 Create OAuth manager component
    - Implement `OAuthManager` class with installation URL generation
    - Add OAuth callback handler for token exchange
    - Implement secure token storage with AES-256 encryption
    - _Requirements: 1.1, 1.2, 12.1_
  
  - [x] 3.2 Add token management operations
    - Implement token retrieval and revocation
    - Add token refresh logic for expired tokens
    - _Requirements: 1.5, 12.5_
  
  - [x] 3.3 Write unit tests for OAuth flow
    - Test successful installation flow
    - Test authorization denial handling
    - Test token encryption/decryption
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 3.4 Write property test for token encryption
    - **Property 27: OAuth Token Encryption**
    - **Validates: Requirements 12.1**

- [x] 4. Implement webhook handler and validation
  - [x] 4.1 Create webhook event receiver
    - Implement HTTP endpoint for Slack webhooks
    - Add signature validation using signing secret
    - Implement timestamp validation (5-minute window)
    - _Requirements: 7.3, 12.4_
  
  - [x] 4.2 Add webhook deduplication
    - Implement Redis-based event ID tracking with TTL
    - Add deduplication check before processing
    - _Requirements: 7.4_
  
  - [x] 4.3 Implement async event processing
    - Add immediate acknowledgment (< 3s) for all webhooks
    - Implement background task queue for long-running operations
    - _Requirements: 7.1, 7.2_
  
  - [x] 4.4 Write property test for webhook signature validation
    - **Property 12: Webhook Signature Validation**
    - **Validates: Requirements 7.3**
  
  - [x] 4.5 Write property test for webhook deduplication
    - **Property 13: Webhook Deduplication**
    - **Validates: Requirements 7.4**
  
  - [x] 4.6 Write property test for webhook response timing
    - **Property 11: Webhook Response Timing**
    - **Validates: Requirements 7.1, 7.2**

- [x] 5. Checkpoint - Ensure OAuth and webhook infrastructure works
  - Verify OAuth installation flow completes successfully
  - Verify webhook signature validation rejects invalid requests
  - Verify webhook deduplication prevents duplicate processing
  - Ensure all tests pass, ask the user if questions arise

- [x] 6. Implement message formatting with Block Kit
  - [x] 6.1 Create MessageFormatter class
    - Implement Block Kit structure generation
    - Add helper methods for common block types (header, section, actions)
    - _Requirements: 2.2_
  
  - [x] 6.2 Implement daily plan formatting
    - Create `format_daily_plan()` method with approval buttons
    - Add priority task section with all required fields
    - Add administrative task grouping section
    - Format JIRA keys as clickable links
    - Add urgency emoji indicators
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 9.3, 9.5_
  
  - [x] 6.3 Implement blocking task notification formatting
    - Create `format_blocking_task_alert()` method
    - Include re-planning action button
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 6.4 Add error message formatting
    - Implement `format_error_message()` with user-friendly templates
    - Add troubleshooting suggestions
    - _Requirements: 11.3_
  
  - [x] 6.5 Write property test for complete plan formatting
    - **Property 3: Complete Plan Formatting**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5**
  
  - [x] 6.6 Write property test for JIRA link formatting
    - **Property 19: JIRA Link Formatting**
    - **Validates: Requirements 9.3**
  
  - [x] 6.7 Write property test for urgency emoji mapping
    - **Property 21: Urgency Emoji Mapping**
    - **Validates: Requirements 9.5**
  
  - [x] 6.8 Write unit tests for message formatting edge cases
    - Test plan with 0 priority tasks
    - Test plan with no admin tasks
    - Test long description truncation
    - _Requirements: 9.4_

- [x] 7. Implement slash command handling
  - [x] 7.1 Create CommandHandler class
    - Implement command routing logic
    - Add command parsing and validation
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 7.2 Implement `/triage plan` command
    - Call TrIAge API to trigger plan generation
    - Handle date parameter parsing
    - Return formatted response or acknowledgment
    - _Requirements: 4.1_
  
  - [x] 7.3 Implement `/triage status` command
    - Fetch current plan status from TrIAge API
    - Format and display plan approval state
    - _Requirements: 4.2_
  
  - [x] 7.4 Implement `/triage help` command
    - Display available commands and usage
    - Include examples for each command
    - _Requirements: 4.3_
  
  - [x] 7.5 Implement `/triage config` command
    - Display current user configuration
    - Provide instructions for updating settings
    - _Requirements: 10.1_
  
  - [x] 7.6 Write property test for command response timing
    - **Property 6: Slash Command Response Timing**
    - **Validates: Requirements 4.4**
  
  - [x] 7.7 Write property test for command error handling
    - **Property 7: Command Error Handling**
    - **Validates: Requirements 4.5**
  
  - [x] 7.8 Write unit tests for each slash command
    - Test `/triage plan` with valid and invalid dates
    - Test `/triage status` with and without active plan
    - Test `/triage help` output completeness
    - Test `/triage config` display
    - _Requirements: 4.1, 4.2, 4.3, 10.1_

- [x] 8. Implement interaction handling for buttons
  - [x] 8.1 Create InteractionHandler class
    - Implement button click event routing
    - Add message update functionality
    - _Requirements: 3.2, 3.5_
  
  - [x] 8.2 Implement approve button handler
    - Call TrIAge API approval endpoint
    - Update message to show approval status
    - Disable action buttons after approval
    - _Requirements: 3.2, 3.5_
  
  - [x] 8.3 Implement reject button handler
    - Create feedback collection thread
    - Prompt user for rejection reason
    - _Requirements: 3.3, 6.1_
  
  - [x] 8.4 Implement modify button handler
    - Provide modification instructions
    - Guide user to appropriate workflow
    - _Requirements: 3.4_
  
  - [x] 8.5 Write property test for approval state transition
    - **Property 4: Approval State Transition**
    - **Validates: Requirements 3.2, 3.5**
  
  - [x] 8.6 Write property test for rejection feedback collection
    - **Property 5: Rejection Feedback Collection**
    - **Validates: Requirements 3.3, 6.1, 6.2, 6.3**
  
  - [x] 8.7 Write unit tests for button interactions
    - Test approve updates message correctly
    - Test reject creates thread
    - Test buttons disabled after action
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

- [x] 9. Checkpoint - Ensure core interaction flows work
  - Verify slash commands execute and respond within 3 seconds
  - Verify button clicks trigger correct API calls
  - Verify messages update correctly after approval
  - Ensure all tests pass, ask the user if questions arise

- [x] 10. Implement TrIAge API client for Slack bot
  - [x] 10.1 Create TrIAge API client class
    - Implement async HTTP client using httpx
    - Add bearer token authentication
    - Enforce HTTPS for all requests
    - _Requirements: 12.2_
  
  - [x] 10.2 Add plan generation endpoint integration
    - Implement `generate_plan()` method
    - Handle API errors and timeouts
    - _Requirements: 4.1_
  
  - [x] 10.3 Add approval workflow endpoints
    - Implement `approve_plan()` and `reject_plan()` methods
    - Add `submit_feedback()` method
    - _Requirements: 3.2, 3.3, 6.2_
  
  - [x] 10.4 Add user configuration endpoints
    - Implement `get_config()` and `update_config()` methods
    - Add user mapping operations
    - _Requirements: 10.2, 8.1_
  
  - [x] 10.5 Write property test for HTTPS enforcement
    - **Property 28: HTTPS Enforcement**
    - **Validates: Requirements 12.2**
  
  - [x] 10.6 Write unit tests for API client
    - Test authentication header inclusion
    - Test error handling for 401, 403, 404, 503
    - Test retry logic with exponential backoff
    - _Requirements: 11.2_

- [x] 11. Implement daily plan delivery
  - [x] 11.1 Create notification delivery service
    - Implement plan delivery to configured channel/DM
    - Add user lookup and channel resolution
    - _Requirements: 2.1_
  
  - [x] 11.2 Add TrIAge API webhook endpoint for plan notifications
    - Create `/api/v1/notifications/slack/plan` endpoint
    - Validate incoming requests from TrIAge API
    - Route to notification delivery service
    - _Requirements: 2.1_
  
  - [x] 11.3 Write property test for plan delivery routing
    - **Property 2: Plan Delivery Routing**
    - **Validates: Requirements 2.1**
  
  - [x] 11.4 Write integration test for end-to-end plan delivery
    - Test plan generation triggers Slack notification
    - Test message appears in correct channel
    - Test approval buttons are functional
    - _Requirements: 2.1, 2.5, 3.2_

- [x] 12. Implement blocking task notifications
  - [x] 12.1 Create blocking task notification handler
    - Implement notification formatting for blocking tasks
    - Add grouping logic for multiple simultaneous blocks
    - Include re-planning action button
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [x] 12.2 Add TrIAge API webhook endpoint for blocking task alerts
    - Create `/api/v1/notifications/slack/blocking-task` endpoint
    - Route to blocking task handler
    - _Requirements: 5.1_
  
  - [x] 12.3 Implement blocking task resolution notifications
    - Add follow-up notification when blocker resolved
    - _Requirements: 5.5_
  
  - [x] 12.4 Write property test for complete blocking task notifications
    - **Property 8: Complete Blocking Task Notifications**
    - **Validates: Requirements 5.1, 5.2, 5.3**
  
  - [x] 12.5 Write property test for blocking task grouping
    - **Property 9: Blocking Task Grouping**
    - **Validates: Requirements 5.4**
  
  - [x] 12.6 Write property test for resolution notifications
    - **Property 10: Blocking Task Resolution Notifications**
    - **Validates: Requirements 5.5**

- [x] 13. Implement user configuration management
  - [x] 13.1 Create user configuration storage
    - Implement database schema for SlackConfig
    - Add CRUD operations for user preferences
    - _Requirements: 10.2_
  
  - [x] 13.2 Add configuration update handlers
    - Implement notification channel selection
    - Add delivery time configuration
    - Add notification enable/disable toggle
    - _Requirements: 10.3, 10.4, 10.5_
  
  - [x] 13.3 Implement notification filtering based on preferences
    - Check user preferences before sending proactive notifications
    - Always allow slash command responses
    - _Requirements: 10.5_
  
  - [x] 13.4 Write property test for configuration persistence
    - **Property 22: Configuration Persistence**
    - **Validates: Requirements 10.2**
  
  - [x] 13.5 Write property test for notification disable behavior
    - **Property 23: Notification Disable Behavior**
    - **Validates: Requirements 10.5**

- [x] 14. Implement multi-user support and data isolation
  - [x] 14.1 Add user identification middleware
    - Extract Slack user ID from all events
    - Map Slack user to TrIAge user
    - _Requirements: 8.1_
  
  - [x] 14.2 Implement user mapping storage
    - Create database schema for SlackUser mappings
    - Add user registration flow for new users
    - _Requirements: 8.1_
  
  - [x] 14.3 Add data isolation checks
    - Verify all queries filter by user ID
    - Add authorization checks for cross-user access
    - _Requirements: 8.2, 8.5_
  
  - [x] 14.4 Write property test for user identification consistency
    - **Property 15: User Identification Consistency**
    - **Validates: Requirements 8.1**
  
  - [x] 14.5 Write property test for multi-user data isolation
    - **Property 16: Multi-User Data Isolation**
    - **Validates: Requirements 8.2, 8.5**
  
  - [x] 14.6 Write property test for user-specific JIRA account usage
    - **Property 17: User-Specific JIRA Account Usage**
    - **Validates: Requirements 8.4**

- [x] 15. Checkpoint - Ensure multi-user functionality works
  - Verify multiple users can use bot independently
  - Verify user data is properly isolated
  - Verify each user's JIRA credentials are used correctly
  - Ensure all tests pass, ask the user if questions arise

- [x] 16. Implement error handling and retry logic
  - [x] 16.1 Add Slack API retry mechanism
    - Implement exponential backoff with jitter
    - Retry up to 3 times for retryable errors
    - _Requirements: 11.2_
  
  - [x] 16.2 Implement error message templates
    - Create user-friendly error messages for common failures
    - Add troubleshooting suggestions
    - _Requirements: 11.3_
  
  - [x] 16.3 Add comprehensive error logging
    - Log all errors with context and stack traces
    - Implement structured logging for debugging
    - _Requirements: 11.5_
  
  - [x] 16.4 Implement graceful degradation
    - Ensure Slack failures don't block TrIAge core functionality
    - Add retry queue for failed deliveries
    - _Requirements: 11.1_
  
  - [x] 16.5 Write property test for Slack API retry behavior
    - **Property 24: Slack API Retry Behavior**
    - **Validates: Requirements 11.2**
  
  - [x] 16.6 Write property test for action failure explanation
    - **Property 25: Action Failure Explanation**
    - **Validates: Requirements 11.3**
  
  - [x] 16.7 Write property test for error logging completeness
    - **Property 26: Error Logging Completeness**
    - **Validates: Requirements 11.5**
  
  - [x] 16.8 Write unit tests for error scenarios
    - Test API unavailable handling
    - Test rate limit handling
    - Test invalid token handling
    - _Requirements: 11.1, 11.4_

- [x] 17. Implement security features
  - [x] 17.1 Add credential redaction in logs
    - Implement log sanitization for sensitive data
    - Ensure JIRA credentials never appear in logs or messages
    - _Requirements: 12.3_
  
  - [x] 17.2 Implement workspace uninstall handler
    - Add OAuth revocation endpoint
    - Delete all tokens and user data on uninstall
    - _Requirements: 12.5_
  
  - [x] 17.3 Write property test for credential redaction
    - **Property 29: Credential Redaction**
    - **Validates: Requirements 12.3**
  
  - [x] 17.4 Write property test for webhook signature verification
    - **Property 30: Webhook Signature Verification**
    - **Validates: Requirements 12.4**
  
  - [x] 17.5 Write property test for uninstall data deletion
    - **Property 31: Uninstall Data Deletion**
    - **Validates: Requirements 12.5**
  
  - [x] 17.6 Write unit tests for security features
    - Test signature validation with invalid signatures
    - Test token encryption/decryption
    - Test data deletion on uninstall
    - _Requirements: 12.1, 12.4, 12.5_

- [x] 18. Implement remaining message formatting properties
  - [x] 18.1 Write property test for effort estimate formatting
    - **Property 18: Effort Estimate Formatting**
    - **Validates: Requirements 9.2**
  
  - [x] 18.2 Write property test for long description truncation
    - **Property 20: Long Description Truncation**
    - **Validates: Requirements 9.4**

- [x] 19. Implement webhook processing error handling property
  - [x] 19.1 Write property test for webhook processing error handling
    - **Property 14: Webhook Processing Error Handling**
    - **Validates: Requirements 7.5**

- [x] 20. Add Docker and deployment configuration
  - [x] 20.1 Create Dockerfile for Slack bot service
    - Use multi-stage build for optimization
    - Include all dependencies
    - _Requirements: All_
  
  - [x] 20.2 Create docker-compose.yml for local development
    - Include Slack bot, Redis, PostgreSQL
    - Add environment variable configuration
    - _Requirements: All_
  
  - [x] 20.3 Add deployment documentation
    - Document environment variables
    - Add setup instructions for local development
    - Include production deployment guide
    - _Requirements: All_

- [-] 21. Integration testing and end-to-end validation
  - [x] 21.1 Write integration test for complete OAuth flow
    - Test installation, token storage, and retrieval
    - _Requirements: 1.1, 1.2_
  
  - [x] 21.2 Write integration test for complete approval workflow
    - Test plan delivery, button click, API call, message update
    - _Requirements: 2.1, 3.2, 3.5_
  
  - [x] 21.3 Write integration test for slash command execution
    - Test command receipt, API call, response delivery
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 21.4 Write integration test for multi-user scenario
    - Test concurrent users with data isolation
    - _Requirements: 8.1, 8.2, 8.5_
  
  - [x] 21.5 Write integration test for error recovery
    - Test retry logic and graceful degradation
    - _Requirements: 11.2, 11.3_

- [x] 22. Final checkpoint - Complete system validation
  - Run all unit tests and verify > 90% coverage
  - Run all property tests (100+ iterations each)
  - Run all integration tests
  - Verify all 31 correctness properties are implemented
  - Test complete workflows end-to-end
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- All code must include the AGPLv3 license header
- Use `uv` for Python package management
- All API communication must use HTTPS
- Token storage must use AES-256 encryption
