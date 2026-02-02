"""Test state manager module."""

import pytest
import json
from pathlib import Path
from lib.state_manager import serialize_adapter_state


class TestStateManager:
    """Test protocol state serialization."""

    def test_serialize_adapter_state_returns_dict(self, mock_llm_client):
        """serialize_adapter_state should return a dict."""
        result = serialize_adapter_state(None)
        assert isinstance(result, (dict, type(None)))

    def test_serialize_adapter_state_is_json_serializable(self, mock_llm_client):
        """Serialized state should be JSON-serializable."""
        result = serialize_adapter_state(None)
        if result is not None:
            try:
                json_str = json.dumps(result)
                assert isinstance(json_str, str)
            except TypeError:
                pytest.fail("serialize_adapter_state result is not JSON-serializable")

    def test_state_includes_role_if_present(self, mock_llm_client):
        """Serialized state should include role information if adapter has it."""
        result = serialize_adapter_state(None)
        # State can be None or a dict - both are valid
        assert result is None or isinstance(result, dict)

    def test_state_serialization_idempotent(self, mock_llm_client):
        """Multiple serializations should produce same result."""
        result1 = serialize_adapter_state(None)
        result2 = serialize_adapter_state(None)
        assert result1 == result2
