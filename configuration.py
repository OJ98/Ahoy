from pathlib import Path

import bspl

BASE_DIR = Path(__file__).resolve().parent
PURCHASE_PROTOCOL_PATH = BASE_DIR / "protocols" / "purchase.bspl"
LOGISTICS_PROTOCOL_PATH = BASE_DIR / "protocols" / "logistics.bspl"

# Load the Purchase protocol
purchase_spec = bspl.load_file(str(PURCHASE_PROTOCOL_PATH))
purchase_protocol = purchase_spec.protocols.get("Purchase")
# Export a module named 'Purchase' for convenient imports
purchase_spec.export("Purchase")

from Purchase import Buyer, Seller, Shipper

# Load the Logistics protocol
logistics_spec = bspl.load_file(str(LOGISTICS_PROTOCOL_PATH))
logistics_protocol = logistics_spec.protocols.get("Logistics")
# Export a module named 'Logistics' for convenient imports
logistics_spec.export("Logistics")

from Logistics import Labeler, Merchant, Packer, Wrapper

# systems: mapping of system name -> { roles: {role_name: agent_identifier}, protocol: Protocol }
systems = {
    "Purchase": {
        # Map Role objects (from the parsed protocol) to agent identifiers
        "roles": {
            purchase_protocol.roles["Buyer"]: Buyer,
            purchase_protocol.roles["Seller"]: Seller,
            purchase_protocol.roles["Shipper"]: Shipper,
        },
        "protocol": purchase_protocol,
    },
    "Logistics": {
        # Map Role objects (from the parsed protocol) to agent identifiers
        "roles": {
            logistics_protocol.roles["Labeler"]: Labeler,
            logistics_protocol.roles["Merchant"]: Merchant,
            logistics_protocol.roles["Packer"]: Packer,
            logistics_protocol.roles["Wrapper"]: Wrapper,
        },
        "protocol": logistics_protocol,
    }
}

# agents / endpoints: mapping of agent identifier -> address tuple
agents = {
    Buyer: [("127.0.0.1", 8001)],
    Seller: [("127.0.0.1", 8002)],
    Shipper: [("127.0.0.1", 8003)],
    Labeler: [("127.0.0.1", 8004)],
    Merchant: [("127.0.0.1", 8005)],
    Packer: [("127.0.0.1", 8006)],
    Wrapper: [("127.0.0.1", 8007)],
}
