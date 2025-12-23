from pathlib import Path

import bspl

BASE_DIR = Path(__file__).resolve().parent
PROTOCOL_PATH = BASE_DIR / "protocols" / "purchase.bspl"

# Load the specification and get the Protocol object for 'Purchase'
spec = bspl.load_file(str(PROTOCOL_PATH))
protocol = spec.protocols.get("Purchase")
# Also export a module named 'Purchase' for convenient imports
spec.export("Purchase")

from Purchase import Buyer, Seller, Shipper

# systems: mapping of system name -> { roles: {role_name: agent_identifier}, protocol: Protocol }
systems = {
    "Purchase": {
        # Map Role objects (from the parsed protocol) to agent identifiers
        "roles": {
            protocol.roles["Buyer"]: Buyer,
            protocol.roles["Seller"]: Seller,
            protocol.roles["Shipper"]: Shipper,
        },
        "protocol": protocol,
    }
}

# agents / endpoints: mapping of agent identifier -> address tuple
agents = {
    Buyer: [("127.0.0.1", 8000)],
    Seller: [("127.0.0.1", 8001)],
    Shipper: [("127.0.0.1", 8002)],
}
