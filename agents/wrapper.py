"""
This agent handles wrapping requests by choosing appropriate wrapping material based on item type.
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
from Logistics import Wrapped, RequestWrapping, Wrapper
from lib import setup_logging
from lib.utils import shutdown_watcher

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize logging system
# Use fixed filename (no timestamp) so logs are overwritten each run
log_filename = str(LOG_DIR / "wrapper.log")

debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger."""
    debug_logger.debug(msg)

adapter = Adapter(Wrapper, systems, agents)

logger = logging.getLogger("wrapper")
logger.setLevel(logging.INFO)

@adapter.reaction(RequestWrapping)
async def wrap(msg):
    """Handles wrapping requests by selecting appropriate material (bubblewrap for fragile items)."""
    wrapping = "bubblewrap" if msg["item"] in ["plate", "glass"] else "paper"
    logger.info(f"Order {msg['orderID']} item {msg['itemID']} ({msg['item']}) wrapped with {wrapping}")
    await adapter.send(
        Wrapped(
            wrapping=wrapping,
            **msg.payload
        )
    )
    return msg

if __name__ == "__main__":
    logger.info("Starting Wrapper...")
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Wrapper interrupted by user")
    except SystemExit as e:
        logger.info(f"✅ Wrapper shutting down gracefully: {e}")
        print("✅ Wrapper shutting down gracefully")
    except NameError as e:
        # Expected error during BSPL shutdown - connection_lost callback tries to access adapter
        # This happens after protocol completion and doesn't affect functionality
        if "adapter" in str(e):
            logger.debug(f"Expected cleanup error during shutdown: {e}")
        else:
            raise
    except Exception as e:
        logger.error(f"❌ Wrapper error: {type(e).__name__}: {e}")
        print(f"❌ Wrapper error: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
