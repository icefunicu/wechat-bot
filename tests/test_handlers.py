
import pytest
from unittest.mock import MagicMock, patch
from backend.handlers.sender import send_quote_message
from backend.handlers.converters import normalize_message_item

def test_send_quote_message_exception_retry():
    quote_item = MagicMock()
    
    # First call raises exception, second succeeds
    quote_item.quote.side_effect = [Exception("First fail"), "Success"]
    
    # We need to mock time.sleep to avoid waiting
    with patch("time.sleep") as mock_sleep:
        success, msg = send_quote_message(quote_item, "text", 5.0)
        
        assert success is True
        assert mock_sleep.called

def test_normalize_msg_item_bad_timestamp():
    class MockItem:
        pass
    
    mock_item = MockItem()
    mock_item.type = "friend"
    mock_item.content = "hello"
    mock_item.sender = "user"
    mock_item.time = "invalid_timestamp" 
    
    # normalize_message_item(chat_name, item, self_name, chat_type=None)
    # Check definition, chat_type might be required
    event = normalize_message_item("chat", mock_item, "me", "friend")
    assert event is not None
    assert event.timestamp is None
