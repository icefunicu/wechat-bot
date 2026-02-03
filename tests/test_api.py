
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from quart import Quart

# Mock wxauto before importing api
import sys
sys.modules["wxauto"] = MagicMock()

# Import app
from backend.api import app
import backend.api as api_module

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

@pytest.fixture
def mock_manager():
    manager = MagicMock()
    manager.get_status.return_value = {"running": True}
    manager.start = AsyncMock(return_value={"status": "started"})
    manager.stop = AsyncMock(return_value={"status": "stopped"})
    manager.pause = AsyncMock(return_value={"status": "paused"})
    manager.resume = AsyncMock(return_value={"status": "resumed"})
    manager.restart = AsyncMock(return_value={"status": "restarted"})
    
    # Mock MemoryManager
    mem_mgr = MagicMock()
    async def async_get_messages(*args, **kwargs):
        return []
    mem_mgr.get_global_recent_messages = MagicMock(side_effect=async_get_messages)
    manager.get_memory_manager.return_value = mem_mgr
    
    # Replace the manager in the api module
    original_manager = api_module.manager
    api_module.manager = manager
    yield manager
    # Restore
    api_module.manager = original_manager

@pytest.mark.asyncio
async def test_api_status(client, mock_manager):
    response = await client.get('/api/status')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["running"] is True
    mock_manager.get_status.assert_called_once()

@pytest.mark.asyncio
async def test_api_start(client, mock_manager):
    response = await client.post('/api/start')
    assert response.status_code == 200
    mock_manager.start.assert_called_once()

@pytest.mark.asyncio
async def test_api_stop(client, mock_manager):
    response = await client.post('/api/stop')
    assert response.status_code == 200
    mock_manager.stop.assert_called_once()

@pytest.mark.asyncio
async def test_api_messages(client, mock_manager):
    response = await client.get('/api/messages?limit=10')
    assert response.status_code == 200
    mock_manager.get_memory_manager.assert_called()
    mock_manager.get_memory_manager().get_global_recent_messages.assert_called_with(limit=10)

@pytest.mark.asyncio
async def test_api_send(client, mock_manager):
    mock_manager.send_message = AsyncMock(return_value={"success": True})
    response = await client.post('/api/send', json={"target": "User", "content": "Hello"})
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True
    mock_manager.send_message.assert_called_with("User", "Hello")

@pytest.mark.asyncio
async def test_api_usage(client, mock_manager):
    mock_manager.get_usage.return_value = {"total_tokens": 100}
    response = await client.get('/api/usage')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True
    assert data["stats"]["total_tokens"] == 100

@pytest.mark.asyncio
async def test_api_messages_error(client, mock_manager):
    mock_manager.get_memory_manager().get_global_recent_messages.side_effect = Exception("DB Error")
    response = await client.get('/api/messages?limit=10')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is False
    assert "DB Error" in data["message"]

@pytest.mark.asyncio
async def test_api_send_error(client, mock_manager):
    mock_manager.send_message.side_effect = Exception("Send Error")
    response = await client.post('/api/send', json={"target": "User", "content": "Hello"})
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is False
    assert "Send Error" in data["message"]

@pytest.mark.asyncio
async def test_api_usage_error(client, mock_manager):
    mock_manager.get_usage.side_effect = Exception("Usage Error")
    response = await client.get('/api/usage')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is False
    assert "Usage Error" in data["message"]
