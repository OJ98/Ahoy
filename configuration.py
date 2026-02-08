from pathlib import Path

import bspl

BASE_DIR = Path(__file__).resolve().parent
PURCHASE_PROTOCOL_PATH = BASE_DIR / "protocols" / "purchase.bspl"
LOGISTICS_PROTOCOL_PATH = BASE_DIR / "protocols" / "logistics.bspl"
CREDIT_PURCHASE_PROTOCOL_PATH = BASE_DIR / "protocols" / "credit_purchase.bspl"

# Load the Purchase protocol
purchase_spec = bspl.load_file(str(PURCHASE_PROTOCOL_PATH))
purchase_protocol = purchase_spec.protocols.get("Purchase")
# Export a module named 'Purchase' for convenient imports
purchase_spec.export("Purchase")

from Purchase import Buyer, Seller, Shipper

# Load the CreditPurchase protocol
credit_purchase_spec = bspl.load_file(str(CREDIT_PURCHASE_PROTOCOL_PATH))
credit_purchase_protocol = credit_purchase_spec.protocols.get("CreditPurchase")
# Export a module named 'CreditPurchase' for convenient imports
credit_purchase_spec.export("CreditPurchase")
from CreditPurchase import CreditBuyer, CreditSeller, CreditShipper

# Load the Logistics protocol
logistics_spec = bspl.load_file(str(LOGISTICS_PROTOCOL_PATH))
logistics_protocol = logistics_spec.protocols.get("Logistics")
# Export a module named 'Logistics' for convenient imports
logistics_spec.export("Logistics")

from Logistics import Labeler, Merchant, Packer, Wrapper

# MULTI-ROLE SUPPORT: Agent identities (strings) instead of role objects
# Each agent can have multiple addresses to support playing multiple roles simultaneously
# Format: agent_name -> list of (host, port) tuples
agents = {
    "Buyer": [("127.0.0.1", 8001)],
    "Seller": [("127.0.0.1", 8002)],
    "Shipper": [("127.0.0.1", 8003)],
    "Labeler": [("127.0.0.1", 8004)],
    "Merchant": [("127.0.0.1", 8005)],
    "Packer": [("127.0.0.1", 8006)],
    "Wrapper": [("127.0.0.1", 8007)],
    "CreditBuyer": [("127.0.0.1", 8008)],
    "CreditSeller": [("127.0.0.1", 8009)],
    "CreditShipper": [("127.0.0.1", 8010)],
    # Generic LLM agent for multiprotocol testing (ahoy.py uses this)
    # Running on port 8000 for simplified configuration
    "ahoy": [("127.0.0.1", 8000)],
}

# BACKWARD COMPATIBILITY: Legacy role-based agent mapping for existing hardcoded agents
# These allow old agents (buyer.py, seller.py, etc.) to continue working
# Maps role objects to agent identities for resolution
agents[Buyer] = agents["Buyer"]
agents[Seller] = agents["Seller"]
agents[Shipper] = agents["Shipper"]
agents[Labeler] = agents["Labeler"]
agents[Merchant] = agents["Merchant"]
agents[Packer] = agents["Packer"]
agents[Wrapper] = agents["Wrapper"]
agents[CreditBuyer] = agents["CreditBuyer"]
agents[CreditSeller] = agents["CreditSeller"]
agents[CreditShipper] = agents["CreditShipper"]

# Special agent registry class to handle both string and role object keys
class AgentRegistry(dict):
    """
    Dictionary that supports looking up agent addresses by both string name and role object.
    Falls back to string lookup if role object lookup fails.
    """
    def __getitem__(self, key):
        # Try direct lookup first (string or role object)
        try:
            return super().__getitem__(key)
        except KeyError:
            # If key is a role object with a name, try string lookup
            if hasattr(key, 'name'):
                try:
                    return super().__getitem__(key.name)
                except KeyError:
                    pass
            # Also try the other direction - if it's a string, check for role object
            if isinstance(key, str):
                # Search for a role object with this name
                for k, v in self.items():
                    if hasattr(k, 'name') and k.name == key:
                        return v
            raise KeyError(key)
    
    def __contains__(self, key):
        # Check direct lookup
        if super().__contains__(key):
            return True
        # Check name-based lookup for role objects
        if hasattr(key, 'name') and super().__contains__(key.name):
            return True
        # Check reverse lookup
        if isinstance(key, str):
            for k in self.keys():
                if hasattr(k, 'name') and k.name == key:
                    return True
        return False


# Convert agents dict to AgentRegistry for robust lookups
agents = AgentRegistry(agents)

# Legacy alias for backward compatibility (old agents import 'config' instead of 'agents')
config = agents

# systems: mapping of system name -> { roles: {role_obj: agent_name}, protocol: Protocol }
# Role objects map to agent identities (strings), not role identifiers anymore
systems = {
    "Purchase": {
        # Map Role objects (from the parsed protocol) to agent identities (strings)
        "roles": {
            purchase_protocol.roles["Buyer"]: "Buyer",
            purchase_protocol.roles["Seller"]: "Seller",
            purchase_protocol.roles["Shipper"]: "Shipper",
        },
        "protocol": purchase_protocol,
    },
    "CreditPurchase": {
        # Map Role objects (from the parsed protocol) to agent identities (strings)
        "roles": {
            credit_purchase_protocol.roles["CreditBuyer"]: "CreditBuyer",
            credit_purchase_protocol.roles["CreditSeller"]: "CreditSeller",
            credit_purchase_protocol.roles["CreditShipper"]: "CreditShipper",
        },
        "protocol": credit_purchase_protocol,
    },
    "Logistics": {
        # Map Role objects (from the parsed protocol) to agent identities (strings)
        "roles": {
            logistics_protocol.roles["Labeler"]: "Labeler",
            logistics_protocol.roles["Merchant"]: "Merchant",
            logistics_protocol.roles["Packer"]: "Packer",
            logistics_protocol.roles["Wrapper"]: "Wrapper",
        },
        "protocol": logistics_protocol,
    }
}


def configure_ahoy_for_multiprotocol(protocol_role_pairs):
    """
    Configure the role mappings to use 'ahoy' agent for multiprotocol participation.
    
    Args:
        protocol_role_pairs: List of (protocol_name, role_name) tuples
                              e.g., [("Purchase", "Buyer"), ("Logistics", "Merchant")]
    
    This function dynamically updates:
    1. The role-to-agent mappings in the systems dict to use "ahoy" agent
    2. The agents dict so that messages to these roles route to ahoy's address
    """
    # Get ahoy's address
    ahoy_addresses = agents.get("ahoy", [("127.0.0.1", 9000)])
    
    for protocol_name, role_name in protocol_role_pairs:
        if protocol_name in systems and role_name in systems[protocol_name]["protocol"].roles:
            # Get the role object from the protocol
            role_obj = systems[protocol_name]["protocol"].roles[role_name]
            
            # Map this role to the "ahoy" agent in systems
            # This tells the BSPL adapter that this role is handled by "ahoy"
            systems[protocol_name]["roles"][role_obj] = "ahoy"
            
            # CRITICAL: Update agents dict so messages route to ahoy's port, not the original role's port
            # When other agents send messages to this role, they look it up in the agents dict
            # and need to find ahoy's address (port 8000), not the original address (e.g., port 8001 for Buyer)
            agents[role_obj] = ahoy_addresses
            agents[role_name] = ahoy_addresses  # Also update string-based lookup


def _apply_multiprotocol_ahoy_from_env():
    """
    Apply multiprotocol ahoy configuration from environment variable.
    
    Environment variable: MULTIPROTOCOL_AHOY_ROLES
    Value: Comma-separated list of "Protocol:Role" pairs
    Example: "Purchase:Buyer,Logistics:Merchant"
    
    This is called automatically at module load time if the env var is set.
    """
    import os
    roles_str = os.environ.get("MULTIPROTOCOL_AHOY_ROLES")
    if not roles_str:
        return
    
    try:
        # Parse roles from env var
        protocol_role_pairs = []
        for pair_str in roles_str.split(","):
            parts = pair_str.strip().split(":")
            if len(parts) == 2:
                protocol, role = parts
                protocol_role_pairs.append((protocol.strip(), role.strip()))
        
        if protocol_role_pairs:
            configure_ahoy_for_multiprotocol(protocol_role_pairs)
    except Exception as e:
        import sys
        print(f"Warning: Failed to apply MULTIPROTOCOL_AHOY_ROLES override: {e}", file=sys.stderr)


# Apply multiprotocol ahoy overrides from environment variable at module load time
_apply_multiprotocol_ahoy_from_env()

