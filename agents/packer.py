"""
This agent combines wrapped items with their labels to create the final package.
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from configuration import systems, agents
from Logistics import Packed, Packer
from lib import setup_logging

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
logger.setLevel(logging.INFO)

@adapter.enabled(Packed)
async def pack(msg):
    """Handles enabled Packed messages by setting their status."""
    msg["status"] = "packed"
    logger.info(f"Order {msg['orderID']} item {msg['itemID']} packed with wrapping {msg['wrapping']} and label {msg['label']}")
    return msg

if __name__ == "__main__":
    logger.info("Starting Packer...")
    adapter.start()
