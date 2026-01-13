"""
This agent generates unique labels for orders upon request.
"""

import logging
import uuid
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bspl.adapter import Adapter
from configuration import systems, agents
from Logistics import Labeled, RequestLabel, Labeler
from lib import setup_logging

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

@adapter.reaction(RequestLabel)
async def label(msg):
    """Handles label requests by generating a unique UUID-based label."""
    label = str(uuid.uuid4())
    logger.info(f"Generated label {label} for order {msg['orderID']}")
    await adapter.send(Labeled(label=label, **msg.payload))
    return msg

if __name__ == "__main__":
    logger.info("Starting Labeler...")
    adapter.start()
