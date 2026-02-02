"""Shared pytest fixtures and configuration."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = MagicMock()
    client.complete.return_value = {
        "content": [{"text": '{"role": "Buyer", "protocol": "Purchase"}'}]
    }
    return client


@pytest.fixture
def temp_test_dir(tmp_path):
    """Temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_bspl_content():
    """Sample BSPL protocol content."""
    return """
protocol Purchase
    role Buyer
    role Seller
    
    message RequestToBuy(item)
    message Quote(price)
    message Shipped()
    
    Buyer sends RequestToBuy to Seller
    Seller sends Quote to Buyer
    Buyer sends Payment to Seller
    Seller sends Shipped to Buyer
"""


@pytest.fixture
def sample_protocol_structure():
    """Sample protocol structure for testing."""
    return {
        "Purchase": {
            "roles": ["Buyer", "Seller", "Shipper"],
            "messages": {
                "RequestToBuy": {"from": "Buyer", "to": "Seller"},
                "Quote": {"from": "Seller", "to": "Buyer"},
                "Payment": {"from": "Buyer", "to": "Seller"},
                "Shipped": {"from": "Seller", "to": "Shipper"},
            },
        }
    }
