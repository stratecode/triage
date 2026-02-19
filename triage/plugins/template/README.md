# Plugin Template
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

## Overview

This is a minimal plugin template for TrIAge. Use it as a starting point to create new channel integration plugins.

## Quick Start

1. **Copy the template:**
   ```bash
   cp -r triage/plugins/template triage/plugins/yourplugin
   ```

2. **Rename the plugin class:**
   - Open `plugin.py`
   - Rename `TemplatePlugin` to `YourPlugin`
   - Update `self.name = "yourplugin"`

3. **Define configuration schema:**
   - Update `get_config_schema()` with your required configuration fields

4. **Implement initialization:**
   - Add your API client initialization in `initialize()`
   - Add connection setup in `start()`
   - Add cleanup in `stop()`

5. **Implement message handling:**
   - Update `handle_message()` to parse your platform's messages
   - Add command handlers as needed
   - Update `send_message()` to format and send responses

6. **Implement event handling:**
   - Update event handlers to send notifications via your platform

7. **Register your plugin:**
   - Add to `triage/plugins/__init__.py`:
     ```python
     from .yourplugin.plugin import YourPlugin
     
     AVAILABLE_PLUGINS = {
         "slack": SlackPlugin,
         "yourplugin": YourPlugin,
     }
     ```

8. **Add configuration:**
   - Create `config/plugins/yourplugin.yaml`
   - Add environment variables to `.env`

9. **Write tests:**
   - Create `tests/unit/plugins/test_yourplugin.py`
   - Create `tests/property/test_yourplugin_properties.py`

10. **Update CloudFormation:**
    - Add plugin configuration to `template.yaml`

## What's Included

The template includes:

- ✅ All required interface methods
- ✅ Basic error handling
- ✅ Logging setup
- ✅ Command routing pattern
- ✅ Event handling pattern
- ✅ Core API integration examples
- ✅ TODO comments for customization points

## What You Need to Implement

- [ ] Configuration schema
- [ ] API client initialization
- [ ] Message parsing (platform-specific)
- [ ] Response formatting (platform-specific)
- [ ] Authentication/authorization
- [ ] Webhook verification (if applicable)
- [ ] Health check logic
- [ ] Tests

## Example Plugins

See these plugins for reference implementations:

- **Slack Plugin**: `triage/plugins/slack/` - OAuth, webhooks, Block Kit formatting
- **WhatsApp Example**: `docs/PLUGIN_EXAMPLE_WHATSAPP.md` - Phone numbers, media messages
- **ChatGPT Example**: `docs/PLUGIN_EXAMPLE_CHATGPT.md` - Function calling, context management

## Documentation

- [Plugin Development Guide](../../../docs/PLUGIN_DEVELOPMENT_GUIDE.md)
- [Plugin Interface Reference](../../../docs/PLUGIN_INTERFACE_REFERENCE.md)
- [Core Actions API Reference](../../../docs/CORE_ACTIONS_API_REFERENCE.md)
- [Event Subscription Guide](../../../docs/EVENT_SUBSCRIPTION_GUIDE.md)

## Testing Your Plugin

```bash
# Run unit tests
pytest tests/unit/plugins/test_yourplugin.py

# Run property tests
pytest tests/property/test_yourplugin_properties.py

# Run integration tests
pytest tests/integration/test_yourplugin_integration.py

# Test locally with Docker
docker-compose up -d
```

## Common Patterns

### Command Parsing

```python
def _parse_command(self, text: str) -> tuple[str, Dict[str, Any]]:
    """Parse command from message text."""
    parts = text.strip().split()
    command = parts[0].lstrip('/')
    params = {}
    
    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            params[key] = value
    
    return command, params
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def _send_with_retry(self, data):
    return await self.client.post("/endpoint", json=data)
```

### Rate Limiting

```python
from asyncio import Semaphore

class YourPlugin(PluginInterface):
    def __init__(self):
        self.rate_limiter = Semaphore(10)  # Max 10 concurrent
    
    async def send_message(self, channel_id, user_id, response):
        async with self.rate_limiter:
            # Send message
            pass
```

## Need Help?

- Check the [Plugin Development Guide](../../../docs/PLUGIN_DEVELOPMENT_GUIDE.md)
- Review existing plugin implementations
- Open an issue on GitHub
