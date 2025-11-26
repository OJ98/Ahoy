#!/usr/bin/env python3

import random, os, asyncio
from bspl.adapter import Adapter
from configuration import systems, agents
from lib.utils import shutdown_watcher
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Shipper, deliver

# Instantiate the adapter for the Shipper role
adapter = Adapter(Shipper, systems, agents)
_recv.adapter = adapter


@adapter.enabled(deliver)
async def deliver_item(msg):
    """Mark item as delivered."""
    msg.bindings["outcome"] = "delivered"
    import sys
    print(f"[SHIPPER] Delivered: ID={msg.bindings.get('ID')}, item='{msg.bindings.get('item')}', address={msg.bindings.get('address')}", file=sys.stderr)
    return msg


if __name__ == "__main__":
    adapter.start(shutdown_watcher(adapter))
