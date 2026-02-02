"""Test utility functions."""

import pytest
from pathlib import Path
from lib.utils import validate_protocol_and_role
from configuration import systems


class TestUtils:
    """Test utility functions."""

    def test_validate_protocol_and_role_valid(self):
        """Should accept valid protocol and role combinations."""
        for protocol_name, protocol_data in systems.items():
            protocol = protocol_data["protocol"]
            for role_name in protocol.roles:
                # Should not raise exception
                try:
                    validate_protocol_and_role(protocol_name, role_name)
                except Exception as e:
                    pytest.fail(f"Valid protocol/role rejected: {protocol_name}/{role_name}: {e}")

    def test_validate_protocol_and_role_invalid_protocol(self):
        """Should reject invalid protocol."""
        with pytest.raises((ValueError, KeyError)):
            validate_protocol_and_role("InvalidProtocol", "SomeRole")

    def test_validate_protocol_and_role_invalid_role(self):
        """Should reject invalid role for protocol."""
        # Get first protocol name
        protocol_name = list(systems.keys())[0]
        
        with pytest.raises((ValueError, KeyError)):
            validate_protocol_and_role(protocol_name, "InvalidRole99999")

    def test_validate_accepts_all_known_protocols(self):
        """Should validate all known protocols."""
        for protocol_name in systems.keys():
            protocol = systems[protocol_name]["protocol"]
            first_role = list(protocol.roles)[0]
            
            try:
                validate_protocol_and_role(protocol_name, first_role)
            except Exception as e:
                pytest.fail(f"Failed to validate known protocol: {protocol_name}: {e}")
