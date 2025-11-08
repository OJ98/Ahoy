#!/usr/bin/env python3

import random, logging, os, asyncio
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Seller, quote, ship

# Instantiate the adapter for the Seller role
adapter = Adapter(Seller, systems, agents, color=COLORS[1])
_recv.adapter = adapter 

@adapter.enabled(quote)
async def send_quote(msg):
    msg["price"] = random.randint(0, 100)
    return msg


@adapter.enabled(ship)
async def send_ship(msg):
    msg["shipped"] = True
    print(f"Shipping item for order ID {msg['ID']}")
    return msg


async def _shutdown_watcher(adapter, stop_path=".stop_signal"):
    """Watch for a filesystem stop file and gracefully stop adapter when present."""
    while True:
        if os.path.exists(stop_path):
            # attempt graceful shutdown: stop receivers and emitter
            try:
                for r in getattr(adapter, "receivers", []):
                    if hasattr(r, "stop"):
                        await r.stop()
                if hasattr(adapter.emitter, "stop"):
                    await adapter.emitter.stop()
            except Exception as e:
                adapter.warning(f"Error during shutdown: {e}")
            # mark adapter not running
            adapter.running = False
            break
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    # Start adapter and the shutdown watcher so processes can exit cleanly
    adapter.start(_shutdown_watcher(adapter))
