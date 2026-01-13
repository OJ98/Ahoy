#!/usr/bin/env python3

import asyncio
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.utils import shutdown_watcher
from lib import setup_logging
import bspl.adapter.receiver as _recv

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
import tempfile

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

# Initialize logging system
# Use fixed filename (no timestamp) so logs are overwritten each run
log_filename = str(LOG_DIR / "seller.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

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
    """
    Generate and send a realistic price quote based on item type.
    
    Implements dynamic pricing strategy where simple items (stationery)
    are cheaper and complex items (electronics) are more expensive.
    
    Args:
        msg: Partial object with bindings containing item description
    
    Returns:
        msg: Modified Partial with price binding set
    """
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
    """
    Mark an accepted order as shipped.
    
    Sets the shipped flag to True and logs shipping details
    for the adapter to process. Note: price is not in the ship message
    binding (protocol only passes ID, item, address).
    
    Args:
        msg: Partial object with bindings containing order details
    
    Returns:
        msg: Modified Partial with shipped binding set to True
    """
    msg.bindings["shipped"] = True
    delivery_id = msg.bindings.get('ID')
    item = msg.bindings.get('item')
    address = msg.bindings.get('address')
    log_debug(f"Shipping: ID={delivery_id}, item='{item}', address={address}")
    return msg


if __name__ == "__main__":
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Seller interrupted by user")
    except SystemExit:
        print("✅ Seller shutting down gracefully")
    except Exception as e:
        print(f"❌ Seller error: {e}")
        log_debug(f"Error: {e}")

