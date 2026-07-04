"""Test LLM client module."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock
from lib.llm_client import (
    AnthropicLLMClient,
    LLMCallTracker,
    OpenRouterLLMClient,
    get_llm_tracker,
    initialize_llm_tracker,
    reset_llm_tracker,
)


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

    def test_tracker_counts_input_and_output_tokens(self):
        """LLMCallTracker should accumulate input and output tokens."""
        tracker = LLMCallTracker()

        tracker.increment_call(input_tokens=10, output_tokens=5)
        tracker.increment_call(input_tokens=7, output_tokens=3)

        assert tracker.call_count == 2
        assert tracker.input_tokens == 17
        assert tracker.output_tokens == 8

    @patch("requests.post")
    def test_openrouter_complete_posts_expected_payload_and_tracks_usage(self, mock_post, monkeypatch):
        """OpenRouter client should send the expected chat payload and record usage."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
        monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://example.org")
        monkeypatch.setenv("OPENROUTER_APP_TITLE", "Ahoy")
        reset_llm_tracker()
        initialize_llm_tracker()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "openrouter response"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 4},
        }
        mock_post.return_value = mock_response

        client = OpenRouterLLMClient()
        result = asyncio.run(
            client.complete("hello", max_tokens=123, system_prompt="system")
        )

        assert result == "openrouter response"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {
            "model": "anthropic/claude-3.5-haiku",
            "max_tokens": 123,
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
            ],
        }
        assert kwargs["headers"]["Authorization"] == "Bearer test-openrouter-key"
        assert kwargs["headers"]["HTTP-Referer"] == "https://example.org"
        assert kwargs["headers"]["X-OpenRouter-Title"] == "Ahoy"
        assert kwargs["timeout"] == 60
        tracker = get_llm_tracker()
        assert tracker.call_count == 1
        assert tracker.input_tokens == 11
        assert tracker.output_tokens == 4

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
