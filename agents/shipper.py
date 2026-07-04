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
from lib.utils import shutdown_watcher, get_log_dir
from lib import setup_logging
import bspl.adapter.receiver as _recv
import tempfile

LOG_DIR = get_log_dir(PROJECT_ROOT)

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

# Initialize logging system
# Use fixed filename (no timestamp) so logs are overwritten each run
log_filename = str(LOG_DIR / "shipper.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

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
    Mark an item as delivered.
    
    Sets delivery outcome to "delivered". Note: In multi-protocol scenarios,
    the multi-role agent (ahoy) will determine when all protocols are complete
    and create the stop signal. Single-role agents should NOT create the stop signal.
    
    Args:
        msg: Partial object with bindings containing delivery details
    
    Returns:
        msg: Modified Partial with outcome binding set to "delivered"
    """
    msg.bindings["outcome"] = "delivered"
    delivery_id = msg.bindings.get('ID')
    item = msg.bindings.get('item')
    address = msg.bindings.get('address')
    
    log_debug(f"Delivered: ID={delivery_id}, item='{item}', address={address}")
    log_debug(f"Note: Multi-protocol transaction completion will be determined by multi-role agent")
    
    return msg


if __name__ == "__main__":
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Shipper interrupted by user")
    except SystemExit:
        print("✅ Shipper shutting down gracefully")
    except Exception as e:
        print(f"❌ Shipper error: {e}")
        log_debug(f"Error: {e}")
