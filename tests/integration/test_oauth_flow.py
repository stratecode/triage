# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for complete OAuth installation flow.
Validates: Requirements 1.1, 1.2
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from slack_bot.oauth_manager import OAuthManager


@pytest.fixture
def oauth_config():
    return {
        'client_id': 'test_client_id_value_here',
        'client_secret': 'test_client_secret_val',
        'redirect_uri': 'https://test.com/callback',
        'encryption_key': '12345678901234567890123456789012'
    }


@pytest.fixture
def mock_oauth_response():
    return {
        'ok': True,
        'access_token': 'xoxb-test-token-value',
        'token_type': 'bot',
        'scope': 'chat:write,commands',
        'bot_user_id': 'U12345ABCDE',
        'team': {'id': 'T12345ABCDE', 'name': 'Test Workspace'}
    }


@pytest.mark.asyncio
async def test_complete_oauth_installation_flow(oauth_config, mock_oauth_response):
    """
    Test complete OAuth flow from installation to token retrieval.
    Validates: Requirements 1.1, 1.2
    """
    token_storage = {}
    oauth_manager = OAuthManager(
        client_id=oauth_config['client_id'],
        client_secret=oauth_config['client_secret'],
        redirect_url=oauth_config['redirect_uri'],
        encryption_key=oauth_config['encryption_key'],
        token_storage=token_storage
    )
    
    # Test installation URL generation
    install_url = oauth_manager.generate_install_url(state='test_state')
    assert 'slack.com/oauth/v2/authorize' in install_url
    assert oauth_config['client_id'] in install_url
    
    # Test OAuth callback and token exchange
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_oauth_response
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        token = await oauth_manager.handle_callback(code='test_code', state='test_state')
        await oauth_manager.store_token(token)
    
    # Verify token is stored and encrypted
    assert 'T12345ABCDE' in token_storage
    stored = token_storage['T12345ABCDE']
    assert stored.access_token != 'xoxb-test-token-value'
    
    # Verify token retrieval and decryption
    retrieved = await oauth_manager.get_token('T12345ABCDE')
    assert retrieved.access_token == 'xoxb-test-token-value'
    assert retrieved.team_id == 'T12345ABCDE'


@pytest.mark.asyncio
async def test_oauth_token_revocation(oauth_config, mock_oauth_response):
    """
    Test token revocation on workspace uninstall.
    Validates: Requirements 1.5, 12.5
    """
    token_storage = {}
    oauth_manager = OAuthManager(
        client_id=oauth_config['client_id'],
        client_secret=oauth_config['client_secret'],
        redirect_url=oauth_config['redirect_uri'],
        encryption_key=oauth_config['encryption_key'],
        token_storage=token_storage
    )
    
    # Install app
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_oauth_response
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        token = await oauth_manager.handle_callback(code='test_code', state='test_state')
        await oauth_manager.store_token(token)
    
    assert 'T12345ABCDE' in token_storage
    
    # Revoke token
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True}
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        result = await oauth_manager.revoke_token('T12345ABCDE')
    
    assert result is True
    assert 'T12345ABCDE' not in token_storage
