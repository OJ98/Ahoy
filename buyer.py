#!/usr/bin/env python3

import uuid, random, asyncio, os
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Buyer, rfq, quote, accept, reject, deliver

# Import the LLM Interface
from llm_helper import LLMClient, MockLLMClient, choose_and_bind


# Instantiate the adapter for the Buyer role
adapter = Adapter(Buyer, systems, agents, color=COLORS[0])
_recv.adapter = adapter

# Instantiate the mock LLM client for testing
llm_client: LLMClient = MockLLMClient('{"choice": null, "params": {}}')

deliveries = 0
rejections = 0

async def main():
    for i in range(10):
        msg = rfq(ID=str(uuid.uuid4()), item=random.sample(["ball", "bat"], 1)[0])
        await adapter.send(msg)
        await asyncio.sleep(0.1)


@adapter.reaction(quote)
async def decision(msg):
    if msg["price"] < 50:
        await adapter.send(accept(**msg.payload, address="Home", resp="Accept"))
    else:
        msg = reject(**msg.payload, outcome="Rejected", resp="Reject")
        print(msg)
        global rejections
        rejections += 1
        await adapter.send(msg)


@adapter.reaction(deliver)
async def receive(msg):
    global deliveries
    deliveries += 1
    print(msg)


# Decision handler registered with the Adapter decision decorator
# Trigger on any enabled change (added or removed)
@adapter.decision(filter=lambda e: (
    (isinstance(e, dict) and (bool(e.get("added")) or bool(e.get("removed")) or bool(e.get("observations"))))
    or (not isinstance(e, dict) and (bool(getattr(e, "added", None)) or bool(getattr(e, "removed", None)) or bool(getattr(e, "observations", None))))
))
async def llm_decision(enabled_store, event):
    """
    Ask LLM to choose an enabled message on any enabled-set change.
    Re-validate the chosen Partial is still present in the enabled set
    before binding and returning the instance.
    """
    # Debug: print the incoming event
    try:
        print("llm_decision invoked; event type:", type(event), "event:", event)
    except Exception:
        # defensive: printing should never crash the handler
        pass

    # Normalize/check event for added/removed info in a tolerant way.
    has_added = False
    has_removed = False
    if isinstance(event, dict):
        has_added = bool(event.get("added"))
        has_removed = bool(event.get("removed"))
    else:
        # Some adapters send an object with attributes instead of a dict
        try:
            has_added = bool(getattr(event, "added", None))
            has_removed = bool(getattr(event, "removed", None))
        except Exception:
            has_added = False
            has_removed = False

    # If there's no meaningful change, skip the decision
    if not (has_added or has_removed):
        return None
    print("LLM decision invoked due to enabled set change.")
    timeout = 4.0
    
    
    # Call LLM to choose message and bind parameters
    instance = await choose_and_bind(adapter, enabled_store, event, llm_client, timeout=timeout)
    if instance is None:
        return None

    # Extra safety: ensure the underlying partial that produced `instance` is still enabled.
    # Compare by schema + key projection (keys that define matching contexts).
    chosen_schema = instance.schema

    # Check whether enabled_store still contains a matching partial/context
    still_enabled = False
    for p in enabled_store.messages():
        # p is a Partial; compare projected key against instance key
        # create a temporary instance with p.bindings filled to check key projection
        try:
            # p.bindings may contain None; project only keys present in schema
            projected = {k: p.bindings.get(k) for k in chosen_schema.keys}
            # Only consider p if it has the same schema
            if p.schema == chosen_schema:
                # if all key values exist and match the instance's key values
                matches = all((projected.get(k) is not None) and (projected.get(k) == instance.payload.get(k)) for k in chosen_schema.keys)
                if matches:
                    still_enabled = True
                    break
        except Exception:
            continue

    if not still_enabled:
        adapter.logger and adapter.logger.info("Chosen option no longer enabled; skipping")
        return None

    # Final precaution: adapter.send() will run protocol checks; returning instance is fine.
    return instance


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

# Add decision handler for user events.

if __name__ == "__main__":
    async def _runner():
        await asyncio.gather(main(), _shutdown_watcher(adapter))

    adapter.start(_runner())
    print(
        f"Completed enactments: {rejections + deliveries} "
        + f"({rejections} rejections, {deliveries} deliveries)"
    )
