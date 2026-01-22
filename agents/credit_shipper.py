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
log_filename = str(LOG_DIR / "credit_shipper.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

# Import the protocol
import CreditPurchase
from CreditPurchase import CreditShipper, deliver

# Instantiate the adapter for the Shipper role
adapter = Adapter(CreditShipper, systems, agents, color=COLORS[2])
_recv.adapter = adapter

# Suppress adapter's internal logging to console
adapter_logger = logging.getLogger("bspl")
adapter_logger.setLevel(logging.CRITICAL)
adapter_logger.propagate = False


@adapter.enabled(deliver)
async def deliver_item(msg):
    """
    Mark an item as delivered and signal transaction completion.
    
    Sets delivery outcome to "delivered" and creates a stop signal
    that instructs all agents to gracefully shut down when the
    transaction reaches its final state.
    
    Args:
        msg: Partial object with bindings containing delivery details
    
    Returns:
        msg: Modified Partial with outcome binding set to "delivered"
    
    Raises:
        Creates maf_stop_signal.txt file in temp directory for all agents to monitor
    """
    msg.bindings["outcome"] = "delivered"
    delivery_id = msg.bindings.get('ID')
    item = msg.bindings.get('item')
    address = msg.bindings.get('address')
    
    log_debug(f"Delivered: ID={delivery_id}, item='{item}', address={address}")
    
    # Signal successful completion to all agents
    try:
        STOP_SIGNAL_PATH.write_text("delivery_complete")
        log_debug("✅ DELIVERY COMPLETE - Stop signal created for all agents")
        # Print success to terminal
        print(f"\n{'='*70}")
        print(f"✅ SUCCESS: Item delivered!")
        print(f"   Transaction ID: {delivery_id}")
        print(f"   Item: {item}")
        print(f"   Address: {address}")
        print(f"   All agents shutting down gracefully...")
        print(f"{'='*70}\n")
    except Exception as e:
        log_debug(f"Error creating stop signal: {e}")
    
    return msg


if __name__ == "__main__":
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ CreditShipper interrupted by user")
    except SystemExit:
        print("✅ CreditShipper shutting down gracefully")
    except Exception as e:
        print(f"❌ CreditShipper error: {e}")
        log_debug(f"Error: {e}")
