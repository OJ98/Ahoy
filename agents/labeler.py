"""
This agent generates unique labels for orders upon request.
"""

import logging
import uuid
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from configuration import systems, agents
from Logistics import Labeled, RequestLabel, Labeler
from lib import setup_logging
from lib.utils import shutdown_watcher

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize logging system
# Use fixed filename (no timestamp) so logs are overwritten each run
log_filename = str(LOG_DIR / "labeler.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

adapter = Adapter(Labeler, systems, agents)

logger = logging.getLogger("labeler")
logger.setLevel(logging.INFO)

# Statistics tracking
labels_generated = 0
orders_processed = set()

@adapter.reaction(RequestLabel)
async def label(msg):
    """Handles label requests by generating a unique UUID-based label."""
    global labels_generated, orders_processed
    
    order_id = msg['orderID']
    address = msg['address'] if 'address' in msg else 'N/A'
    label_text = str(uuid.uuid4())
    
    labels_generated += 1
    orders_processed.add(order_id)
    
    logger.info(f"[{labels_generated}] Generated label {label_text[:8]}... for order {order_id[:8]}... (address: {address})")
    log_debug(f"Full details: Order={order_id}, Address={address}, Label={label_text}")
    
    await adapter.send(Labeled(label=label_text, **msg.payload))
    logger.debug(f"Sent Labeled message for order {order_id[:8]}... | Total labels generated: {labels_generated}")
    return msg

if __name__ == "__main__":
    logger.info("Starting Labeler...")
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Labeler interrupted by user")
    except SystemExit:
        print("✅ Labeler shutting down gracefully")
    except Exception as e:
        print(f"❌ Labeler error: {e}")
