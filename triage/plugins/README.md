# TrIAge Plugin System

The TrIAge plugin system provides a flexible, extensible architecture for integrating communication channels (Slack, WhatsApp, ChatGPT, Discord, etc.) with TrIAge Core business logic.

## Architecture Overview

The plugin system consists of three main layers:

1. **Plugin Interface** - Abstract contracts defining how channels interact with core
2. **Plugin Registry** - Manages plugin lifecycle, routing, and health monitoring
3. **Core Actions API** - Exposes TrIAge business logic to plugins

## Key Components

### Plugin Interface (`interface.py`)

Defines the abstract base class that all channel plugins must implement:

- `PluginInterface` - Abstract base class with required methods
- `PluginMessage` - Channel-agnostic message representation
- `PluginResponse` - Channel-agnostic response format
- `PluginConfig` - Plugin configuration schema
- `PluginStatus` - Health status enumeration

### Plugin Registry (`registry.py`)

Manages plugin lifecycle and coordination:

- Plugin discovery and loading
- Plugin initialization and startup
- Message routing to appropriate plugins
- Event broadcasting to subscribed plugins
- Health monitoring and error isolation

### Core Actions API (`../core/actions_api.py`)

Exposes TrIAge business logic:

- `generate_plan()` - Generate daily plans
- `approve_plan()` - Approve/reject plans
- `decompose_task()` - Break down long-running tasks
- `get_status()` - Get plan status
- `configure_settings()` - Update user preferences

### Event Bus (`../core/event_bus.py`)

Enables asynchronous core-to-plugin communication:

- Pub/sub pattern for event distribution
- Event types: `plan_generated`, `task_blocked`, `approval_timeout`
- Error isolation for handler failures
- Queue-based processing for high-volume scenarios

## Creating a Plugin

To create a new channel plugin:

1. **Create plugin directory**: `triage/plugins/{channel_name}/`

2. **Implement PluginInterface**:

```python
from triage.plugins.interface import PluginInterface, PluginMessage, PluginResponse

class MyChannelPlugin(PluginInterface):
    def get_name(self) -> str:
        return "mychannel"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["api_key"],
            "properties": {
                "api_key": {"type": "string"}
            }
        }
    
    async def initialize(self, config, core_api):
        # Initialize your channel client
        pass
    
    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        # Handle incoming messages
        # Invoke core_api methods as needed
        pass
    
    # Implement other required methods...
```

3. **Register plugin**:

```python
from triage.plugins.registry import PluginRegistry
from triage.core.actions_api import CoreActionsAPI

core_api = CoreActionsAPI(...)
registry = PluginRegistry(core_api=core_api)

config = PluginConfig(
    plugin_name="mychannel",
    plugin_version="1.0.0",
    config={"api_key": "..."}
)

await registry.load_plugin("mychannel", config)
await registry.start_all()
```

## Plugin Lifecycle

1. **Discovery** - Registry scans plugins directory
2. **Loading** - Plugin module is imported and instantiated
3. **Initialization** - Plugin receives config and core API reference
4. **Startup** - Plugin registers webhooks, opens connections
5. **Operation** - Plugin handles messages and events
6. **Shutdown** - Plugin closes connections and cleans up

## Message Flow

### Incoming Messages (User → Plugin → Core)

1. User sends message via channel (e.g., Slack)
2. Channel webhook delivers to plugin
3. Plugin converts to `PluginMessage`
4. Registry routes to appropriate plugin
5. Plugin invokes Core Actions API
6. Plugin formats response as `PluginResponse`
7. Plugin sends response back to channel

### Outgoing Events (Core → Plugin → User)

1. Core emits event to Event Bus
2. Event Bus broadcasts to subscribed plugins
3. Plugin receives event via `handle_event()`
4. Plugin formats notification for channel
5. Plugin sends notification to user

## Error Handling

The plugin system provides comprehensive error isolation:

- **Plugin Load Failure** - Logged, other plugins continue loading
- **Plugin Crash** - Caught, plugin marked unhealthy, system continues
- **Handler Error** - Isolated, generic error returned to user
- **Health Check Failure** - Plugin marked degraded/unhealthy

## Testing

Run plugin infrastructure tests:

```bash
# Unit tests
python -m pytest tests/unit/test_plugin_interface.py -v
python -m pytest tests/unit/test_plugin_registry.py -v
python -m pytest tests/unit/test_core_actions_api.py -v
python -m pytest tests/unit/test_event_bus.py -v

# Demo
python examples/demo_plugin_infrastructure.py
```

## Next Steps

The plugin infrastructure is now ready for:

1. Implementing the Slack connector plugin (Task 8)
2. Adding OAuth handlers (Task 7)
3. Creating database schema for plugin installations (Task 6)
4. Implementing event-driven notifications (Task 3)

## Reference Implementation

The Slack connector will serve as the reference implementation, demonstrating:

- OAuth 2.0 authorization flow
- Workspace installation management
- Command parsing and mapping
- Interactive components (buttons, modals)
- Event subscriptions and notifications
- Message formatting (Block Kit)

See `.kiro/specs/plugin-architecture/design.md` for detailed architecture and design decisions.
