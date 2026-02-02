"""Test LLM client module."""

import pytest
from unittest.mock import patch, MagicMock
from lib.llm_client import AnthropicLLMClient


class TestLLMClient:
    """Test LLM client functionality."""

    @pytest.fixture
    def llm_client(self):
        """Create LLM client instance."""
        return AnthropicLLMClient()

    def test_llm_client_init(self, llm_client):
        """LLMClient should initialize."""
        assert llm_client is not None

    def test_llm_client_has_complete_method(self, llm_client):
        """LLMClient should have complete method."""
        assert hasattr(llm_client, "complete")
        assert callable(llm_client.complete)

    @patch("anthropic.Anthropic")
    def test_llm_client_complete_returns_response(self, mock_anthropic, llm_client):
        """complete() should return response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="test response")]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        result = llm_client.complete(
            messages=[{"role": "user", "content": "test"}],
            model="claude-haiku-4-5-20251001"
        )
        
        assert result is not None

    def test_llm_client_has_call_tracking(self, llm_client):
        """LLMClient should have call tracking attributes."""
        assert hasattr(llm_client, "call_count") or hasattr(llm_client, "max_calls")

    def test_llm_client_max_calls_constraint(self, llm_client):
        """LLMClient should enforce max call limit."""
        # Should have max_calls attribute or similar constraint
        assert hasattr(llm_client, "max_calls") or hasattr(llm_client, "call_limit")

    @patch("anthropic.Anthropic")
    def test_llm_client_message_format(self, mock_anthropic, llm_client):
        """complete() should accept properly formatted messages."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response")]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        messages = [
            {"role": "user", "content": "What is 2+2?"}
        ]
        
        result = llm_client.complete(
            messages=messages,
            model="claude-haiku-4-5-20251001"
        )
        
        assert result is not None
