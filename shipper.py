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
log_filename = f"./logs/shipper_debug_{timestamp}.log"

debug_logger, console_logger = setup_logging(log_filename)

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

# Import the protocol
import Purchase
from Purchase import Shipper, deliver

# Instantiate the adapter for the Shipper role
adapter = Adapter(Shipper, systems, agents, color=COLORS[2])
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
        Creates .stop_signal file for all agents to monitor
    """
    msg.bindings["outcome"] = "delivered"
    delivery_id = msg.bindings.get('ID')
    item = msg.bindings.get('item')
    address = msg.bindings.get('address')
    
    log_debug(f"Delivered: ID={delivery_id}, item='{item}', address={address}")
    
    # Signal successful completion to all agents
    try:
        with open(".stop_signal", "w") as f:
            f.write("delivery_complete")
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
        adapter.start(shutdown_watcher(adapter))
    except KeyboardInterrupt:
        print("\n⏹ Shipper interrupted by user")
    except SystemExit:
        print("✅ Shipper shutting down gracefully")
    except Exception as e:
        print(f"❌ Shipper error: {e}")
        log_debug(f"Error: {e}")
