"""
This agent combines wrapped items with their labels to create the final package.
"""

import logging
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from configuration import systems, agents
from Logistics import Packed, Wrapped, Labeled, Packer
from lib import setup_logging
from lib.utils import shutdown_watcher

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize logging system
# Use fixed filename (no timestamp) so logs are overwritten each run
log_filename = str(LOG_DIR / "packer.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

adapter = Adapter(Packer, systems, agents)

logger = logging.getLogger("packer")
logger.setLevel(logging.DEBUG)

# Store received messages to match pairs
received_wrapped = {}  # Key: (orderID, itemID), Value: Wrapped message
received_labeled = {}  # Key: orderID, Value: Labeled message

# Statistics tracking
items_wrapped = 0
items_labeled = 0
items_packed = 0

@adapter.reaction(Wrapped)
async def receive_wrapped(msg):
    """Handles wrapped items by storing them and checking if we can pack."""
    global items_wrapped
    
    key = (msg["orderID"], msg["itemID"])
    received_wrapped[key] = msg
    items_wrapped += 1
    
    item_name = msg["item"]
    wrapping = msg["wrapping"]
    logger.info(f"[W{items_wrapped}] Received Wrapped: order {msg['orderID'][:8]}... item {msg['itemID'][:8]}... ({item_name}, {wrapping})")
    log_debug(f"Full: orderID={msg['orderID']}, itemID={msg['itemID']}, item={item_name}, wrapping={wrapping}")
    
    await try_pack()
    return msg

@adapter.reaction(Labeled)
async def receive_labeled(msg):
    """Handles labeled items by storing them and checking if we can pack."""
    global items_labeled
    
    order_id = msg["orderID"]
    received_labeled[order_id] = msg
    items_labeled += 1
    
    label = msg["label"]
    logger.info(f"[L{items_labeled}] Received Labeled: order {order_id[:8]}... label {label[:8]}...")
    log_debug(f"Full: orderID={order_id}, label={label}")
    
    await try_pack()
    return msg

async def try_pack():
    """Attempt to pack if we have both Wrapped and Labeled for an order/item."""
    global items_packed
    
    # Find matching pairs of wrapped and labeled items
    packed_items = []
    for (order_id, item_id), wrapped_msg in list(received_wrapped.items()):
        if order_id in received_labeled:
            labeled_msg = received_labeled[order_id]
            # Create packed message
            msg_dict = {
                "orderID": wrapped_msg["orderID"],
                "itemID": wrapped_msg["itemID"],
                "item": wrapped_msg["item"],
                "wrapping": wrapped_msg["wrapping"],
                "label": labeled_msg["label"],
                "status": "packed"
            }
            items_packed += 1
            
            item_name = msg_dict["item"]
            wrapping = msg_dict["wrapping"]
            label_short = msg_dict["label"][:8]
            logger.info(f"[P{items_packed}] Packed: order {msg_dict['orderID'][:8]}... item {msg_dict['itemID'][:8]}... ({item_name}, {wrapping}, label {label_short}...)")
            log_debug(f"Full: orderID={msg_dict['orderID']}, itemID={msg_dict['itemID']}, item={item_name}, wrapping={wrapping}, label={msg_dict['label']}")
            
            packed_items.append(msg_dict)
            await adapter.send(Packed(**msg_dict))
            
            # Remove from tracking
            del received_wrapped[(order_id, item_id)]
    
    if packed_items:
        logger.debug(f"Packing batch: {len(packed_items)} items packed, {len(received_wrapped)} wrapped items waiting, {len(received_labeled)} labeled orders available")


if __name__ == "__main__":
    logger.info("Starting Packer...")
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Packer interrupted by user")
    except SystemExit:
        print("✅ Packer shutting down gracefully")
    except Exception as e:
        print(f"❌ Packer error: {e}")
