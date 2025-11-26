#!/usr/bin/env python3

import random, os, asyncio
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.utils import shutdown_watcher
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Seller, quote, ship


# Instantiate the adapter for the Seller role
adapter = Adapter(Seller, systems, agents, color=COLORS[1])
_recv.adapter = adapter 


@adapter.enabled(quote)
async def send_quote(msg):
    """Generate a realistic price based on item type."""
    # msg is a Partial object, access bindings through it
    item = msg.bindings.get("item", "").lower() if hasattr(msg, 'bindings') else ""
    
    # Price strategy based on item characteristics
    # Simple items (pen, paper, etc.) should be cheaper
    # Complex items should be more expensive
    if any(word in item for word in ["pen", "pencil", "paper", "notebook", "stationery", "simple", "basic", "standard"]):
        # Simple office items: $2-15
        msg.bindings["price"] = random.randint(2, 15)
    elif any(word in item for word in ["computer", "laptop", "phone", "device", "electronics", "complex"]):
        # Electronics/complex items: $500-2000
        msg.bindings["price"] = random.randint(500, 2000)
    elif any(word in item for word in ["book", "guide", "manual", "document"]):
        # Books/documents: $10-50
        msg.bindings["price"] = random.randint(10, 50)
    else:
        # Unknown items: generic range $5-100
        msg.bindings["price"] = random.randint(5, 100)
    
    log_msg = f"Quote generated: item='{msg.bindings.get('item')}', price=${msg.bindings['price']}"
    import sys
    print(f"[SELLER] {log_msg}", file=sys.stderr)
    return msg


@adapter.enabled(ship)
async def send_ship(msg):
    """Mark item as shipped."""
    msg.bindings["shipped"] = True
    import sys
    print(f"[SELLER] Shipping: ID={msg.bindings.get('ID')}, item='{msg.bindings.get('item')}', price=${msg.bindings.get('price')}", file=sys.stderr)
    return msg


if __name__ == "__main__":
    # Start adapter and the shutdown watcher so processes can exit cleanly
    adapter.start(shutdown_watcher(adapter))
