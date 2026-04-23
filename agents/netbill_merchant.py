#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import logging
import random
from datetime import datetime

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
log_filename = str(LOG_DIR / "netbill_merchant.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

# Import the protocol
import NetBill
from NetBill import Merchant, offer, goods, receipt

# Instantiate the adapter for the Merchant role
adapter = Adapter(Merchant, systems, agents, color=COLORS[1])
_recv.adapter = adapter 

# Suppress adapter's internal logging to console
adapter_logger = logging.getLogger("bspl")
adapter_logger.setLevel(logging.CRITICAL)
adapter_logger.propagate = False 


@adapter.enabled(offer)
async def send_offer(msg):
    """
    Generate and send a price quote based on item type.
    
    Args:
        msg: Partial object with bindings containing item description
    
    Returns:
        msg: Modified Partial with price binding set
    """
    item = msg.bindings.get("item", "").lower() if hasattr(msg, 'bindings') else ""
    
    # Price strategy based on item type
    if any(word in item for word in ["pen", "pencil", "paper", "notebook", "stationery", "simple"]):
        msg.bindings["price"] = random.randint(5, 20)
    elif any(word in item for word in ["electronic", "device", "computer"]):
        msg.bindings["price"] = random.randint(200, 500)
    elif any(word in item for word in ["book", "guide", "manual"]):
        msg.bindings["price"] = random.randint(15, 50)
    else:
        msg.bindings["price"] = random.randint(10, 100)
    
    log_msg = f"Quote generated: item='{msg.bindings.get('item')}', price=${msg.bindings['price']}"
    log_debug(log_msg)
    return msg


@adapter.enabled(goods)
async def send_goods(msg):
    """
    Mark an accepted order as shipped/delivered.
    
    Sets the document field to confirm goods have been sent.
    
    Args:
        msg: Partial object with bindings containing order details
    
    Returns:
        msg: Modified Partial with document binding set
    """
    msg.bindings["document"] = "shipped"
    delivery_id = msg.bindings.get('ID')
    item = msg.bindings.get('item')
    log_debug(f"Shipping goods: ID={delivery_id}, item='{item}', document marked as shipped")
    return msg


@adapter.enabled(receipt)
async def send_receipt(msg):
    """
    Send final receipt to customer after receiving payment.
    
    Sets the done flag to mark transaction as complete.
    
    Args:
        msg: Partial object with bindings containing transaction details
    
    Returns:
        msg: Modified Partial with done binding set
    """
    msg.bindings["done"] = "completed"
    transaction_id = msg.bindings.get('ID')
    log_debug(f"Transaction completed and receipt sent: ID={transaction_id}")
    return msg


if __name__ == "__main__":
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Merchant interrupted by user")
    except SystemExit:
        print("✅ Merchant shutting down gracefully")
    except Exception as e:
        print(f"❌ Merchant error: {e}")
        log_debug(f"Error: {e}")
