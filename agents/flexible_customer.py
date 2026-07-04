# #!/usr/bin/env python3

# import sys
# from pathlib import Path

# PROJECT_ROOT = Path(__file__).resolve().parent.parent
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# import uuid
# import random
# import asyncio
# import tempfile
# import logging
# from datetime import datetime
# from bspl.adapter import Adapter
# from bspl.adapter.core import COLORS
# from configuration import systems, agents
# from lib.utils import shutdown_watcher, get_log_dir
# from lib import setup_logging

# STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

# LOG_DIR = get_log_dir(PROJECT_ROOT)

# log_filename = str(LOG_DIR / "flexible_customer.log")
# debug_logger, console_logger = setup_logging(log_filename, mode='w')

# def log_debug(msg):
#     """Log to debug logger."""
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
#     debug_logger.debug(msg)
#     print(f"[{timestamp}] CUSTOMER: {msg}", flush=True)

# # Import the protocol
# import FlexiblePurchase
# from FlexiblePurchase import FlexibleCustomer, rfq, offer, accept, standard_delivery_request, standard_delivery, express_delivery_request, express_delivery, pay_express, pay_standard, receipt

# log_debug("Initializing FlexibleCustomer adapter...")
# adapter = Adapter(FlexibleCustomer, systems, agents, color=COLORS[0])
# log_debug(f"Adapter created: {adapter}")
# log_debug(f"Adapter roles: {adapter.roles}")

# requests_sent = 0
# purchases_completed = 0
# # Track pending confirmations and delivery options per transaction ID
# pending_transactions = {}  # {ID: {"item": ..., "price": ..., "confirmation": ..., "standard_delivery": ..., "express_delivery": ...}}


# async def main():
#     """Generate RFQs for random items."""
#     global requests_sent
    
#     # Wait for other agents to start up (hardcoded delay)
#     log_debug("[STARTUP] Waiting 3 seconds for other agents to initialize...")
#     await asyncio.sleep(3)
#     log_debug("[STARTUP] Starting RFQ generation")
    
#     for i in range(5):
#         msg_id = str(uuid.uuid4())
#         item = random.choice(["book", "pen", "phone"])
        
#         log_debug(f"[RFQ] Generating RFQ #{i+1}")
#         log_debug(f"      ID: {msg_id}, item: {item}")
        
#         try:
#             msg = rfq(ID=msg_id, item=item)
#             await adapter.send(msg)
#             requests_sent += 1
#             log_debug(f"[RFQ] ✓ RFQ sent successfully")
#         except Exception as e:
#             log_debug(f"[RFQ] ✗ ERROR sending RFQ: {e}")
#             import traceback
#             log_debug(traceback.format_exc())
        
#         await asyncio.sleep(0.1)


# @adapter.reaction(offer)
# async def handle_offer(msg):
#     """React to price offers - accept if price is reasonable."""
#     msg_id = msg["ID"]
#     item = msg["item"]
#     price = msg["price"]
    
#     log_debug(f"[OFFER] Received price offer from FlexibleMerchant")
#     log_debug(f"        ID: {msg_id}, item: {item}, price: ${price}")
    
#     # Initialize transaction tracking first
#     pending_transactions[msg_id] = {
#         "item": item,
#         "price": price,
#         "confirmation": "confirmed",
#         "standard_delivery": None,
#         "express_delivery": None
#     }
#     log_debug(f"[OFFER] ✓ Initialized transaction tracking for {msg_id}")
    
#     # Always accept offers for now (simple logic)
#     try:
#         await adapter.send(
#             accept(
#                 ID=msg_id,
#                 item=item,
#                 price=price,
#                 confirmation="confirmed"
#             )
#         )
#         log_debug(f"[OFFER] ✓ Sent acceptance/confirmation")
#     except Exception as e:
#         log_debug(f"[OFFER] ✗ ERROR sending acceptance: {e}")
#         import traceback
#         log_debug(traceback.format_exc())




# @adapter.enabled(standard_delivery_request)
# async def send_when_standard_delivery_enabled(msg):
#     """Send standard delivery request when enabled by protocol."""
#     try:
#         # Extract bindings from the enabled message
#         ID = msg.bindings.get("ID")
#         item = msg.bindings.get("item")
#         confirmation = msg.bindings.get("confirmation")
        
#         log_debug(f"[STD_REQ] Sending standard delivery request")
#         log_debug(f"          ID: {ID}, item: {item}")
        
#         await adapter.send(
#             standard_delivery_request(
#                 ID=ID,
#                 item=item,
#                 confirmation=confirmation,
#                 standard_delivery=True
#             )
#         )
#         log_debug(f"[STD_REQ] ✓ Standard delivery request sent")
#     except Exception as e:
#         log_debug(f"[STD_REQ] ✗ ERROR: {e}")
#         import traceback
#         log_debug(traceback.format_exc())


# @adapter.enabled(express_delivery_request)
# async def send_when_express_delivery_enabled(msg):
#     """Send express delivery request when enabled by protocol."""
#     try:
#         # Extract bindings from the enabled message
#         ID = msg.bindings.get("ID")
#         item = msg.bindings.get("item")
#         confirmation = msg.bindings.get("confirmation")
        
#         log_debug(f"[EXP_REQ] Sending express delivery request")
#         log_debug(f"          ID: {ID}, item: {item}")
        
#         await adapter.send(
#             express_delivery_request(
#                 ID=ID,
#                 item=item,
#                 confirmation=confirmation,
#                 express_delivery=True
#             )
#         )
#         log_debug(f"[EXP_REQ] ✓ Express delivery request sent")
#     except Exception as e:
#         log_debug(f"[EXP_REQ] ✗ ERROR: {e}")
#         import traceback
#         log_debug(traceback.format_exc())




# @adapter.reaction(standard_delivery)
# async def handle_standard_delivery(msg):
#     """Receive standard delivery response and check if ready to pay."""
#     msg_id = msg["ID"]
#     log_debug(f"[STD_DELIVERY] Received standard delivery confirmation")
#     log_debug(f"               ID: {msg_id}, item: {msg['item']}, delivery: {msg['standard_delivery']}")
    
#     if msg_id in pending_transactions:
#         pending_transactions[msg_id]["standard_delivery"] = msg["standard_delivery"]
#         await send_payment_when_ready(msg_id)
#     else:
#         log_debug(f"[STD_DELIVERY] ⚠ WARNING: Transaction {msg_id} not tracked")


# @adapter.reaction(express_delivery)
# async def handle_express_delivery(msg):
#     """Receive express delivery response and check if ready to pay."""
#     msg_id = msg["ID"]
#     log_debug(f"[EXP_DELIVERY] Received express delivery confirmation")
#     log_debug(f"               ID: {msg_id}, item: {msg['item']}, delivery: {msg['express_delivery']}")
    
#     if msg_id in pending_transactions:
#         pending_transactions[msg_id]["express_delivery"] = msg["express_delivery"]
#         await send_payment_when_ready(msg_id)
#     else:
#         log_debug(f"[EXP_DELIVERY] ⚠ WARNING: Transaction {msg_id} not tracked")


# async def send_payment_when_ready(msg_id):
#     """Send payment once ANY delivery option is received."""
#     if msg_id not in pending_transactions:
#         return
    
#     txn = pending_transactions[msg_id]
#     log_debug(f"[PAYMENT] Checking readiness for transaction {msg_id}")
#     log_debug(f"          std_delivery={txn['standard_delivery']}, exp_delivery={txn['express_delivery']}")
    
#     # Send payment if ANY delivery option has been confirmed (not waiting for both)
#     # This allows the agent to choose ONE delivery method
#     if txn["standard_delivery"] is not None or txn["express_delivery"] is not None:
#         log_debug(f"[PAYMENT] ✓ Delivery option(s) received, sending payment")
        
#         # Build payment message with whichever delivery options are available
#         payment_kwargs = {
#             "ID": msg_id,
#             "price": txn["price"],
#             "payment": "paid"
#         }
        
#         # Add standard_delivery only if it was requested/confirmed
#         if txn["standard_delivery"] is not None:
#             payment_kwargs["standard_delivery"] = txn["standard_delivery"]
#             try:
#                 await adapter.send(pay_standard(**payment_kwargs))
#                 log_debug(f"[PAYMENT] ✓ Payment sent successfully")
#                 del pending_transactions[msg_id]
#             except Exception as e:
#                 log_debug(f"[PAYMENT] ✗ ERROR sending payment: {e}")
#                 import traceback
#                 log_debug(traceback.format_exc())
#         # Add express_delivery only if it was requested/confirmed
#         if txn["express_delivery"] is not None:
#             payment_kwargs["express_delivery"] = txn["express_delivery"]
#             try:
#                 await adapter.send(pay_express(**payment_kwargs))
#                 log_debug(f"[PAYMENT] ✓ Payment sent successfully")
#                 del pending_transactions[msg_id]
#             except Exception as e:
#                 log_debug(f"[PAYMENT] ✗ ERROR sending payment: {e}")
#                 import traceback
#                 log_debug(traceback.format_exc())
       
#     else:
#         log_debug(f"[PAYMENT] ⏳ Waiting for delivery option...")

# @adapter.reaction(receipt)
# async def handle_receipt(msg):
#     """Receive final receipt and mark purchase complete."""
#     global purchases_completed
#     purchases_completed += 1
    
#     msg_id = msg["ID"]
#     log_debug(f"[RECEIPT] Received final receipt (purchase complete)")
#     log_debug(f"          ID: {msg_id}, item: {msg['item']}, payment: {msg['payment']}, done: {msg['done']}")
#     log_debug(f"[RECEIPT] Purchase #{purchases_completed} completed!")




# if __name__ == "__main__":
#     try:
#         log_debug("=" * 70)
#         log_debug("FlexibleCustomer agent starting...")
#         log_debug("=" * 70)
#         log_debug("Stop signal file: " + str(STOP_SIGNAL_PATH))
#         log_debug("Generating RFQs and waiting for offers...")
#         log_debug("=" * 70)
        
#         adapter.start(
#             main(),
#             shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH))
#         )
#     except KeyboardInterrupt:
#         log_debug("\n⏹ Customer interrupted by user")
#         print("\n⏹ Customer interrupted by user")
#     except SystemExit as e:
#         log_debug(f"✅ Customer shutting down gracefully: {e}")
#         print("✅ Customer shutting down gracefully")
#     except NameError as e:
#         # Expected error during BSPL shutdown - connection_lost callback tries to access adapter
#         # This happens after protocol completion and doesn't affect functionality
#         if "adapter" in str(e):
#             log_debug(f"Expected cleanup error during shutdown: {e}")
#         else:
#             raise
#     except Exception as e:
#         log_debug(f"❌ Customer error: {e}")
#         import traceback
#         log_debug(traceback.format_exc())
#         print(f"❌ Customer error: {e}")
#     finally:
#         log_debug("=" * 70)
#         log_debug(f"Completed purchases: {purchases_completed}")
#         log_debug(f"Pending transactions: {len(pending_transactions)}")
#         log_debug("FlexibleCustomer agent stopped")
#         log_debug("=" * 70)
#         print(f"Completed purchases: {purchases_completed}")

