#!/usr/bin/env python3

import random, os, asyncio, logging
from datetime import datetime
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.utils import shutdown_watcher
from lib import setup_logging
import bspl.adapter.receiver as _recv

# Initialize logging system
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"./logs/seller_debug_{timestamp}.log"

debug_logger, console_logger = setup_logging(log_filename)

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

# Import the protocol
import Purchase
from Purchase import Seller, quote, ship


# Instantiate the adapter for the Seller role
adapter = Adapter(Seller, systems, agents, color=COLORS[1])
_recv.adapter = adapter 

# Suppress adapter's internal logging to console
adapter_logger = logging.getLogger("bspl")
adapter_logger.setLevel(logging.CRITICAL)
adapter_logger.propagate = False 


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
    log_debug(log_msg)
    return msg


@adapter.enabled(ship)
async def send_ship(msg):
    """Mark item as shipped."""
    msg.bindings["shipped"] = True
    log_debug(f"Shipping: ID={msg.bindings.get('ID')}, item='{msg.bindings.get('item')}', price=${msg.bindings.get('price')}")
    return msg


if __name__ == "__main__":
    try:
        adapter.start(shutdown_watcher(adapter))
    except KeyboardInterrupt:
        print("\n⏹ Seller interrupted by user")
    except SystemExit:
        print("✅ Seller shutting down gracefully")
    except Exception as e:
        print(f"❌ Seller error: {e}")
        log_debug(f"Error: {e}")

