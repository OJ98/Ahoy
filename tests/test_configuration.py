"""Test configuration module."""

import pytest
from pathlib import Path
from configuration import systems


class TestConfigurationLoading:
    """Test protocol configuration loading."""

    def test_systems_dict_not_empty(self):
        """Systems configuration should be populated."""
        assert systems is not None
        assert isinstance(systems, dict)
        assert len(systems) > 0

    def test_purchase_protocol_exists(self):
        """Purchase protocol should be loaded."""
        assert "Purchase" in systems
        assert "protocol" in systems["Purchase"]

    def test_logistics_protocol_exists(self):
        """Logistics protocol should be loaded."""
        assert "Logistics" in systems
        assert "protocol" in systems["Logistics"]

    def test_protocol_has_roles(self):
        """Each protocol should have roles defined."""
        for protocol_name, protocol_data in systems.items():
            protocol = protocol_data.get("protocol")
            assert protocol is not None
            assert hasattr(protocol, "roles")
            assert len(protocol.roles) > 0

    def test_protocol_has_messages(self):
        """Each protocol should have messages."""
        for protocol_name, protocol_data in systems.items():
            protocol = protocol_data.get("protocol")
            assert hasattr(protocol, "messages") or hasattr(protocol, "dialogue_moves")

    def test_role_names_are_strings(self):
        """Role names should be strings."""
        for protocol_name, protocol_data in systems.items():
            protocol = protocol_data.get("protocol")
            for role_name in protocol.roles:
                assert isinstance(role_name, str)
                assert len(role_name) > 0

    @pytest.mark.parametrize("protocol_name", ["Purchase", "Logistics"])
    def test_protocols_exist(self, protocol_name):
        """Test each known protocol exists."""
        assert protocol_name in systems
