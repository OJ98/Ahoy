#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uuid, random, asyncio
import tempfile
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
from lib.utils import shutdown_watcher

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "maf_stop_signal.txt"

import NetBill
from NetBill import Customer, rfq, offer, accept, goods, pay, receipt

adapter = Adapter(Customer, systems, agents, color=COLORS[0])

transactions = 0
rejections = 0


async def main():
    for i in range(10):
        msg = rfq(ID=str(uuid.uuid4()), item=random.sample(["book", "electronic", "stationery"], 1)[0])
        await adapter.send(msg)
        await asyncio.sleep(0.1)


@adapter.reaction(offer)
async def receive_offer(msg):
    """Receive price quote from merchant and decide whether to accept."""
    if msg["price"] < 100:
        await adapter.send(accept(**msg.payload, confirmation="confirmed"))
    else:
        # Don't respond to expensive offers
        global rejections
        rejections += 1


@adapter.reaction(goods)
async def receive_goods(msg):
    """Receive goods from merchant and send payment."""
    await adapter.send(pay(**msg.payload, payment="paid"))


@adapter.reaction(receipt)
async def receive_receipt(msg):
    """Receive final receipt from merchant."""
    global transactions
    transactions += 1


if __name__ == "__main__":
    try:
        adapter.start(shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH)))
    except KeyboardInterrupt:
        print("\n⏹ Customer interrupted by user")
    except SystemExit:
        print("✅ Customer shutting down gracefully")
    except Exception as e:
        print(f"❌ Customer error: {e}")
    print(
        f"Completed transactions: {transactions} "
        + f"({rejections} rejected offers)"
    )
