#!/usr/bin/env python3

import random, os, asyncio
from bspl.adapter import Adapter
from configuration import systems, agents
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Shipper, deliver

# Instantiate the adapter for the Shipper role
adapter = Adapter(Shipper, systems, agents)
_recv.adapter = adapter


@adapter.enabled(deliver)
async def deliver_item(msg):
    msg["outcome"] = "delivered"
    print(f"Delivered item for order ID {msg['ID']}")
    return msg


async def _shutdown_watcher(adapter, stop_path=".stop_signal"):
    while True:
        if os.path.exists(stop_path):
            try:
                for r in getattr(adapter, "receivers", []):
                    if hasattr(r, "stop"):
                        await r.stop()
                if hasattr(adapter.emitter, "stop"):
                    await adapter.emitter.stop()
            except Exception as e:
                adapter.warning(f"Error during shutdown: {e}")
            adapter.running = False
            break
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    adapter.start(_shutdown_watcher(adapter))
