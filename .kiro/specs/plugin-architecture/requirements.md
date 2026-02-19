# Requirements Document

## Introduction

TrIAge currently has a monolithic Slack bot module that tightly couples the communication channel with the core business logic. This creates maintenance challenges and prevents integration with other communication platforms. This feature transforms TrIAge into a plugin-based architecture where different channels (Slack, WhatsApp, ChatGPT, Discord, Teams, etc.) can integrate with the core system through well-defined interface contracts.

The architecture prioritizes extensibility and simplicity for future integrations. The plugin interface must be designed so that adding a new channel connector (like WhatsApp or ChatGPT) requires minimal effort and follows a clear, repeatable pattern. The first plugin implementation will be a Slack connector that serves as the reference implementation, demonstrating OAuth authorization, workspace installation, and command mapping. This reference implementation will guide future connector development and validate that the interface contracts are sufficient and intuitive.

## Glossary

- **TrIAge_Core**: The core business logic system that handles task classification, plan generation, approval workflows, and JIRA integration
- **Plugin**: A self-contained module that implements the plugin interface to integrate a communication channel with TrIAge_Core
- **Plugin_Interface**: The contract that all plugins must implement to interact with TrIAge_Core
- **Slack_Connector**: The first plugin implementation that integrates Slack with TrIAge_Core
- **Channel**: A communication platform (Slack, Discord, Teams, etc.) that users interact with
- **Core_Action**: A business operation provided by TrIAge_Core (generate plan, approve, decompose tasks, etc.)
- **Plugin_Registry**: The system component that manages plugin lifecycle and routing
- **OAuth_Flow**: The authorization process for installing the Slack app in workspaces
- **Workspace**: A Slack workspace where the TrIAge app is installed
- **Command_Mapping**: The translation layer between channel-specific commands and Core_Actions

## Requirements

### Requirement 1: Plugin Interface Definition

**User Story:** As a TrIAge architect, I want a well-defined plugin interface with clear contracts, so that new communication channels (WhatsApp, ChatGPT, etc.) can be integrated easily without modifying core logic.

#### Acceptance Criteria

1. THE Plugin_Interface SHALL be defined as an abstract base class or protocol with explicit method signatures
2. THE Plugin_Interface SHALL define methods for initializing plugins with configuration
3. THE Plugin_Interface SHALL define methods for handling incoming messages from channels
4. THE Plugin_Interface SHALL define methods for sending responses back to channels
5. THE Plugin_Interface SHALL define methods for plugin lifecycle management (start, stop, health check)
6. THE Plugin_Interface SHALL define methods for registering command handlers
7. THE Plugin_Interface SHALL provide access to all Core_Actions through a standardized API
8. THE Plugin_Interface SHALL use channel-agnostic data structures for messages and events
9. WHEN a plugin is initialized, THE Plugin_Registry SHALL validate that it implements all required interface methods
10. THE Plugin_Interface SHALL be documented with clear contracts specifying input/output types and expected behaviors
11. THE Plugin_Interface SHALL minimize channel-specific assumptions to maximize reusability

### Requirement 2: Core Actions Exposure

**User Story:** As a plugin developer, I want access to all TrIAge core actions through a clean API, so that I can invoke business logic from any channel.

#### Acceptance Criteria

1. THE TrIAge_Core SHALL expose a generate_plan action that accepts user context and returns a daily plan
2. THE TrIAge_Core SHALL expose an approve_plan action that accepts approval decisions and updates plan status
3. THE TrIAge_Core SHALL expose a reject_plan action that accepts rejection feedback and triggers re-planning
4. THE TrIAge_Core SHALL expose a decompose_task action that breaks long-running tasks into daily-closable subtasks
5. THE TrIAge_Core SHALL expose a get_status action that returns current plan status and task progress
6. THE TrIAge_Core SHALL expose a configure_settings action that updates user preferences and notification settings
7. WHEN a Core_Action is invoked, THE TrIAge_Core SHALL validate input parameters and return structured results
8. WHEN a Core_Action fails, THE TrIAge_Core SHALL return error information with actionable messages

### Requirement 3: Plugin Registry

**User Story:** As a TrIAge system administrator, I want a plugin registry that manages plugin lifecycle, so that plugins can be loaded, configured, and monitored centrally.

#### Acceptance Criteria

1. THE Plugin_Registry SHALL discover and load plugins from a configured plugins directory
2. THE Plugin_Registry SHALL validate plugin implementations against the Plugin_Interface
3. THE Plugin_Registry SHALL initialize plugins with their specific configuration
4. THE Plugin_Registry SHALL route incoming events to the appropriate plugin based on channel identifier
5. THE Plugin_Registry SHALL provide health check endpoints for monitoring plugin status
6. WHEN a plugin fails to load, THE Plugin_Registry SHALL log the error and continue loading other plugins
7. WHEN a plugin crashes during operation, THE Plugin_Registry SHALL isolate the failure and prevent system-wide impact

### Requirement 4: Slack Bot Module Removal

**User Story:** As a TrIAge maintainer, I want the monolithic slack_bot module removed, so that Slack integration follows the plugin architecture pattern.

#### Acceptance Criteria

1. THE System SHALL remove the existing slack_bot module from the codebase
2. THE System SHALL migrate all Slack-specific functionality to the Slack_Connector plugin
3. THE System SHALL preserve all existing Slack bot capabilities in the new plugin
4. WHEN the migration is complete, THE System SHALL have no direct Slack dependencies in TrIAge_Core
5. WHEN the migration is complete, THE System SHALL pass all existing integration tests with the new architecture

### Requirement 5: Slack Connector Plugin Implementation

**User Story:** As a TrIAge user, I want to interact with TrIAge through Slack using the new plugin architecture, so that I can continue using familiar workflows.

#### Acceptance Criteria

1. THE Slack_Connector SHALL implement the Plugin_Interface
2. THE Slack_Connector SHALL handle Slack slash commands and map them to Core_Actions
3. THE Slack_Connector SHALL handle Slack interactive components (buttons, modals) for approvals
4. THE Slack_Connector SHALL send formatted messages and notifications to Slack channels
5. THE Slack_Connector SHALL handle Slack events (app mentions, direct messages)
6. WHEN a user invokes a slash command, THE Slack_Connector SHALL parse parameters and invoke the corresponding Core_Action
7. WHEN a Core_Action completes, THE Slack_Connector SHALL format the response for Slack and send it to the user

### Requirement 6: OAuth Authorization Flow

**User Story:** As a Slack workspace administrator, I want to install TrIAge using OAuth, so that the app has proper permissions and follows Slack security best practices.

#### Acceptance Criteria

1. THE Slack_Connector SHALL implement the OAuth 2.0 authorization flow for Slack apps
2. WHEN a workspace administrator initiates installation, THE Slack_Connector SHALL redirect to Slack's OAuth authorization page
3. WHEN Slack redirects back with an authorization code, THE Slack_Connector SHALL exchange it for access tokens
4. THE Slack_Connector SHALL store workspace access tokens securely in the database
5. THE Slack_Connector SHALL handle token refresh when tokens expire
6. WHEN OAuth authorization fails, THE Slack_Connector SHALL display a clear error message to the administrator
7. THE Slack_Connector SHALL request only the minimum required Slack permissions (scopes)

### Requirement 7: Workspace Installation Management

**User Story:** As a Slack workspace administrator, I want to manage TrIAge installation settings, so that I can configure the app for my workspace.

#### Acceptance Criteria

1. THE Slack_Connector SHALL store installation data per workspace (team_id, access_token, bot_user_id)
2. THE Slack_Connector SHALL support multiple workspace installations from a single TrIAge instance
3. WHEN a workspace uninstalls the app, THE Slack_Connector SHALL remove stored tokens and configuration
4. WHEN a user from a workspace interacts with TrIAge, THE Slack_Connector SHALL verify the workspace is properly installed
5. THE Slack_Connector SHALL isolate data between different workspaces
6. WHEN workspace installation data is missing, THE Slack_Connector SHALL prompt the administrator to reinstall

### Requirement 8: Command Mapping

**User Story:** As a TrIAge user, I want Slack commands to map intuitively to TrIAge actions, so that I can use the system without learning new syntax.

#### Acceptance Criteria

1. THE Slack_Connector SHALL map `/triage plan` to the generate_plan Core_Action
2. THE Slack_Connector SHALL map `/triage status` to the get_status Core_Action
3. THE Slack_Connector SHALL map `/triage config` to the configure_settings Core_Action
4. THE Slack_Connector SHALL map approval button clicks to the approve_plan Core_Action
5. THE Slack_Connector SHALL map rejection button clicks to the reject_plan Core_Action
6. WHEN a user invokes an unknown command, THE Slack_Connector SHALL display available commands
7. WHEN a command is missing required parameters, THE Slack_Connector SHALL display usage help

### Requirement 9: Plugin Configuration

**User Story:** As a TrIAge system administrator, I want plugins to be configurable through environment variables and config files, so that I can deploy plugins with different settings.

#### Acceptance Criteria

1. THE Plugin_Interface SHALL define a configuration schema that plugins must declare
2. THE Plugin_Registry SHALL load plugin configuration from environment variables
3. THE Plugin_Registry SHALL load plugin configuration from YAML or TOML config files
4. THE Plugin_Registry SHALL validate plugin configuration against the declared schema
5. WHEN plugin configuration is invalid, THE Plugin_Registry SHALL fail fast with clear error messages
6. THE Slack_Connector SHALL declare configuration for OAuth credentials, signing secret, and webhook URLs
7. WHERE configuration is missing, THE Plugin_Registry SHALL use sensible defaults when available

### Requirement 10: Event-Driven Plugin Communication

**User Story:** As a plugin developer, I want to receive events from TrIAge_Core asynchronously, so that I can notify users when plans are generated or tasks are blocked.

#### Acceptance Criteria

1. THE TrIAge_Core SHALL emit events when plans are generated
2. THE TrIAge_Core SHALL emit events when blocking tasks are detected
3. THE TrIAge_Core SHALL emit events when approval timeouts occur
4. THE Plugin_Interface SHALL define methods for subscribing to core events
5. WHEN a core event is emitted, THE Plugin_Registry SHALL route it to all subscribed plugins
6. THE Slack_Connector SHALL subscribe to plan generation events and send notifications to configured channels
7. THE Slack_Connector SHALL subscribe to blocking task events and send alerts to users

### Requirement 11: Error Handling and Isolation

**User Story:** As a TrIAge system administrator, I want plugin errors to be isolated, so that one failing plugin doesn't crash the entire system.

#### Acceptance Criteria

1. WHEN a plugin raises an exception during message handling, THE Plugin_Registry SHALL catch it and log the error
2. WHEN a plugin raises an exception, THE Plugin_Registry SHALL return a generic error response to the user
3. WHEN a plugin fails health checks repeatedly, THE Plugin_Registry SHALL mark it as unhealthy
4. THE Plugin_Registry SHALL continue routing to healthy plugins when one plugin is unhealthy
5. WHEN a plugin is unhealthy, THE Plugin_Registry SHALL attempt periodic recovery
6. THE Plugin_Registry SHALL expose metrics on plugin health and error rates
7. WHEN a plugin error occurs, THE System SHALL not expose internal implementation details to users

### Requirement 12: Migration Path and Backward Compatibility

**User Story:** As a TrIAge user, I want the transition to plugin architecture to be seamless, so that my existing workflows continue working without interruption.

#### Acceptance Criteria

1. THE Slack_Connector SHALL support all commands from the previous slack_bot implementation
2. THE Slack_Connector SHALL maintain the same message formats and user experience
3. THE Slack_Connector SHALL preserve existing database schemas for workspace and user data
4. WHEN the system is upgraded, THE Slack_Connector SHALL automatically migrate existing installations
5. WHEN the system is upgraded, THE Slack_Connector SHALL maintain existing OAuth tokens
6. THE System SHALL provide a migration script for transitioning from old to new architecture
7. THE System SHALL document breaking changes and migration steps in the changelog

### Requirement 13: Extensibility for Future Connectors

**User Story:** As a TrIAge architect, I want the plugin interface to be designed for easy extension to new channels like WhatsApp and ChatGPT, so that adding new connectors requires minimal effort and follows a proven pattern.

#### Acceptance Criteria

1. THE Plugin_Interface SHALL use abstract message types that can represent messages from any channel
2. THE Plugin_Interface SHALL separate channel-specific concerns (authentication, formatting) from core interaction patterns
3. THE Plugin_Interface SHALL define a standard message envelope with sender, content, and metadata fields
4. THE Plugin_Interface SHALL define a standard response format that plugins can adapt to their channel's capabilities
5. THE Slack_Connector SHALL demonstrate how to map channel-specific events to the abstract message types
6. THE Slack_Connector SHALL demonstrate how to transform abstract responses into channel-specific formats
7. WHEN designing the interface, THE System SHALL consider requirements for WhatsApp (phone numbers, media messages) and ChatGPT (conversational context, streaming)
8. THE Plugin_Interface SHALL provide extension points for channel-specific features without breaking the core contract
9. THE System SHALL document common patterns that apply across all channels (authentication, user identification, message threading)
10. THE System SHALL validate that a new connector can be implemented in under 500 lines of code for basic functionality

### Requirement 14: Plugin Documentation and Examples

**User Story:** As a future plugin developer, I want clear documentation and examples, so that I can create new channel integrations efficiently.

#### Acceptance Criteria

1. THE System SHALL provide documentation for the Plugin_Interface with all required methods
2. THE System SHALL provide a plugin development guide with step-by-step instructions
3. THE System SHALL provide the Slack_Connector source code as a reference implementation
4. THE System SHALL provide a minimal plugin template for quick starts
5. THE System SHALL document the Core_Actions API with parameters and return types
6. THE System SHALL document the event subscription mechanism with event schemas
7. THE System SHALL provide examples of common plugin patterns (authentication, message formatting, error handling)

### Requirement 14: Plugin Documentation and Examples

**User Story:** As a future plugin developer, I want clear documentation and examples, so that I can create new channel integrations (WhatsApp, ChatGPT, etc.) efficiently.

#### Acceptance Criteria

1. THE System SHALL provide documentation for the Plugin_Interface with all required methods and their contracts
2. THE System SHALL provide a plugin development guide with step-by-step instructions
3. THE System SHALL provide the Slack_Connector source code as a reference implementation
4. THE System SHALL provide a minimal plugin template for quick starts
5. THE System SHALL document the Core_Actions API with parameters and return types
6. THE System SHALL document the event subscription mechanism with event schemas
7. THE System SHALL provide examples of common plugin patterns (authentication, message formatting, error handling)
8. THE System SHALL include a comparison table showing how different channels (Slack, WhatsApp, ChatGPT) map to the interface
9. THE System SHALL document best practices for handling channel-specific features while maintaining interface compliance

### Requirement 15: AWS Infrastructure Compatibility

**User Story:** As a TrIAge system administrator, I want the plugin architecture to work seamlessly with the existing AWS infrastructure, so that deployment and operations remain unchanged.

#### Acceptance Criteria

1. THE Plugin_Registry SHALL be deployable as an AWS Lambda function
2. THE Plugin_Registry SHALL support API Gateway integration for HTTP endpoints
3. THE Slack_Connector SHALL handle Slack webhook events through API Gateway
4. THE Plugin_Interface SHALL support both synchronous (Lambda) and asynchronous (SQS/SNS) invocation patterns
5. THE Plugin_Registry SHALL store plugin configuration in AWS Systems Manager Parameter Store or Secrets Manager
6. THE Slack_Connector SHALL store OAuth tokens in the existing database infrastructure
7. WHEN deployed to AWS Lambda, THE Plugin_Registry SHALL have cold start times under 3 seconds
8. THE Plugin_Registry SHALL support the existing Docker-based local development workflow
9. THE System SHALL maintain compatibility with the existing AWS SAM or CloudFormation templates
10. THE Plugin_Registry SHALL use the same logging and monitoring infrastructure (CloudWatch)
11. WHEN a plugin needs to invoke Core_Actions, THE System SHALL support both in-process and cross-Lambda invocation patterns

### Requirement 16: Testing Infrastructure for Plugins

**User Story:** As a plugin developer, I want testing utilities for plugins, so that I can validate my implementation without deploying to production.

#### Acceptance Criteria

1. THE System SHALL provide mock implementations of TrIAge_Core for plugin testing
2. THE System SHALL provide test fixtures for common Core_Action responses
3. THE System SHALL provide utilities for simulating channel events
4. THE Slack_Connector SHALL include unit tests for command parsing and mapping
5. THE Slack_Connector SHALL include integration tests for OAuth flow
6. THE Slack_Connector SHALL include property-based tests for message formatting
7. WHEN running plugin tests, THE System SHALL not require external service dependencies
