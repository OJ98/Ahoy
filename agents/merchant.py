"""
This agent initiates the logistics protocol by generating orders and handling packed responses.
"""

import logging
import random
import asyncio
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from configuration import systems, agents
from Logistics import RequestLabel, RequestWrapping, Packed, Merchant
from lib import setup_logging
from lib.utils import shutdown_watcher

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize logging system
# Use fixed filename (no timestamp) so logs are overwritten each run
log_filename = str(LOG_DIR / "merchant.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

adapter = Adapter(Merchant, systems, agents)

logger = logging.getLogger("merchant")
# logger.setLevel(logging.DEBUG)

async def order_generator():
    """Generates sample orders with random items and addresses."""
    for orderID in range(10):
        await adapter.send(
            RequestLabel(
                orderID=orderID,
                address=random.choice(["Lancaster University", "NCSU"]),
            )
        )
        for i in range(2):
            await adapter.send(
                RequestWrapping(
                    orderID=orderID,
                    itemID=i,
                    item=random.choice(["ball", "bat", "plate", "glass"]),
                )
            )
        await asyncio.sleep(0)

@adapter.reaction(Packed)
async def packed(msg):
    """Handles packed items by logging their status."""
    logger.info(f"Order {msg['orderID']} item {msg['itemID']} packed with status: {msg['status']}")
    return msg

if __name__ == "__main__":
    logger.info("Starting Merchant...")
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Merchant interrupted by user")
    except SystemExit as e:
        logger.info(f"✅ Merchant shutting down gracefully: {e}")
        print("✅ Merchant shutting down gracefully")
    except NameError as e:
        # Expected error during BSPL shutdown - connection_lost callback tries to access adapter
        # This happens after protocol completion and doesn't affect functionality
        if "adapter" in str(e):
            logger.debug(f"Expected cleanup error during shutdown: {e}")
        else:
            raise
    except Exception as e:
        logger.error(f"❌ Merchant error: {type(e).__name__}: {e}")
        print(f"❌ Merchant error: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
