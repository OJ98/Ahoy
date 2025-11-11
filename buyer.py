#!/usr/bin/env python3

import uuid, random, asyncio, os
import sys
from io import StringIO, TextIOWrapper
from datetime import datetime

# Ensure UTF-8 encoding for stdout on Windows
if sys.platform == 'win32':
    sys.stdout = TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import systems, agents
import bspl.adapter.receiver as _recv

# Import the protocol
import Purchase
from Purchase import Buyer, rfq, quote, accept, reject, deliver

# Import the LLM Interface
from llm_helper import LLMClient, MockLLMClient, AnthropicLLMClient, choose_and_bind

# Console output capture class
class ConsoleTee:
    """Captures stdout to both console and a file."""
    def __init__(self, filename):
        self.filename = filename
        self.terminal = sys.stdout
        self.file = None
        self._open_file()
    
    def _open_file(self):
        """Open or create the log file."""
        try:
            self.file = open(self.filename, 'a', encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not open log file {self.filename}: {e}")
            self.file = None
    
    def write(self, message):
        """Write to both terminal and file."""
        try:
            # Try to write to terminal; if it fails due to encoding, use 'replace' error handler
            self.terminal.write(message)
        except UnicodeEncodeError:
            # Fall back to encoding with error handling for terminal output
            self.terminal.write(message.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
        
        if self.file:
            try:
                self.file.write(message)
                self.file.flush()
            except Exception:
                pass
    
    def flush(self):
        """Flush both terminal and file."""
        self.terminal.flush()
        if self.file:
            try:
                self.file.flush()
            except Exception:
                pass
    
    def close(self):
        """Close the log file."""
        if self.file:
            try:
                self.file.close()
            except Exception:
                pass

# Set global timeout
TIMEOUT = 30.0

# Instantiate console tee for output capture
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"./logs/buyer_console_{timestamp}.log"
console_tee = ConsoleTee(log_filename)
sys.stdout = console_tee


# Instantiate the adapter for the Buyer role
adapter = Adapter(Buyer, systems, agents, color=COLORS[0])
_recv.adapter = adapter

# Instantiate the mock LLM client for testing
llm_client: LLMClient = AnthropicLLMClient()
#llm_client: LLMClient = MockLLMClient()

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

# Print the event in a readable form
def print_event_debug(event):
    """
    Print event object in a readable form with set contents if applicable.
    Handles both dict and object event types.
    """
    try:
        import json
        print("=" * 50)
        print("LLM Decision Event Debug Info:")
        print(f"Event Type: {type(event).__name__}")
        print(f"Event Module: {type(event).__module__}")
        
        if isinstance(event, dict):
            print(f"Event Content (dict):")
            # Special handling for set values
            formatted_event = {}
            for key, value in event.items():
                if isinstance(value, set):
                    # Convert set items to their string representations
                    set_items = [str(item) for item in value]
                    formatted_event[key] = f"<set with {len(value)} items>: {set_items}"
                else:
                    formatted_event[key] = value
            print(json.dumps(formatted_event, indent=2, default=str))
        else:
            print(f"Event Content (object):")
            print(f"  String Repr: {event}")
            if hasattr(event, "__dict__"):
                event_dict = {k: v for k, v in event.__dict__.items() if not k.startswith('_')}
                # Special handling for set values in attributes
                for key, value in event_dict.items():
                    if isinstance(value, set):
                        # Convert set items to their string representations
                        set_items = [str(item) for item in value]
                        event_dict[key] = f"<set with {len(value)} items>: {set_items}"
                print(f"  Public Attributes:")
                print(json.dumps(event_dict, indent=4, default=str))
            # List all non-private attributes
            attrs = [attr for attr in dir(event) if not attr.startswith('_')]
            if attrs:
                print(f"  Available Methods/Properties: {attrs}")
        print("=" * 50)
    except Exception as e:
        # defensive: printing should never crash the handler
        print(f"Error printing event: {e}")
        import traceback
        traceback.print_exc()


# Decision handler registered with the Adapter decision decorator
# Trigger on any enabled change (added or removed)
@adapter.decision()
async def llm_decision(enabled_store, event):
    """
    Ask LLM to choose an enabled message on any enabled-set change.
    Re-validate the chosen Partial is still present in the enabled set
    before binding and returning the instance.
    """
    # Debug: print the incoming event in readable form
    print_event_debug(event)
    
    # Determine if an event is observed
    has_observed = False
    if isinstance(event, dict):
        has_observed = 'observations' in event
    else:
        has_observed = False

    # If there's no meaningful change, skip the decision
    if has_observed:
        print("LLM decision invoked due to message observed.")
    else:    
        return None
    
    # Call LLM to choose message and bind parameters
    instance = await choose_and_bind(adapter=adapter, enabled_store=enabled_store, event=event, client=llm_client, timeout=TIMEOUT)
    if instance is None:
        return None

    # Extra safety: ensure the underlying partial that produced `instance` is still enabled.
    # Compare by schema + key projection (keys that define matching contexts).
    chosen_schema = instance.schema

    # Check whether enabled_store still contains a matching partial/context
    still_enabled = False
    with open("enabled_store_output.txt", "a") as f:
        f.write(str(enabled_store) + "\n")
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
    try:
        async def _runner():
            await asyncio.gather(main(), _shutdown_watcher(adapter))

        adapter.start(_runner())
        print(
            f"Completed enactments: {rejections + deliveries} "
            + f"({rejections} rejections, {deliveries} deliveries)"
        )
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C pressed. Shutting down gracefully...")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[INFO] Console output saved to: {log_filename}")
        console_tee.close()
        sys.stdout = sys.__stdout__  # Restore original stdout
