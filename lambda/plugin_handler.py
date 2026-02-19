# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Handler Lambda Function

AWS Lambda handler for plugin webhook events and OAuth callbacks.
Routes requests to the Plugin Registry and handles:
- Slack webhook events
- OAuth authorization callbacks
- Health check endpoints
- Signature verification for webhooks

Validates: Requirements 15.1, 15.2, 15.3
"""

import json
import os
import sys
import logging
import asyncio
from typing import Dict, Any, Optional
from urllib.parse import parse_qs
import hmac
import hashlib
import time

import boto3

# Add parent directory to path to import triage package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Lazy imports - only import when needed to avoid loading all dependencies
# from triage.plugins.registry import PluginRegistry
# from triage.core.actions_api import CoreActionsAPI
# from triage.core.event_bus import EventBus
# from triage.jira_client import JiraClient
# from triage.task_classifier import TaskClassifier
# from triage.plan_generator import PlanGenerator

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
secrets_client = boto3.client('secretsmanager')
ssm_client = boto3.client('ssm')

# Global registry instance (reused across warm Lambda invocations)
_registry = None
_event_bus = None


def get_secret(secret_name: str) -> Dict[str, str]:
    """
    Retrieve secret from AWS Secrets Manager.
    
    Args:
        secret_name: Name of the secret
        
    Returns:
        Dict containing secret key-value pairs
        
    Raises:
        Exception: If secret retrieval fails
    """
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise


def get_parameter(parameter_name: str, decrypt: bool = True) -> str:
    """
    Retrieve parameter from AWS Systems Manager Parameter Store.
    
    Args:
        parameter_name: Name of the parameter
        decrypt: Whether to decrypt SecureString parameters
        
    Returns:
        Parameter value
        
    Raises:
        Exception: If parameter retrieval fails
    """
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=decrypt
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error retrieving parameter {parameter_name}: {e}")
        raise


async def initialize_registry():
    """
    Initialize Plugin Registry with Core API and Event Bus.
    
    Creates and configures:
    - Event Bus for core-to-plugin communication
    - Core Actions API with JIRA client and plan generator
    - Plugin Registry with auto-configuration loading
    - Loads and starts all enabled plugins
    
    Returns:
        Initialized PluginRegistry
        
    Raises:
        Exception: If initialization fails
    """
    global _registry, _event_bus
    
    # Lazy imports to avoid loading dependencies for simple health checks
    from triage.plugins.registry import PluginRegistry
    from triage.core.actions_api import CoreActionsAPI
    from triage.core.event_bus import EventBus
    from triage.jira_client import JiraClient
    from triage.task_classifier import TaskClassifier
    from triage.plan_generator import PlanGenerator
    
    if _registry is not None:
        logger.info("Reusing existing Plugin Registry (warm Lambda)")
        return _registry
    
    logger.info("Initializing Plugin Registry (cold start)")
    
    try:
        # Initialize Event Bus
        _event_bus = EventBus()
        logger.info("Event Bus initialized")
        
        # Get JIRA credentials from Secrets Manager
        jira_secret_name = os.environ.get('JIRA_SECRET_NAME', 'triage/jira')
        jira_creds = get_secret(jira_secret_name)
        
        # Initialize JIRA client
        jira_client = JiraClient(
            base_url=jira_creds['jira_base_url'],
            email=jira_creds['jira_email'],
            api_token=jira_creds['jira_api_token'],
            project=jira_creds.get('jira_project')
        )
        logger.info("JIRA client initialized")
        
        # Initialize task classifier and plan generator
        classifier = TaskClassifier()
        
        # Use /tmp for closure tracking in Lambda
        closure_dir = os.path.join('/tmp', '.triage', 'closure')
        generator = PlanGenerator(
            jira_client,
            classifier,
            closure_tracking_dir=closure_dir
        )
        logger.info("Task classifier and plan generator initialized")
        
        # Initialize Core Actions API
        core_api = CoreActionsAPI(jira_client, classifier, generator)
        logger.info("Core Actions API initialized")
        
        # Initialize Plugin Registry
        config_dir = os.environ.get('PLUGIN_CONFIG_PATH', '/config/plugins')
        _registry = PluginRegistry(core_api, _event_bus, config_dir=config_dir)
        logger.info("Plugin Registry initialized")
        
        # Load plugins from environment variable (comma-separated list)
        plugins_to_load = os.environ.get('PLUGINS_ENABLED', 'slack').split(',')
        
        for plugin_name in plugins_to_load:
            plugin_name = plugin_name.strip()
            if plugin_name:
                logger.info(f"Loading plugin: {plugin_name}")
                success = await _registry.load_plugin_with_auto_config(plugin_name)
                
                if success:
                    logger.info(f"Plugin {plugin_name} loaded successfully")
                else:
                    logger.warning(f"Failed to load plugin: {plugin_name}")
        
        # Start all loaded plugins
        await _registry.start_all()
        logger.info("All plugins started")
        
        return _registry
        
    except Exception as e:
        logger.error(f"Failed to initialize Plugin Registry: {e}", exc_info=True)
        raise


def create_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict] = None
) -> Dict:
    """
    Create API Gateway response.
    
    Args:
        status_code: HTTP status code
        body: Response body (will be JSON-encoded if dict)
        headers: Optional additional headers
        
    Returns:
        API Gateway response dict
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body) if not isinstance(body, str) else body
    }


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str
) -> bool:
    """
    Verify Slack webhook signature.
    
    Validates that the request came from Slack by verifying the signature
    using the signing secret. Also checks timestamp to prevent replay attacks.
    
    Args:
        signing_secret: Slack signing secret
        timestamp: Request timestamp from X-Slack-Request-Timestamp header
        body: Raw request body
        signature: Signature from X-Slack-Signature header
        
    Returns:
        bool: True if signature is valid, False otherwise
        
    Validates: Requirement 15.3
    """
    # Check timestamp to prevent replay attacks (within 5 minutes)
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        
        if abs(current_time - request_time) > 60 * 5:
            logger.warning("Request timestamp too old (replay attack?)")
            return False
    except (ValueError, TypeError):
        logger.warning("Invalid timestamp format")
        return False
    
    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body}"
    expected_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures (constant-time comparison)
    return hmac.compare_digest(expected_signature, signature)


async def handle_slack_webhook(event: Dict, context: Any) -> Dict:
    """
    Handle Slack webhook events.
    
    Processes incoming Slack events including:
    - Slash commands (/triage plan, /triage status, etc.)
    - Interactive components (button clicks, modal submissions)
    - Event API events (app mentions, direct messages)
    - URL verification challenge
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
        
    Validates: Requirements 15.1, 15.3
    """
    logger.info("Handling Slack webhook")
    
    try:
        # Get request body
        body = event.get('body', '')
        
        # Verify Slack signature
        headers = event.get('headers', {})
        timestamp = headers.get('X-Slack-Request-Timestamp', '')
        signature = headers.get('X-Slack-Signature', '')
        
        # Get signing secret from environment or parameter store
        signing_secret = os.environ.get('SLACK_SIGNING_SECRET')
        
        if not signing_secret:
            # Try to get from Parameter Store
            try:
                signing_secret = get_parameter('/triage/slack/signing_secret')
            except Exception:
                logger.error("Slack signing secret not configured")
                return create_response(500, {
                    'error': 'Server configuration error'
                })
        
        # Verify signature
        if not verify_slack_signature(signing_secret, timestamp, body, signature):
            logger.warning("Invalid Slack signature")
            return create_response(401, {
                'error': 'Invalid signature'
            })
        
        # Parse request body
        content_type = headers.get('Content-Type', '')
        
        if 'application/json' in content_type:
            # Event API or interactive component
            payload = json.loads(body)
        else:
            # Slash command (application/x-www-form-urlencoded)
            payload = parse_qs(body)
            # Convert single-value lists to strings
            payload = {k: v[0] if len(v) == 1 else v for k, v in payload.items()}
        
        # Handle URL verification challenge
        if payload.get('type') == 'url_verification':
            logger.info("Handling URL verification challenge")
            return create_response(200, {
                'challenge': payload.get('challenge')
            })
        
        # Initialize registry
        registry = await initialize_registry()
        
        # Get Slack plugin
        slack_plugin = registry.get_plugin('slack')
        
        if not slack_plugin:
            logger.error("Slack plugin not loaded")
            return create_response(500, {
                'error': 'Slack plugin not available'
            })
        
        # Route based on payload type
        if payload.get('type') == 'event_callback':
            # Event API event
            logger.info(f"Handling Event API event: {payload.get('event', {}).get('type')}")
            response = await slack_plugin.handle_slack_event(payload)
            
        elif payload.get('type') == 'interactive_message' or payload.get('type') == 'block_actions':
            # Interactive component
            logger.info("Handling interactive component")
            
            # Parse payload if it's a string (from form data)
            if isinstance(payload.get('payload'), str):
                payload = json.loads(payload['payload'])
            
            response = await slack_plugin.handle_interactive_component(payload)
            
        elif 'command' in payload:
            # Slash command
            command = payload.get('command', '').replace('/triage', '').strip()
            logger.info(f"Handling slash command: {command}")
            
            # Parse command into PluginMessage
            from triage.plugins.slack.command_parser import SlackCommandParser
            message = SlackCommandParser.parse_slash_command(payload)
            
            response = await slack_plugin.handle_message(message)
            
        else:
            logger.warning(f"Unknown Slack payload type: {payload.get('type')}")
            return create_response(400, {
                'error': 'Unknown payload type'
            })
        
        # Convert PluginResponse to Slack format
        slack_response = {
            'text': response.content,
            'response_type': response.response_type
        }
        
        # Add blocks if available
        if response.actions or response.attachments:
            blocks = slack_plugin._convert_to_slack_blocks(response)
            slack_response['blocks'] = blocks
        
        return create_response(200, slack_response)
        
    except Exception as e:
        logger.error(f"Error handling Slack webhook: {e}", exc_info=True)
        return create_response(500, {
            'error': 'Internal server error'
        })


async def handle_oauth_authorize(event: Dict, context: Any) -> Dict:
    """
    Handle OAuth authorization request.
    
    Generates the Slack OAuth authorization URL and redirects the user.
    Simplified version that doesn't require full plugin registry initialization.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response with redirect to Slack OAuth
        
    Validates: Requirements 15.2
    """
    logger.info("Handling OAuth authorize request")
    
    try:
        # Get Slack credentials from Secrets Manager (without initializing full registry)
        try:
            # Use environment-specific secret name
            env = os.environ.get('Environment', 'dev')
            slack_secret_name = f'/{env}/triage/slack'
            slack_secret = get_secret(slack_secret_name)
            client_id = slack_secret.get('client_id')
            client_secret = slack_secret.get('client_secret')
        except Exception as e:
            logger.error(f"Failed to get Slack credentials: {e}")
            return create_response(500, {
                'error': 'Slack not configured'
            })
        
        if not client_id or not client_secret:
            logger.error("Slack credentials incomplete")
            return create_response(500, {
                'error': 'Slack credentials incomplete'
            })
        
        # Get redirect URI from environment
        redirect_uri = os.environ.get('SLACK_OAUTH_REDIRECT_URI', 
                                      'http://localhost:8000/plugins/slack/oauth/callback')
        
        # Build Slack OAuth URL manually (without requiring cryptography)
        # Slack OAuth scopes for bot functionality
        scopes = [
            'commands',           # Slash commands
            'chat:write',         # Send messages
            'users:read',         # Read user info
            'channels:read',      # Read channel info
            'im:write',           # Send DMs
            'app_mentions:read'   # Read mentions
        ]
        
        scope_string = ','.join(scopes)
        
        # Generate authorization URL
        from urllib.parse import urlencode
        params = {
            'client_id': client_id,
            'scope': scope_string,
            'redirect_uri': redirect_uri
        }
        
        auth_url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
        
        logger.info(f"Redirecting to Slack OAuth: {auth_url}")
        
        # Return redirect response
        return {
            'statusCode': 302,
            'headers': {
                'Location': auth_url,
                'Access-Control-Allow-Origin': '*'
            },
            'body': ''
        }
        
    except Exception as e:
        logger.error(f"Error handling OAuth authorize: {e}", exc_info=True)
        return create_response(500, {
            'error': 'Failed to generate authorization URL'
        })


async def handle_oauth_callback(event: Dict, context: Any) -> Dict:
    """
    Handle OAuth authorization callback.
    
    Processes the OAuth callback from Slack after workspace authorization.
    Exchanges the authorization code for access tokens and stores the
    installation in the database.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response with success/error page
        
    Validates: Requirements 15.2
    """
    logger.info("Handling OAuth callback")
    
    try:
        # Get query parameters
        params = event.get('queryStringParameters', {})
        code = params.get('code')
        state = params.get('state')
        error = params.get('error')
        
        # Check for OAuth error
        if error:
            logger.error(f"OAuth error: {error}")
            return create_response(400, {
                'error': f'OAuth authorization failed: {error}'
            }, headers={'Content-Type': 'text/html'})
        
        # Validate code
        if not code:
            logger.error("No authorization code provided")
            return create_response(400, {
                'error': 'No authorization code provided'
            }, headers={'Content-Type': 'text/html'})
        
        # Initialize registry
        registry = await initialize_registry()
        
        # Get Slack plugin
        slack_plugin = registry.get_plugin('slack')
        
        if not slack_plugin:
            logger.error("Slack plugin not loaded")
            return create_response(500, {
                'error': 'Slack plugin not available'
            })
        
        # Get OAuth handler
        from triage.plugins.slack.oauth_handler import SlackOAuthHandler
        
        client_id = slack_plugin.config.config.get('client_id')
        client_secret = slack_plugin.config.config.get('client_secret')
        redirect_uri = os.environ.get('SLACK_OAUTH_REDIRECT_URI', 
                                      'https://api.triage.example.com/plugins/slack/oauth/callback')
        
        oauth_handler = SlackOAuthHandler(client_id, client_secret, redirect_uri)
        
        # Exchange code for tokens
        logger.info("Exchanging authorization code for tokens")
        tokens = await oauth_handler.exchange_code_for_token(code)
        
        # Store installation
        logger.info(f"Storing installation for workspace: {tokens.team_id}")
        installation = await slack_plugin.store_installation(
            team_id=tokens.team_id,
            access_token=tokens.access_token,
            bot_user_id=tokens.bot_user_id,
            team_name=tokens.team_name,
            refresh_token=tokens.refresh_token,
            metadata={
                'scope': tokens.scope,
                'installed_at': time.time()
            }
        )
        
        logger.info(
            "Installation successful",
            extra={
                'team_id': tokens.team_id,
                'installation_id': installation.id
            }
        )
        
        # Return success page
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TrIAge Installation Successful</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 500px;
                }}
                h1 {{ color: #2eb886; }}
                p {{ color: #666; line-height: 1.6; }}
                .button {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 24px;
                    background: #2eb886;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Installation Successful!</h1>
                <p>TrIAge has been installed in <strong>{tokens.team_name}</strong>.</p>
                <p>You can now use TrIAge commands in Slack:</p>
                <ul style="text-align: left; display: inline-block;">
                    <li><code>/triage plan</code> - Generate your daily plan</li>
                    <li><code>/triage status</code> - Check plan status</li>
                    <li><code>/triage config</code> - Configure settings</li>
                </ul>
                <a href="slack://open" class="button">Open Slack</a>
            </div>
        </body>
        </html>
        """
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': success_html
        }
        
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}", exc_info=True)
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TrIAge Installation Failed</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 500px;
                }}
                h1 {{ color: #e01e5a; }}
                p {{ color: #666; line-height: 1.6; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Installation Failed</h1>
                <p>There was an error installing TrIAge. Please try again or contact support.</p>
                <p style="font-size: 12px; color: #999;">Error: {str(e)}</p>
            </div>
        </body>
        </html>
        """
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': error_html
        }


async def handle_health_check(event: Dict, context: Any) -> Dict:
    """
    Handle health check endpoint.
    
    Returns basic health status without initializing plugins.
    For full plugin health checks, use the registry directly.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response with health status
        
    Validates: Requirement 15.1
    """
    logger.info("Handling health check")
    
    try:
        # Simple health check without initializing full registry
        # This avoids loading all dependencies just for health check
        return create_response(200, {
            'status': 'healthy',
            'service': 'triage-plugin-handler',
            'version': '1.0.0',
            'message': 'Plugin handler is running',
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error in health check: {e}", exc_info=True)
        return create_response(500, {
            'status': 'unhealthy',
            'error': str(e)
        })


def handler(event: Dict, context: Any) -> Dict:
    """
    Main Lambda handler for plugin webhook events.
    
    Routes requests to appropriate handlers based on path:
    - /plugins/slack/webhook -> Slack webhook handler
    - /plugins/slack/oauth/callback -> OAuth callback handler
    - /plugins/health -> Health check handler
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    # Log request
    logger.info(
        "Plugin handler invoked",
        extra={
            'path': event.get('path'),
            'method': event.get('httpMethod'),
            'request_id': getattr(context, 'aws_request_id', 'unknown')
        }
    )
    
    # Get path
    path = event.get('path', '')
    
    # Route to appropriate handler
    try:
        if '/plugins/slack/webhook' in path:
            return asyncio.run(handle_slack_webhook(event, context))
        elif '/plugins/slack/oauth/authorize' in path:
            return asyncio.run(handle_oauth_authorize(event, context))
        elif '/plugins/slack/oauth/callback' in path:
            return asyncio.run(handle_oauth_callback(event, context))
        elif '/plugins/health' in path:
            return asyncio.run(handle_health_check(event, context))
        else:
            logger.warning(f"Unknown path: {path}")
            return create_response(404, {
                'error': 'Not found'
            })
    except Exception as e:
        logger.error(f"Unhandled error in handler: {e}", exc_info=True)
        return create_response(500, {
            'error': 'Internal server error'
        })
