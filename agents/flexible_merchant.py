#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import random
import asyncio
import tempfile
import logging
from datetime import datetime
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.utils import shutdown_watcher
from lib import setup_logging

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = str(LOG_DIR / "flexible_merchant.log")
debug_logger, console_logger = setup_logging(log_filename, mode='w')

def log_debug(msg):
    """Log to debug logger (with timestamp added by formatter) and console."""
    debug_logger.debug(msg)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] MERCHANT: {msg}", flush=True)

# Import the protocol
import FlexiblePurchase
from FlexiblePurchase import FlexibleMerchant, rfq, offer, accept, standard_delivery_request, standard_delivery, express_delivery_request, express_delivery, pay_express, pay_standard, receipt

log_debug("Initializing FlexibleMerchant adapter...")
adapter = Adapter(FlexibleMerchant, systems, agents, color=COLORS[1])
log_debug(f"Adapter created: {adapter}")
log_debug(f"Adapter roles: {adapter.roles}")

quotes_sent = 0
orders_completed = 0
# Track transaction info per ID for sending proper receipt
transaction_tracker = {}  # {ID: {"item": ..., "price": ...}}


@adapter.reaction(rfq)
async def handle_rfq(msg):
    """React to RFQs by sending price quote."""
    global quotes_sent
    quotes_sent += 1
    
    item = msg["item"].lower()
    ID = msg["ID"]
    
    log_debug(f"[RFQ] Received RFQ from FlexibleCustomer")
    log_debug(f"[RFQ]   ID: {ID}, item: {item}")
    
    # Simple pricing strategy based on item type
    if "book" in item:
        price = random.randint(10, 25)
    elif "pen" in item:
        price = random.randint(2, 5)
    elif "phone" in item:
        price = random.randint(200, 600)
    else:
        price = random.randint(20, 100)
    
    # Store transaction info for later use in receipt
    transaction_tracker[ID] = {
        "item": msg["item"],  # Store original capitalization
        "price": price
    }
    
    log_debug(f"[RFQ] Generating quote: ${price}")
    
    try:
        await adapter.send(
            offer(
                ID=ID,
                item=msg["item"],
                price=price
            )
        )
        log_debug(f"[RFQ] ✓ Sent offer message (quote #{quotes_sent})")
    except Exception as e:
        log_debug(f"[RFQ] ✗ ERROR sending offer: {e}")
        import traceback
        log_debug(traceback.format_exc())


@adapter.reaction(accept)
async def handle_accept(msg):
    """React to accepted offers - customer can now request delivery options."""
    ID = msg["ID"]
    log_debug(f"[ACCEPT] Received acceptance from FlexibleCustomer")
    log_debug(f"[ACCEPT]   ID: {ID}, item: {msg['item']}, price: {msg['price']}")
    # No response needed - customer can now request delivery options


@adapter.reaction(standard_delivery_request)
async def handle_standard_delivery_request(msg):
    """React to standard delivery requests."""
    ID = msg["ID"]
    log_debug(f"[STD_DELIVERY] Received standard delivery request")
    log_debug(f"[STD_DELIVERY]   ID: {ID}, item: {msg['item']}")
    
    try:
        await adapter.send(
            standard_delivery(
                ID=ID,
                item=msg["item"],
                standard_delivery=msg["standard_delivery"]
            )
        )
        log_debug(f"[STD_DELIVERY] ✓ Sent standard delivery confirmation")
    except Exception as e:
        log_debug(f"[STD_DELIVERY] ✗ ERROR sending delivery: {e}")
        import traceback
        log_debug(traceback.format_exc())


@adapter.reaction(express_delivery_request)
async def handle_express_delivery_request(msg):
    """React to express delivery requests."""
    ID = msg["ID"]
    log_debug(f"[EXP_DELIVERY] Received express delivery request")
    log_debug(f"[EXP_DELIVERY]   ID: {ID}, item: {msg['item']}")
    
    try:
        await adapter.send(
            express_delivery(
                ID=ID,
                item=msg["item"],
                express_delivery=msg["express_delivery"]
            )
        )
        log_debug(f"[EXP_DELIVERY] ✓ Sent express delivery confirmation")
    except Exception as e:
        log_debug(f"[EXP_DELIVERY] ✗ ERROR sending delivery: {e}")
        import traceback
        log_debug(traceback.format_exc())


@adapter.reaction(pay_standard)
async def handle_pay(msg):
    """React to standard payment by sending receipt."""
    global orders_completed
    
    ID = msg["ID"]
    payment = msg["payment"]
    log_debug(f"[PAYMENT] Received payment from FlexibleCustomer")
    log_debug(f"[PAYMENT]   ID: {ID}, payment: ${payment}")
    
    try:
        # Retrieve stored item from transaction tracker
        item = transaction_tracker.get(ID, {}).get("item", "unknown")
        
        await adapter.send(
            receipt(
                ID=ID,
                item=item,
                payment=payment,
                done="completed"
            )
        )
        log_debug(f"[PAYMENT] ✓ Sent receipt (order #{orders_completed + 1})")
        orders_completed += 1
        
        # Clean up transaction tracker
        if ID in transaction_tracker:
            del transaction_tracker[ID]
    except Exception as e:
        log_debug(f"[PAYMENT] ✗ ERROR sending receipt: {e}")
        import traceback
        log_debug(traceback.format_exc())

@adapter.reaction(pay_express)
async def handle_pay_express(msg):
    """React to express payment by sending receipt."""
    global orders_completed
    
    ID = msg["ID"]
    payment = msg["payment"]
    log_debug(f"[PAYMENT] Received payment from FlexibleCustomer")
    log_debug(f"[PAYMENT]   ID: {ID}, payment: ${payment}")
    
    try:
        # Retrieve stored item from transaction tracker
        item = transaction_tracker.get(ID, {}).get("item", "unknown")
        
        await adapter.send(
            receipt(
                ID=ID,
                item=item,
                payment=payment,
                done="completed"
            )
        )
        log_debug(f"[PAYMENT] ✓ Sent receipt (order #{orders_completed + 1})")
        orders_completed += 1
        
        # Clean up transaction tracker
        if ID in transaction_tracker:
            del transaction_tracker[ID]
    except Exception as e:
        log_debug(f"[PAYMENT] ✗ ERROR sending receipt: {e}")
        import traceback
        log_debug(traceback.format_exc())



if __name__ == "__main__":
    try:
        log_debug("=" * 70)
        log_debug("FlexibleMerchant agent starting...")
        log_debug("=" * 70)
        log_debug("Stop signal file: " + str(STOP_SIGNAL_PATH))
        log_debug("Waiting for RFQs from FlexibleCustomer...")
        log_debug("=" * 70)
        
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        log_debug("\n⏹ Merchant interrupted by user")
        print("\n⏹ Merchant interrupted by user")
    except SystemExit as e:
        log_debug(f"✅ Merchant shutting down gracefully: {e}")
        print("✅ Merchant shutting down gracefully")
    except NameError as e:
        # Expected error during BSPL shutdown - connection_lost callback tries to access adapter
        # This happens after protocol completion and doesn't affect functionality
        if "adapter" in str(e):
            log_debug(f"Expected cleanup error during shutdown: {e}")
        else:
            raise
    except Exception as e:
        log_debug(f"❌ Merchant error: {e}")
        import traceback
        log_debug(traceback.format_exc())
        print(f"❌ Merchant error: {e}")
    finally:
        log_debug("=" * 70)
        log_debug(f"Completed orders: {orders_completed} (quotes sent: {quotes_sent})")
        log_debug("FlexibleMerchant agent stopped")
        log_debug("=" * 70)
        print(f"Completed orders: {orders_completed} (quotes sent: {quotes_sent})")

