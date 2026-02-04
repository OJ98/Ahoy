"""Test configuration module."""

import pytest
import json
from pathlib import Path
from configuration import systems, agents, config
from lib.dynamic_adapter_manager import (
    create_adapter_for_agent,
    create_adapter_for_role,
)


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


class TestMultiRoleConfiguration:
    """Test multi-role configuration setup."""

    def test_agents_dict_uses_string_identities(self):
        """Agents dict should use string identities as primary keys."""
        assert "Buyer" in agents
        assert "Seller" in agents
        assert "Wrapper" in agents
        assert isinstance(agents["Buyer"], list)
        assert len(agents["Buyer"]) > 0

    def test_agents_dict_has_addresses(self):
        """Each agent should have address tuples."""
        for agent_name, addresses in agents.items():
            if isinstance(agent_name, str) and "." not in agent_name:  # Skip role object keys
                assert isinstance(addresses, list)
                for addr in addresses:
                    assert isinstance(addr, tuple)
                    assert len(addr) == 2  # (host, port)
                    assert isinstance(addr[0], str)  # host
                    assert isinstance(addr[1], int)  # port

    def test_systems_map_roles_to_agent_identities(self):
        """Systems should map role objects to agent identity strings."""
        for protocol_name, protocol_config in systems.items():
            roles_mapping = protocol_config.get("roles", {})
            for role_obj, agent_identity in roles_mapping.items():
                assert isinstance(agent_identity, str)
                assert agent_identity in agents

    def test_backward_compatibility_config_alias(self):
        """config should be an alias for agents dict."""
        assert config is agents


class TestMultiRoleBackwardCompatibility:
    """Test backward compatibility with legacy role-based access."""

    def test_legacy_role_object_access(self):
        """Legacy code should still access agents with role objects."""
        from Purchase import Buyer, Seller
        
        # Role objects should still work as keys
        assert agents.get(Buyer) is not None
        assert agents.get(Seller) is not None

    def test_legacy_role_object_addresses(self):
        """Role object access should return correct addresses."""
        from Purchase import Buyer
        
        # Both string and role object should return same addresses
        assert agents["Buyer"] == agents[Buyer]

    def test_legacy_create_adapter_for_role(self):
        """Legacy create_adapter_for_role should still work."""
        adapter, error = create_adapter_for_role("Purchase", "Buyer")
        
        assert error is None
        assert adapter is not None
        assert adapter.name == "Buyer"

    def test_legacy_all_roles_support(self):
        """All standard roles should work with legacy method."""
        roles = [
            ("Purchase", "Buyer"),
            ("Purchase", "Seller"),
            ("Purchase", "Shipper"),
            ("Logistics", "Merchant"),
            ("Logistics", "Wrapper"),
            ("Logistics", "Packer"),
            ("Logistics", "Labeler"),
        ]
        
        for protocol, role in roles:
            adapter, error = create_adapter_for_role(protocol, role)
            assert error is None
            assert adapter is not None


class TestMultiRoleAgentCreation:
    """Test creating adapters for agent identities."""

    def test_create_adapter_for_agent_buyer(self):
        """Should create adapter for Buyer agent identity."""
        adapter, error = create_adapter_for_agent("Buyer")
        
        assert error is None
        assert adapter is not None
        assert adapter.name == "Buyer"

    def test_create_adapter_for_agent_wrapper(self):
        """Should create adapter for Wrapper agent identity."""
        adapter, error = create_adapter_for_agent("Wrapper")
        
        assert error is None
        assert adapter is not None
        assert adapter.name == "Wrapper"

    def test_create_adapter_for_invalid_agent(self):
        """Should return error for non-existent agent."""
        adapter, error = create_adapter_for_agent("NonExistentAgent")
        
        assert adapter is None
        assert error is not None
        assert "not found" in error.lower()

    def test_adapter_color_index(self):
        """Adapter should accept color index parameter."""
        adapter, error = create_adapter_for_agent("Buyer", color_index=2)
        
        assert error is None
        assert adapter is not None


class TestMultiRoleConfigParsing:
    """Test parsing multi-role CHIPS config format."""

    def test_parse_single_role_format(self):
        """Should parse single-role format (backward compatible)."""
        config_content = "Purchase:Buyer"
        
        # Parse logic from ahoy.py _initialize_protocol_and_role
        if ":" in config_content:
            parts = config_content.split(":")
            assert len(parts) == 2
            protocol = parts[0].strip()
            role = parts[1].strip()
            
            assert protocol == "Purchase"
            assert role == "Buyer"

    def test_parse_multi_role_json_format(self):
        """Should parse multi-role JSON format."""
        config_content = json.dumps({
            "roles": [
                {"protocol": "Purchase", "role": "Buyer"},
                {"protocol": "Logistics", "role": "Wrapper"}
            ]
        })
        
        # Parse logic
        roles_list = []
        if config_content.startswith('{'):
            config_data = json.loads(config_content)
            if "roles" in config_data:
                for role_entry in config_data["roles"]:
                    protocol = role_entry.get("protocol", "").strip()
                    role = role_entry.get("role", "").strip()
                    if protocol and role:
                        roles_list.append((protocol, role))
        
        assert len(roles_list) == 2
        assert roles_list[0] == ("Purchase", "Buyer")
        assert roles_list[1] == ("Logistics", "Wrapper")

    def test_map_roles_to_agent_identity(self):
        """Should map multiple roles to agent identities."""
        roles_list = [
            ("Purchase", "Buyer"),
            ("Logistics", "Wrapper")
        ]
        
        agent_roles = {}
        
        for protocol_name, role_name in roles_list:
            protocol_config = systems.get(protocol_name)
            assert protocol_config is not None
            
            protocol = protocol_config["protocol"]
            role_obj = protocol.roles.get(role_name)
            assert role_obj is not None
            
            agent_identity = protocol_config["roles"].get(role_obj)
            assert agent_identity is not None
            
            if agent_identity not in agent_roles:
                agent_roles[agent_identity] = []
            agent_roles[agent_identity].append((protocol_name, role_name))
        
        # In this specific case, Buyer and Wrapper are different agents
        assert "Buyer" in agent_roles
        assert "Wrapper" in agent_roles
