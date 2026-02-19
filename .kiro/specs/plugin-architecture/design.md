# Design Document: Plugin Architecture

## Overview

This design transforms TrIAge from a monolithic architecture with a tightly-coupled Slack bot into a flexible plugin-based system. The core principle is to define clear interface contracts that make adding new communication channels (WhatsApp, ChatGPT, Discord, Teams) trivial and repeatable.

The architecture separates concerns into three layers:
1. **TrIAge Core**: Business logic for task classification, plan generation, and JIRA integration
2. **Plugin Interface**: Abstract contracts defining how channels interact with the core
3. **Channel Plugins**: Concrete implementations for specific platforms (Slack, WhatsApp, etc.)

This design prioritizes extensibility, AWS Lambda compatibility, and minimal coupling between components.

## Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Communication Channels"
        Slack[Slack Workspace]
        WhatsApp[WhatsApp Business]
        ChatGPT[ChatGPT Plugin]
    end
    
    subgraph "API Gateway"
        APIGW[AWS API Gateway]
    end
    
    subgraph "Plugin Layer"
        SlackPlugin[Slack Connector Plugin]
        WhatsAppPlugin[WhatsApp Connector Plugin]
        ChatGPTPlugin[ChatGPT Connector Plugin]
    end
    
    subgraph "Plugin Registry"
        Registry[Plugin Registry]
        Router[Event Router]
    end
    
    subgraph "TrIAge Core"
        CoreAPI[Core Actions API]
        PlanGen[Plan Generator]
        TaskClass[Task Classifier]
        JiraClient[JIRA Client]
        EventBus[Event Bus]
    end
    
    subgraph "External Services"
        JIRA[JIRA API]
        Secrets[AWS Secrets Manager]
        DB[(PostgreSQL)]
    end
    
    Slack -->|Webhooks| APIGW
    WhatsApp -->|Webhooks| APIGW
    ChatGPT -->|API Calls| APIGW
    
    APIGW -->|Route by channel| Registry
    Registry -->|Dispatch| SlackPlugin
    Registry -->|Dispatch| WhatsAppPlugin
    Registry -->|Dispatch| ChatGPTPlugin
    
    SlackPlugin -->|Invoke| CoreAPI
    WhatsAppPlugin -->|Invoke| CoreAPI
    ChatGPTPlugin -->|Invoke| CoreAPI
    
    CoreAPI --> PlanGen
    CoreAPI --> TaskClass
    CoreAPI --> JiraClient
    
    JiraClient --> JIRA
    Registry --> Secrets
    SlackPlugin --> DB
    
    EventBus -->|Notify| Router
    Router -->|Events| SlackPlugin
    Router -->|Events| WhatsAppPlugin
```

### Deployment Architecture (AWS Lambda)

```mermaid
graph TB
    subgraph "API Gateway"
        APIGW[API Gateway]
    end
    
    subgraph "Lambda Functions"
        PluginHandler[Plugin Handler Lambda]
        CoreActions[Core Actions Lambda]
        EventProcessor[Event Processor Lambda]
    end
    
    subgraph "Storage"
        Secrets[Secrets Manager]
        Params[Parameter Store]
        RDS[(RDS PostgreSQL)]
    end
    
    subgraph "Messaging"
        SNS[SNS Topics]
        SQS[SQS Queues]
    end
    
    APIGW -->|/plugins/*| PluginHandler
    APIGW -->|/api/v1/*| CoreActions
    
    PluginHandler -->|Load config| Params
    PluginHandler -->|Get tokens| Secrets
    PluginHandler -->|Store data| RDS
    PluginHandler -->|Invoke| CoreActions
    
    CoreActions -->|Publish events| SNS
    SNS -->|Subscribe| SQS
    SQS -->|Trigger| EventProcessor
    EventProcessor -->|Notify| PluginHandler
```

## Components and Interfaces

### 1. Plugin Interface (Abstract Base Class)

The plugin interface defines the contract that all channel connectors must implement. It uses channel-agnostic abstractions to maximize reusability.

```python
# triage/plugins/interface.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

@dataclass
class PluginMessage:
    """Channel-agnostic message representation."""
    channel_id: str  # Unique identifier for the channel (workspace_id, phone_number, etc.)
    user_id: str  # User identifier within the channel
    content: str  # Message text content
    command: Optional[str] = None  # Parsed command (e.g., "plan", "status")
    parameters: Dict[str, Any] = None  # Command parameters
    metadata: Dict[str, Any] = None  # Channel-specific metadata
    thread_id: Optional[str] = None  # For threaded conversations

@dataclass
class PluginResponse:
    """Channel-agnostic response representation."""
    content: str  # Response text (markdown supported)
    response_type: str = "message"  # message, ephemeral, modal, etc.
    attachments: List[Dict[str, Any]] = None  # Structured attachments
    actions: List[Dict[str, Any]] = None  # Interactive actions (buttons, etc.)
    metadata: Dict[str, Any] = None  # Channel-specific response data

class PluginStatus(Enum):
    """Plugin health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"

@dataclass
class PluginConfig:
    """Plugin configuration schema."""
    plugin_name: str
    plugin_version: str
    enabled: bool = True
    config: Dict[str, Any] = None  # Plugin-specific configuration

class PluginInterface(ABC):
    """Abstract base class for all TrIAge channel plugins."""
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the plugin name (e.g., 'slack', 'whatsapp')."""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """Return the plugin version."""
        pass
    
    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON schema for plugin configuration validation."""
        pass
    
    @abstractmethod
    async def initialize(self, config: PluginConfig, core_api: 'CoreActionsAPI') -> None:
        """Initialize the plugin with configuration and core API access."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the plugin (register webhooks, open connections, etc.)."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the plugin gracefully."""
        pass
    
    @abstractmethod
    async def health_check(self) -> PluginStatus:
        """Check plugin health status."""
        pass
    
    @abstractmethod
    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        """Handle incoming message from the channel."""
        pass
    
    @abstractmethod
    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        """Send a message to the channel."""
        pass
    
    @abstractmethod
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle events from TrIAge Core (plan generated, task blocked, etc.)."""
        pass
```

### 2. Core Actions API

The Core Actions API exposes all TrIAge business logic to plugins through a clean, versioned interface.

```python
# triage/core/actions_api.py

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import date

@dataclass
class CoreActionResult:
    """Standard result wrapper for core actions."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None

class CoreActionsAPI:
    """API for plugins to invoke TrIAge core business logic."""
    
    def __init__(self, jira_client, task_classifier, plan_generator):
        self.jira_client = jira_client
        self.task_classifier = task_classifier
        self.plan_generator = plan_generator
    
    async def generate_plan(
        self, 
        user_id: str, 
        plan_date: Optional[date] = None,
        closure_rate: Optional[float] = None
    ) -> CoreActionResult:
        """Generate a daily plan for the user."""
        try:
            # Implementation delegates to existing PlanGenerator
            issues = await self.jira_client.fetch_active_tasks()
            classified = [self.task_classifier.classify_task(i) for i in issues]
            plan = self.plan_generator.generate_daily_plan(closure_rate)
            
            return CoreActionResult(
                success=True,
                data={
                    'plan': plan,
                    'markdown': plan.to_markdown()
                }
            )
        except Exception as e:
            return CoreActionResult(
                success=False,
                error=str(e),
                error_code='PLAN_GENERATION_FAILED'
            )
    
    async def approve_plan(
        self,
        user_id: str,
        plan_date: date,
        approved: bool,
        feedback: Optional[str] = None
    ) -> CoreActionResult:
        """Approve or reject a plan."""
        # Implementation
        pass
    
    async def reject_plan(
        self,
        user_id: str,
        plan_date: date,
        feedback: str
    ) -> CoreActionResult:
        """Reject a plan and trigger re-planning."""
        # Implementation
        pass
    
    async def decompose_task(
        self,
        user_id: str,
        task_key: str,
        target_days: float = 1.0
    ) -> CoreActionResult:
        """Decompose a long-running task into subtasks."""
        # Implementation
        pass
    
    async def get_status(
        self,
        user_id: str,
        plan_date: Optional[date] = None
    ) -> CoreActionResult:
        """Get current plan status and task progress."""
        # Implementation
        pass
    
    async def configure_settings(
        self,
        user_id: str,
        settings: Dict[str, Any]
    ) -> CoreActionResult:
        """Update user preferences and notification settings."""
        # Implementation
        pass
```

### 3. Plugin Registry

The Plugin Registry manages plugin lifecycle, routing, and health monitoring.

```python
# triage/plugins/registry.py

from typing import Dict, List, Optional
import importlib
import logging

class PluginRegistry:
    """Manages plugin lifecycle and routing."""
    
    def __init__(self, core_api: CoreActionsAPI, event_bus: 'EventBus'):
        self.core_api = core_api
        self.event_bus = event_bus
        self.plugins: Dict[str, PluginInterface] = {}
        self.plugin_health: Dict[str, PluginStatus] = {}
        self.logger = logging.getLogger(__name__)
    
    async def discover_plugins(self, plugins_dir: str) -> List[str]:
        """Discover plugins from directory."""
        # Scan plugins directory for modules implementing PluginInterface
        pass
    
    async def load_plugin(self, plugin_name: str, config: PluginConfig) -> bool:
        """Load and initialize a plugin."""
        try:
            # Dynamically import plugin module
            module = importlib.import_module(f'triage.plugins.{plugin_name}')
            plugin_class = getattr(module, f'{plugin_name.capitalize()}Plugin')
            
            # Instantiate and initialize
            plugin = plugin_class()
            await plugin.initialize(config, self.core_api)
            
            # Validate interface implementation
            if not isinstance(plugin, PluginInterface):
                raise TypeError(f"Plugin {plugin_name} does not implement PluginInterface")
            
            self.plugins[plugin_name] = plugin
            self.plugin_health[plugin_name] = PluginStatus.HEALTHY
            
            self.logger.info(f"Loaded plugin: {plugin_name} v{plugin.get_version()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    async def start_all(self) -> None:
        """Start all loaded plugins."""
        for name, plugin in self.plugins.items():
            try:
                await plugin.start()
                self.logger.info(f"Started plugin: {name}")
            except Exception as e:
                self.logger.error(f"Failed to start plugin {name}: {e}")
                self.plugin_health[name] = PluginStatus.UNHEALTHY
    
    async def route_message(self, channel_type: str, message: PluginMessage) -> PluginResponse:
        """Route incoming message to appropriate plugin."""
        plugin = self.plugins.get(channel_type)
        
        if not plugin:
            return PluginResponse(
                content=f"Unknown channel type: {channel_type}",
                response_type="error"
            )
        
        if self.plugin_health.get(channel_type) != PluginStatus.HEALTHY:
            return PluginResponse(
                content="Service temporarily unavailable",
                response_type="error"
            )
        
        try:
            response = await plugin.handle_message(message)
            return response
        except Exception as e:
            self.logger.error(f"Plugin {channel_type} error: {e}", exc_info=True)
            self.plugin_health[channel_type] = PluginStatus.DEGRADED
            return PluginResponse(
                content="An error occurred processing your request",
                response_type="error"
            )
    
    async def broadcast_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Broadcast core event to all subscribed plugins."""
        for name, plugin in self.plugins.items():
            try:
                await plugin.handle_event(event_type, event_data)
            except Exception as e:
                self.logger.error(f"Plugin {name} failed to handle event {event_type}: {e}")
    
    async def health_check_all(self) -> Dict[str, PluginStatus]:
        """Check health of all plugins."""
        for name, plugin in self.plugins.items():
            try:
                status = await plugin.health_check()
                self.plugin_health[name] = status
            except Exception as e:
                self.logger.error(f"Health check failed for {name}: {e}")
                self.plugin_health[name] = PluginStatus.UNHEALTHY
        
        return self.plugin_health.copy()
```

### 4. Slack Connector Plugin

The Slack connector is the reference implementation demonstrating how to map channel-specific features to the plugin interface.

```python
# triage/plugins/slack/slack_plugin.py

from typing import Dict, Any, Optional
import httpx
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.signature import SignatureVerifier

class SlackPlugin(PluginInterface):
    """Slack channel connector plugin."""
    
    def __init__(self):
        self.name = "slack"
        self.version = "1.0.0"
        self.client: Optional[AsyncWebClient] = None
        self.core_api: Optional[CoreActionsAPI] = None
        self.config: Optional[PluginConfig] = None
        self.signature_verifier: Optional[SignatureVerifier] = None
    
    def get_name(self) -> str:
        return self.name
    
    def get_version(self) -> str:
        return self.version
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["client_id", "client_secret", "signing_secret"],
            "properties": {
                "client_id": {"type": "string"},
                "client_secret": {"type": "string"},
                "signing_secret": {"type": "string"},
                "bot_token": {"type": "string"},
                "app_token": {"type": "string"}
            }
        }
    
    async def initialize(self, config: PluginConfig, core_api: CoreActionsAPI) -> None:
        self.config = config
        self.core_api = core_api
        
        # Initialize Slack client
        bot_token = config.config.get('bot_token')
        if bot_token:
            self.client = AsyncWebClient(token=bot_token)
        
        # Initialize signature verifier for webhook validation
        signing_secret = config.config.get('signing_secret')
        if signing_secret:
            self.signature_verifier = SignatureVerifier(signing_secret)
    
    async def start(self) -> None:
        # Plugin is ready to receive webhooks
        pass
    
    async def stop(self) -> None:
        if self.client:
            await self.client.close()
    
    async def health_check(self) -> PluginStatus:
        if not self.client:
            return PluginStatus.UNHEALTHY
        
        try:
            response = await self.client.auth_test()
            return PluginStatus.HEALTHY if response['ok'] else PluginStatus.DEGRADED
        except Exception:
            return PluginStatus.UNHEALTHY
    
    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        """Handle incoming Slack message/command."""
        command = message.command
        
        if command == "plan":
            return await self._handle_plan_command(message)
        elif command == "status":
            return await self._handle_status_command(message)
        elif command == "config":
            return await self._handle_config_command(message)
        elif command == "approve":
            return await self._handle_approve_command(message)
        elif command == "reject":
            return await self._handle_reject_command(message)
        else:
            return PluginResponse(
                content=self._format_help_message(),
                response_type="ephemeral"
            )
    
    async def _handle_plan_command(self, message: PluginMessage) -> PluginResponse:
        """Handle /triage plan command."""
        result = await self.core_api.generate_plan(
            user_id=message.user_id,
            closure_rate=message.parameters.get('closure_rate')
        )
        
        if result.success:
            plan_markdown = result.data['markdown']
            return PluginResponse(
                content=plan_markdown,
                response_type="message",
                actions=[
                    {"type": "button", "text": "Approve", "action_id": "approve_plan"},
                    {"type": "button", "text": "Reject", "action_id": "reject_plan"}
                ]
            )
        else:
            return PluginResponse(
                content=f"Error generating plan: {result.error}",
                response_type="ephemeral"
            )
    
    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        """Send message to Slack channel."""
        try:
            blocks = self._convert_to_slack_blocks(response)
            
            await self.client.chat_postMessage(
                channel=channel_id,
                text=response.content,
                blocks=blocks
            )
            return True
        except Exception as e:
            return False
    
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle events from TrIAge Core."""
        if event_type == "plan_generated":
            await self._notify_plan_generated(event_data)
        elif event_type == "task_blocked":
            await self._notify_task_blocked(event_data)
        elif event_type == "approval_timeout":
            await self._notify_approval_timeout(event_data)
    
    def _convert_to_slack_blocks(self, response: PluginResponse) -> List[Dict]:
        """Convert PluginResponse to Slack Block Kit format."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": response.content
                }
            }
        ]
        
        # Add action buttons if present
        if response.actions:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": action['text']},
                        "action_id": action['action_id']
                    }
                    for action in response.actions
                ]
            })
        
        return blocks
```

### 5. Event Bus

The Event Bus enables asynchronous communication between TrIAge Core and plugins.

```python
# triage/core/event_bus.py

from typing import Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime
import asyncio

@dataclass
class Event:
    """Core event representation."""
    event_type: str
    event_data: Dict[str, Any]
    timestamp: datetime
    source: str = "triage_core"

EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    """Pub/sub event bus for core-to-plugin communication."""
    
    def __init__(self):
        self.subscribers: Dict[str, List[EventHandler]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        handlers = self.subscribers.get(event.event_type, [])
        
        # Execute all handlers concurrently
        tasks = [handler(event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def publish_async(self, event: Event) -> None:
        """Publish event asynchronously via queue."""
        await self.event_queue.put(event)
    
    async def process_queue(self) -> None:
        """Process events from queue (background task)."""
        while True:
            event = await self.event_queue.get()
            await self.publish(event)
            self.event_queue.task_done()
```

### 6. OAuth Handler (Slack)

Handles OAuth 2.0 flow for Slack workspace installation.

```python
# triage/plugins/slack/oauth_handler.py

from typing import Dict, Any, Optional
import httpx
from dataclasses import dataclass

@dataclass
class OAuthTokens:
    """OAuth token storage."""
    access_token: str
    bot_user_id: str
    team_id: str
    team_name: str
    scope: str
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None

class SlackOAuthHandler:
    """Handles Slack OAuth 2.0 authorization flow."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.oauth_url = "https://slack.com/oauth/v2/authorize"
        self.token_url = "https://slack.com/api/oauth.v2.access"
    
    def get_authorization_url(self, state: str, scopes: List[str]) -> str:
        """Generate OAuth authorization URL."""
        scope_string = ",".join(scopes)
        return (
            f"{self.oauth_url}?"
            f"client_id={self.client_id}&"
            f"scope={scope_string}&"
            f"redirect_uri={self.redirect_uri}&"
            f"state={state}"
        )
    
    async def exchange_code_for_token(self, code: str) -> OAuthTokens:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri
                }
            )
            
            data = response.json()
            
            if not data.get('ok'):
                raise Exception(f"OAuth error: {data.get('error')}")
            
            return OAuthTokens(
                access_token=data['access_token'],
                bot_user_id=data['bot_user_id'],
                team_id=data['team']['id'],
                team_name=data['team']['name'],
                scope=data['scope']
            )
```

## Data Models

### Plugin Configuration Storage

```python
# triage/plugins/models.py

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class PluginInstallation:
    """Represents a plugin installation (e.g., Slack workspace)."""
    id: int
    plugin_name: str  # 'slack', 'whatsapp', etc.
    channel_id: str  # workspace_id, phone_number, etc.
    access_token: str  # Encrypted
    refresh_token: Optional[str] = None
    metadata: Dict[str, Any] = None  # Plugin-specific data
    installed_at: datetime = None
    last_active: datetime = None
    is_active: bool = True
```

Database schema:

```sql
CREATE TABLE plugin_installations (
    id SERIAL PRIMARY KEY,
    plugin_name VARCHAR(50) NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    metadata JSONB,
    installed_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(plugin_name, channel_id)
);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Plugin Interface Validation

*For any* plugin implementation, when the Plugin_Registry attempts to load it, the registry should correctly identify whether it implements all required interface methods and reject invalid implementations.

**Validates: Requirements 1.9**

### Property 2: Core Actions Accessibility

*For any* valid user context and core action (generate_plan, approve_plan, reject_plan, decompose_task, get_status, configure_settings), invoking the action through the Core Actions API should return a structured result (success or error).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

### Property 3: Core Action Input Validation

*For any* core action and invalid input parameters, the TrIAge_Core should reject the request and return an error with an actionable message.

**Validates: Requirements 2.7, 2.8**

### Property 4: Plugin Configuration Initialization

*For any* valid plugin and configuration, when the Plugin_Registry initializes the plugin, the plugin should receive its complete configuration.

**Validates: Requirements 3.3**

### Property 5: Event Routing by Channel

*For any* incoming event with a channel identifier, the Plugin_Registry should route it to the correct plugin based on the channel type.

**Validates: Requirements 3.4**

### Property 6: Plugin Failure Isolation

*For any* plugin that fails to load or crashes during operation, the Plugin_Registry should isolate the failure, log the error, and continue operating other plugins without system-wide impact.

**Validates: Requirements 3.6, 3.7**

### Property 7: Command to Core Action Mapping

*For any* valid Slack slash command with parameters, the Slack_Connector should parse the command, extract parameters, and invoke the corresponding Core_Action with correct arguments.

**Validates: Requirements 5.2, 5.6**

### Property 8: Interactive Component Handling

*For any* Slack interactive component event (button click, modal submission), the Slack_Connector should map it to the appropriate Core_Action.

**Validates: Requirements 5.3**

### Property 9: Response Formatting

*For any* PluginResponse from a Core_Action, the Slack_Connector should format it into valid Slack Block Kit format and send it to the correct channel.

**Validates: Requirements 5.4, 5.7**

### Property 10: Slack Event Handling

*For any* Slack event type (app mention, direct message, etc.), the Slack_Connector should handle it and invoke appropriate Core_Actions.

**Validates: Requirements 5.5**

### Property 11: OAuth Token Storage

*For any* successful OAuth authorization, the Slack_Connector should store the access token securely (encrypted) in the database with all required metadata (team_id, bot_user_id).

**Validates: Requirements 6.4**

### Property 12: OAuth Error Handling

*For any* OAuth authorization failure, the Slack_Connector should return a clear, actionable error message to the administrator without exposing internal details.

**Validates: Requirements 6.6**

### Property 13: Workspace Installation Storage

*For any* Slack workspace installation, the Slack_Connector should store all required fields (team_id, access_token, bot_user_id) and support multiple concurrent installations.

**Validates: Requirements 7.1, 7.2**

### Property 14: Workspace Uninstall Cleanup

*For any* workspace that uninstalls the app, the Slack_Connector should remove all stored tokens and configuration data for that workspace.

**Validates: Requirements 7.3**

### Property 15: Workspace Installation Verification

*For any* incoming request from a user, the Slack_Connector should verify the workspace is properly installed before processing, and reject requests from uninstalled workspaces.

**Validates: Requirements 7.4**

### Property 16: Workspace Data Isolation

*For any* two different Slack workspaces A and B, data and operations from workspace A should never be accessible to workspace B, and vice versa.

**Validates: Requirements 7.5**

### Property 17: Unknown Command Help Display

*For any* unknown or incomplete command, the Slack_Connector should display available commands and usage help instead of failing silently.

**Validates: Requirements 8.6, 8.7**

### Property 18: Configuration Validation

*For any* plugin configuration (valid or invalid), the Plugin_Registry should validate it against the plugin's declared schema and reject invalid configurations with clear error messages.

**Validates: Requirements 9.4, 9.5**

### Property 19: Configuration Defaults

*For any* missing optional configuration value, the Plugin_Registry should use sensible defaults when available.

**Validates: Requirements 9.7**

### Property 20: Core Event Emission

*For any* core operation that completes (plan generation, blocking task detection, approval timeout), the TrIAge_Core should emit the corresponding event to the Event Bus.

**Validates: Requirements 10.1, 10.2, 10.3**

### Property 21: Event Broadcasting to Plugins

*For any* core event emitted to the Event Bus, the Plugin_Registry should route it to all subscribed plugins.

**Validates: Requirements 10.5**

### Property 22: Slack Event Notifications

*For any* core event that the Slack_Connector subscribes to (plan generated, task blocked), the connector should send appropriate notifications to configured Slack channels.

**Validates: Requirements 10.6, 10.7**

### Property 23: Plugin Exception Isolation

*For any* exception raised by a plugin during message handling, the Plugin_Registry should catch it, log the error, and return a generic error response without crashing the system or exposing internal details.

**Validates: Requirements 11.1, 11.2, 11.7**

### Property 24: Health-Based Routing

*For any* plugin that fails health checks repeatedly, the Plugin_Registry should mark it as unhealthy and continue routing requests to healthy plugins.

**Validates: Requirements 11.3, 11.4**

### Property 25: Lambda Invocation Pattern Support

*For any* plugin operation, the system should support both synchronous (direct Lambda invocation) and asynchronous (SQS/SNS) invocation patterns without changing plugin code.

**Validates: Requirements 15.4, 15.11**

## Error Handling

### Plugin Errors

1. **Plugin Load Failure**: Log error, skip plugin, continue loading others
2. **Plugin Crash**: Catch exception, mark unhealthy, isolate from other plugins
3. **Invalid Configuration**: Fail fast with clear validation errors
4. **Health Check Failure**: Mark degraded/unhealthy, attempt periodic recovery

### Core Action Errors

1. **Invalid Parameters**: Return structured error with field-level validation messages
2. **JIRA API Failure**: Return error with retry guidance
3. **Timeout**: Return timeout error with suggested actions
4. **Authorization Failure**: Return clear auth error without exposing credentials

### Channel-Specific Errors

1. **Slack API Failure**: Log error, return user-friendly message
2. **OAuth Failure**: Display clear error with reinstall instructions
3. **Webhook Validation Failure**: Reject request, log security event
4. **Rate Limiting**: Queue request or return retry-after guidance

## Testing Strategy

### Unit Tests

Unit tests focus on specific examples, edge cases, and error conditions:

- Plugin interface validation logic
- Command parsing for specific Slack commands
- OAuth token exchange flow
- Configuration schema validation
- Event routing logic
- Error message formatting
- Workspace data isolation checks

### Property-Based Tests

Property tests verify universal properties across all inputs (minimum 100 iterations per test):

- **Property 1**: Plugin validation with randomly generated plugin implementations
- **Property 2**: Core action invocation with random user contexts
- **Property 3**: Input validation with random invalid parameters
- **Property 6**: Plugin failure isolation with simulated crashes
- **Property 7**: Command parsing with random command strings
- **Property 16**: Workspace isolation with random workspace pairs
- **Property 18**: Configuration validation with random config objects
- **Property 20**: Event emission with random core operations
- **Property 23**: Exception handling with random plugin errors

Each property test must be tagged with:
```python
# Feature: plugin-architecture, Property N: <property text>
```

### Integration Tests

- End-to-end Slack OAuth flow
- Webhook event processing through API Gateway
- Multi-workspace installation and isolation
- Event propagation from core to plugins
- Lambda cold start and warm invocation
- Database token storage and retrieval
- Cross-Lambda core action invocation

### Testing Infrastructure

- Mock Slack API for testing without external dependencies
- Mock Core Actions API for plugin testing
- Test fixtures for common events and responses
- Docker Compose setup for local integration testing
- AWS SAM local testing for Lambda functions


## AWS Lambda Deployment

### Lambda Function Structure

```
lambda/
├── plugin_handler.py       # Main plugin webhook handler
├── core_actions.py         # Core actions Lambda (existing)
├── event_processor.py      # Event processing Lambda
├── triage/                 # TrIAge core package
│   ├── core/
│   │   ├── actions_api.py
│   │   └── event_bus.py
│   └── plugins/
│       ├── interface.py
│       ├── registry.py
│       ├── models.py
│       └── slack/
│           ├── slack_plugin.py
│           ├── oauth_handler.py
│           └── command_parser.py
└── requirements.txt
```

### CloudFormation Template Updates

```yaml
# Add to template.yaml

  # Plugin Handler Lambda
  PluginHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: lambda/
      Handler: plugin_handler.handler
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          PLUGIN_CONFIG_PATH: !Sub '/${Environment}/triage/plugins'
          DATABASE_SECRET_NAME: !Sub '/${Environment}/triage/database'
      Policies:
        - SecretsManagerReadWrite
        - SSMParameterReadPolicy:
            ParameterName: !Sub '${Environment}/triage/*'
        - Statement:
            - Effect: Allow
              Action:
                - lambda:InvokeFunction
              Resource: !GetAtt CoreActionsFunction.Arn
      Events:
        SlackWebhook:
          Type: Api
          Properties:
            RestApiId: !Ref TriageApi
            Path: /plugins/slack/webhook
            Method: POST
            Auth:
              Authorizer: NONE
        SlackOAuth:
          Type: Api
          Properties:
            RestApiId: !Ref TriageApi
            Path: /plugins/slack/oauth/callback
            Method: GET
            Auth:
              Authorizer: NONE
        PluginHealth:
          Type: Api
          Properties:
            RestApiId: !Ref TriageApi
            Path: /plugins/health
            Method: GET

  # Event Processor Lambda
  EventProcessorFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: lambda/
      Handler: event_processor.handler
      Timeout: 60
      Environment:
        Variables:
          PLUGIN_HANDLER_ARN: !GetAtt PluginHandlerFunction.Arn
      Policies:
        - Statement:
            - Effect: Allow
              Action:
                - lambda:InvokeFunction
              Resource: !GetAtt PluginHandlerFunction.Arn
      Events:
        EventQueue:
          Type: SQS
          Properties:
            Queue: !GetAtt CoreEventQueue.Arn
            BatchSize: 10

  # SQS Queue for Core Events
  CoreEventQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${Environment}-triage-core-events'
      VisibilityTimeout: 180
      MessageRetentionPeriod: 86400

  # SNS Topic for Core Events
  CoreEventTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub '${Environment}-triage-core-events'
      Subscription:
        - Protocol: sqs
          Endpoint: !GetAtt CoreEventQueue.Arn

  # Allow SNS to send to SQS
  CoreEventQueuePolicy:
    Type: AWS::SQS::QueuePolicy
    Properties:
      Queues:
        - !Ref CoreEventQueue
      PolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: sns.amazonaws.com
            Action: SQS:SendMessage
            Resource: !GetAtt CoreEventQueue.Arn
            Condition:
              ArnEquals:
                aws:SourceArn: !Ref CoreEventTopic
```

### Environment Variables

```bash
# Plugin Configuration
PLUGIN_CONFIG_PATH=/dev/triage/plugins
PLUGIN_SLACK_ENABLED=true
PLUGIN_SLACK_CLIENT_ID=<from-secrets>
PLUGIN_SLACK_CLIENT_SECRET=<from-secrets>
PLUGIN_SLACK_SIGNING_SECRET=<from-secrets>

# Database
DATABASE_SECRET_NAME=/dev/triage/database

# Event Bus
CORE_EVENT_TOPIC_ARN=arn:aws:sns:...
CORE_EVENT_QUEUE_URL=https://sqs...

# Lambda ARNs for cross-invocation
CORE_ACTIONS_LAMBDA_ARN=arn:aws:lambda:...
PLUGIN_HANDLER_LAMBDA_ARN=arn:aws:lambda:...
```

## Migration Strategy

### Phase 1: Create Plugin Infrastructure (No Breaking Changes)

1. Create `triage/plugins/` package structure
2. Implement `PluginInterface`, `PluginRegistry`, `CoreActionsAPI`
3. Implement `EventBus` for core-to-plugin communication
4. Add new Lambda functions (PluginHandler, EventProcessor)
5. Deploy alongside existing slack_bot module
6. Run integration tests to verify new infrastructure

### Phase 2: Implement Slack Connector Plugin

1. Create `triage/plugins/slack/` package
2. Implement `SlackPlugin` class
3. Implement `OAuthHandler` for workspace installation
4. Migrate command handlers from slack_bot to SlackPlugin
5. Migrate event handlers from slack_bot to SlackPlugin
6. Create database migration for plugin_installations table
7. Run parallel testing (old slack_bot + new SlackPlugin)

### Phase 3: Data Migration

1. Create migration script to convert existing Slack installations
2. Migrate OAuth tokens from old schema to plugin_installations table
3. Migrate workspace configurations
4. Verify data integrity
5. Run smoke tests with migrated data

### Phase 4: Cutover

1. Update API Gateway routes to point to PluginHandler
2. Update Slack app webhook URLs
3. Monitor for errors
4. Keep slack_bot code for rollback capability
5. Run full integration test suite

### Phase 5: Cleanup

1. Remove slack_bot module after 2 weeks of stable operation
2. Remove old database tables
3. Update documentation
4. Archive old code for reference

### Rollback Plan

If issues occur during cutover:
1. Revert API Gateway routes to old slack_bot handlers
2. Revert Slack webhook URLs
3. Investigate issues in staging environment
4. Fix and retry cutover

## Local Development

### Docker Compose Setup

```yaml
# docker-compose.yml additions

services:
  plugin-handler:
    build:
      context: .
      dockerfile: docker/Dockerfile.lambda
    environment:
      - PLUGIN_CONFIG_PATH=/config/plugins
      - DATABASE_URL=postgresql://triage:password@db:5432/triage
      - PLUGIN_SLACK_ENABLED=true
      - PLUGIN_SLACK_CLIENT_ID=${SLACK_CLIENT_ID}
      - PLUGIN_SLACK_CLIENT_SECRET=${SLACK_CLIENT_SECRET}
      - PLUGIN_SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET}
    ports:
      - "9001:8080"
    volumes:
      - ./config:/config
      - ./triage:/app/triage
    depends_on:
      - db
      - localstack

  event-processor:
    build:
      context: .
      dockerfile: docker/Dockerfile.lambda
    environment:
      - DATABASE_URL=postgresql://triage:password@db:5432/triage
      - AWS_ENDPOINT_URL=http://localstack:4566
      - CORE_EVENT_QUEUE_URL=http://localstack:4566/000000000000/triage-events
    depends_on:
      - db
      - localstack

  localstack:
    image: localstack/localstack:latest
    environment:
      - SERVICES=sqs,sns,secretsmanager,ssm
      - DEBUG=1
    ports:
      - "4566:4566"
    volumes:
      - ./localstack:/etc/localstack/init/ready.d
```

### Running Locally

```bash
# Start all services
docker-compose up -d

# Run plugin handler locally
export PLUGIN_CONFIG_PATH=./config/plugins
export DATABASE_URL=postgresql://triage:password@localhost:5432/triage
python lambda/plugin_handler.py

# Test Slack webhook locally (using ngrok)
ngrok http 9001
# Update Slack app webhook URL to ngrok URL

# Run tests
pytest tests/unit/plugins/
pytest tests/integration/plugins/
pytest tests/property/plugins/
```

## Security Considerations

### OAuth Token Storage

- All OAuth tokens encrypted at rest using AWS KMS
- Tokens stored in RDS with encryption enabled
- Access tokens rotated on refresh
- Tokens never logged or exposed in error messages

### Webhook Validation

- All Slack webhooks validated using signing secret
- Timestamp validation to prevent replay attacks
- Invalid signatures rejected immediately
- Rate limiting on webhook endpoints

### Workspace Isolation

- Database queries always filtered by workspace_id
- Row-level security policies in PostgreSQL
- Plugin context includes workspace_id
- Cross-workspace access attempts logged as security events

### API Authentication

- Plugin endpoints require valid Slack signature
- Core action endpoints require JWT token
- Health check endpoint public (no sensitive data)
- OAuth callback validates state parameter

## Monitoring and Observability

### CloudWatch Metrics

- Plugin load success/failure rate
- Plugin health check status
- Message processing latency
- Core action invocation counts
- Error rates by plugin and action
- OAuth flow completion rate

### CloudWatch Logs

- Structured JSON logging
- Log groups per Lambda function
- Retention: 7 days for dev, 30 days for prod
- Log sampling for high-volume events

### Alarms

- Plugin unhealthy for > 5 minutes
- Error rate > 5% for any plugin
- OAuth failure rate > 10%
- Lambda cold start > 3 seconds
- SQS queue depth > 100 messages

### Dashboards

- Plugin health overview
- Message processing throughput
- Error rates and types
- OAuth flow funnel
- Workspace installation trends

## Performance Considerations

### Lambda Cold Starts

- Keep Lambda package size < 50MB
- Use Lambda layers for dependencies
- Implement connection pooling for database
- Cache plugin configurations in memory
- Lazy load plugins on first use

### Database Optimization

- Index on (plugin_name, channel_id) for installations
- Index on (workspace_id, user_id) for user lookups
- Connection pooling with pgbouncer
- Read replicas for high-traffic queries

### Event Processing

- Batch SQS messages (up to 10)
- Parallel event processing per plugin
- Dead letter queue for failed events
- Exponential backoff for retries

### Caching

- Cache plugin configurations (5 minute TTL)
- Cache workspace installations (1 minute TTL)
- Cache Slack user info (10 minute TTL)
- Use Redis for distributed caching (future)

## Future Extensions

### Additional Plugins

Following the same pattern as Slack connector:

**WhatsApp Plugin**:
- OAuth via WhatsApp Business API
- Message handling via webhooks
- Media message support
- Phone number as channel_id

**ChatGPT Plugin**:
- API key authentication
- Conversational context management
- Streaming response support
- User ID as channel_id

**Discord Plugin**:
- OAuth via Discord
- Slash commands and interactions
- Guild/channel management
- Guild ID as channel_id

### Plugin Marketplace

- Plugin discovery and installation UI
- Plugin versioning and updates
- Community-contributed plugins
- Plugin ratings and reviews

### Advanced Features

- Plugin-to-plugin communication
- Shared plugin state management
- Plugin composition and chaining
- A/B testing framework for plugins
