# Implementation Plan: Plugin Architecture

## Overview

This implementation plan transforms TrIAge from a monolithic architecture into a plugin-based system. The approach follows a safe, incremental migration strategy that maintains backward compatibility while building the new plugin infrastructure. The Slack connector serves as the reference implementation, demonstrating how to create channel plugins that are easy to extend to WhatsApp, ChatGPT, and other platforms.

The implementation is organized into phases that allow for testing and validation at each step, with the ability to rollback if issues arise.

## Tasks

- [x] 1. Create plugin infrastructure foundation
  - Create `triage/plugins/` package structure
  - Define `PluginInterface` abstract base class with all required methods
  - Define channel-agnostic data models (`PluginMessage`, `PluginResponse`, `PluginConfig`, `PluginStatus`)
  - Implement `PluginRegistry` for plugin lifecycle management
  - Add plugin discovery and loading mechanism
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 3.1, 3.2_

- [x] 1.1 Write property test for plugin interface validation
  - **Property 1: Plugin Interface Validation**
  - **Validates: Requirements 1.9**

- [x] 2. Implement Core Actions API
  - [x] 2.1 Create `CoreActionsAPI` class in `triage/core/actions_api.py`
    - Implement `generate_plan()` method wrapping existing PlanGenerator
    - Implement `approve_plan()` method
    - Implement `reject_plan()` method
    - Implement `decompose_task()` method wrapping existing decomposition logic
    - Implement `get_status()` method
    - Implement `configure_settings()` method
    - Return `CoreActionResult` with structured success/error responses
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 2.2 Write property test for core actions accessibility
    - **Property 2: Core Actions Accessibility**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

  - [x] 2.3 Write property test for core action input validation
    - **Property 3: Core Action Input Validation**
    - **Validates: Requirements 2.7, 2.8**

- [x] 3. Implement Event Bus for core-to-plugin communication
  - Create `EventBus` class in `triage/core/event_bus.py`
  - Implement pub/sub pattern with event subscriptions
  - Implement async event queue processing
  - Add event types: `plan_generated`, `task_blocked`, `approval_timeout`
  - Integrate EventBus with PlanGenerator to emit events
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 3.1 Write property test for core event emission
  - **Property 20: Core Event Emission**
  - **Validates: Requirements 10.1, 10.2, 10.3**

- [x] 3.2 Write property test for event broadcasting
  - **Property 21: Event Broadcasting to Plugins**
  - **Validates: Requirements 10.5**

- [x] 4. Implement Plugin Registry routing and health monitoring
  - [x] 4.1 Add event routing logic to `PluginRegistry`
    - Implement `route_message()` to dispatch by channel type
    - Implement `broadcast_event()` for core events
    - Add health check tracking per plugin
    - Implement plugin failure isolation with try/catch
    - _Requirements: 3.3, 3.4, 3.6, 3.7, 11.1, 11.2, 11.3, 11.4, 11.7_

  - [x] 4.2 Write property test for plugin configuration initialization
    - **Property 4: Plugin Configuration Initialization**
    - **Validates: Requirements 3.3**

  - [x] 4.3 Write property test for event routing by channel
    - **Property 5: Event Routing by Channel**
    - **Validates: Requirements 3.4**

  - [x] 4.4 Write property test for plugin failure isolation
    - **Property 6: Plugin Failure Isolation**
    - **Validates: Requirements 3.6, 3.7**

  - [x] 4.5 Write property test for plugin exception isolation
    - **Property 23: Plugin Exception Isolation**
    - **Validates: Requirements 11.1, 11.2, 11.7**

  - [x] 4.6 Write property test for health-based routing
    - **Property 24: Health-Based Routing**
    - **Validates: Requirements 11.3, 11.4**

- [x] 5. Checkpoint - Verify plugin infrastructure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Create database schema for plugin installations
  - Create migration script for `plugin_installations` table
  - Add columns: id, plugin_name, channel_id, access_token, refresh_token, metadata, installed_at, last_active, is_active
  - Add unique constraint on (plugin_name, channel_id)
  - Implement encryption for access_token and refresh_token fields
  - Create `PluginInstallation` model in `triage/plugins/models.py`
  - _Requirements: 7.1, 7.2, 7.3, 12.3_

- [x] 7. Implement Slack OAuth handler
  - Create `SlackOAuthHandler` class in `triage/plugins/slack/oauth_handler.py`
  - Implement `get_authorization_url()` for OAuth flow initiation
  - Implement `exchange_code_for_token()` for token exchange
  - Add OAuth token storage to database with encryption
  - Add token refresh logic for expired tokens
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

- [x] 7.1 Write property test for OAuth token storage
  - **Property 11: OAuth Token Storage**
  - **Validates: Requirements 6.4**

- [x] 7.2 Write property test for OAuth error handling
  - **Property 12: OAuth Error Handling**
  - **Validates: Requirements 6.6**

- [x] 8. Implement Slack connector plugin
  - [x] 8.1 Create `SlackPlugin` class implementing `PluginInterface`
    - Implement all required interface methods (initialize, start, stop, health_check)
    - Initialize Slack SDK client with bot token
    - Implement signature verification for webhook validation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 8.2 Implement Slack command parsing and mapping
    - Create command parser for `/triage plan`, `/triage status`, `/triage config`
    - Map commands to CoreActionsAPI methods
    - Parse command parameters from Slack payload
    - Handle unknown commands with help message
    - _Requirements: 8.1, 8.2, 8.3, 8.6, 8.7_

  - [x] 8.3 Implement Slack message formatting
    - Create `_convert_to_slack_blocks()` method
    - Convert PluginResponse to Slack Block Kit format
    - Add interactive buttons for approvals
    - Format markdown content for Slack
    - _Requirements: 5.4, 5.7_

  - [x] 8.4 Implement Slack event handlers
    - Handle app mentions and direct messages
    - Handle interactive component events (button clicks)
    - Handle approval/rejection actions
    - Subscribe to core events (plan_generated, task_blocked)
    - Send notifications to Slack channels
    - _Requirements: 5.3, 5.5, 10.6, 10.7_

  - [x] 8.5 Write property test for command to core action mapping
    - **Property 7: Command to Core Action Mapping**
    - **Validates: Requirements 5.2, 5.6**

  - [x] 8.6 Write property test for interactive component handling
    - **Property 8: Interactive Component Handling**
    - **Validates: Requirements 5.3**

  - [x] 8.7 Write property test for response formatting
    - **Property 9: Response Formatting**
    - **Validates: Requirements 5.4, 5.7**

  - [x] 8.8 Write property test for Slack event handling
    - **Property 10: Slack Event Handling**
    - **Validates: Requirements 5.5**

  - [x] 8.9 Write property test for Slack event notifications
    - **Property 22: Slack Event Notifications**
    - **Validates: Requirements 10.6, 10.7**

  - [x] 8.10 Write property test for unknown command help display
    - **Property 17: Unknown Command Help Display**
    - **Validates: Requirements 8.6, 8.7**

- [x] 9. Implement workspace installation management
  - [x] 9.1 Add workspace installation storage and retrieval
    - Implement methods to store installation data in database
    - Implement workspace verification before processing requests
    - Implement uninstall cleanup logic
    - Add workspace data isolation checks
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 9.2 Write property test for workspace installation storage
    - **Property 13: Workspace Installation Storage**
    - **Validates: Requirements 7.1, 7.2**

  - [x] 9.3 Write property test for workspace uninstall cleanup
    - **Property 14: Workspace Uninstall Cleanup**
    - **Validates: Requirements 7.3**

  - [x] 9.4 Write property test for workspace installation verification
    - **Property 15: Workspace Installation Verification**
    - **Validates: Requirements 7.4**

  - [x] 9.5 Write property test for workspace data isolation
    - **Property 16: Workspace Data Isolation**
    - **Validates: Requirements 7.5**

- [x] 10. Checkpoint - Verify Slack connector
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement plugin configuration management
  - [x] 11.1 Add configuration loading from environment variables
    - Load plugin configs from env vars with `PLUGIN_<NAME>_<KEY>` pattern
    - Load plugin configs from YAML/TOML files
    - Validate configs against plugin-declared schemas using JSON Schema
    - Implement default values for optional configuration
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x] 11.2 Write property test for configuration validation
    - **Property 18: Configuration Validation**
    - **Validates: Requirements 9.4, 9.5**

  - [x] 11.3 Write property test for configuration defaults
    - **Property 19: Configuration Defaults**
    - **Validates: Requirements 9.7**

- [x] 12. Create AWS Lambda handlers
  - [x] 12.1 Create `plugin_handler.py` Lambda function
    - Implement handler for Slack webhook events
    - Implement handler for OAuth callback
    - Implement health check endpoint
    - Route requests to PluginRegistry
    - Add signature verification for Slack webhooks
    - _Requirements: 15.1, 15.2, 15.3_

  - [x] 12.2 Create `event_processor.py` Lambda function
    - Implement SQS event processing
    - Route events to plugins via PluginRegistry
    - Add error handling and dead letter queue support
    - _Requirements: 15.4, 15.11_

  - [x] 12.3 Write property test for Lambda invocation pattern support
    - **Property 25: Lambda Invocation Pattern Support**
    - **Validates: Requirements 15.4, 15.11**

- [x] 13. Update CloudFormation template
  - Add `PluginHandlerFunction` Lambda definition
  - Add `EventProcessorFunction` Lambda definition
  - Add `CoreEventQueue` SQS queue
  - Add `CoreEventTopic` SNS topic
  - Add API Gateway routes for `/plugins/slack/webhook` and `/plugins/slack/oauth/callback`
  - Add IAM policies for cross-Lambda invocation
  - Add environment variables for plugin configuration
  - _Requirements: 15.1, 15.2, 15.3, 15.5, 15.9, 15.10_

- [x] 14. Create data migration script
  - [x] 14.1 Implement migration from slack_bot to plugin architecture
    - Create script to migrate existing Slack installations
    - Migrate OAuth tokens from old schema to plugin_installations table
    - Migrate workspace configurations
    - Add data integrity verification
    - _Requirements: 12.3, 12.4, 12.5, 12.6_

- [x] 15. Update Docker Compose for local development
  - Add `plugin-handler` service
  - Add `event-processor` service
  - Add `localstack` service for SQS/SNS/Secrets Manager
  - Update environment variables for plugin configuration
  - Add volume mounts for local plugin development
  - _Requirements: 15.8_

- [x] 16. Remove slack_bot module
  - Delete `slack_bot/` directory and all files
  - Remove slack_bot imports from other modules
  - Update API Gateway routes to use new plugin handlers
  - Verify no direct Slack dependencies remain in TrIAge Core
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 17. Create plugin documentation
  - Write plugin development guide with step-by-step instructions
  - Document PluginInterface with all methods and contracts
  - Document CoreActionsAPI with parameters and return types
  - Document event subscription mechanism
  - Create minimal plugin template for quick starts
  - Add examples for WhatsApp and ChatGPT plugin patterns
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9_

- [x] 18. Final checkpoint - Integration testing
  - Run full integration test suite with new plugin architecture
  - Test OAuth flow end-to-end
  - Test multi-workspace installation and isolation
  - Test event propagation from core to Slack
  - Test Lambda deployment and cold start performance
  - Verify all existing Slack bot functionality works
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Each property test should run minimum 100 iterations
- Plugin infrastructure is built alongside existing slack_bot (no breaking changes until task 16)
- Migration strategy allows for rollback at any point before task 16
- All code must include AGPLv3 license header
- Use `uv` for package management, not pip
- All documentation and comments in English
