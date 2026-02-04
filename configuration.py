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
