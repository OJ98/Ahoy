#!/usr/bin/env python3
"""
Event Injector: Interface for external systems to inject custom events into running agents.

External systems (e.g., inventory management, market data feeds) can use this module
to inject events into agent event queues without modifying agent code.

This uses a file-based queue to communicate across processes (similar to stop signal).

Usage:
    from lib.event_injector import post_event_to_agent
    
    # Inject an event
    post_event_to_agent(event_type="user_defined", 
                       message="Purchase request: Buy a bat", 
                       priority="high",
                       metadata={"item": "bat", "delivery_address": "...", "budget": 29.99},
                       protocol_name="Purchase",
                       role="Buyer")
"""

import json
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

# Define completion rules for known protocols
# Maps (protocol_name, role_name) -> (message_type, direction, count)
COMPLETION_RULES = {
    ("Purchase", "Buyer"): ("completed", "send", 1),
    ("Purchase", "Seller"): ("completed", "send", 1),
    ("Purchase", "Shipper"): ("completed", "send", 1),
    ("CreditPurchase", "CreditBuyer"): ("completed", "send", 1),
    ("CreditPurchase", "CreditSeller"): ("completed", "send", 1),
    ("CreditPurchase", "CreditShipper"): ("completed", "send", 1),
    ("Logistics", "Merchant"): ("Packed", "receive", 1),
    ("Logistics", "Wrapper"): ("Wrapped", "receive", 1),
    ("Logistics", "Labeler"): ("Labeled", "receive", 1),
    ("Logistics", "Packer"): ("Packed", "send", 1),
}


def get_agent_event_queue():
    """
    Get the event queue file path for agents.
    
    This is file-based, not an in-memory queue, to work across processes.
    Returns the path where agents should read events from.
    """
    return Path(tempfile.gettempdir()) / "maf_events_queue.json"


def _load_event_queue_file() -> Dict[str, Any]:
    """Load the event queue from file."""
    queue_file = get_agent_event_queue()
    if queue_file.exists():
        try:
            with open(queue_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {"events": []}
    return {"events": []}


def post_event_to_agent(
    event_type: str,
    message: str,
    priority: str = "normal",
    metadata: Optional[Dict[str, Any]] = None,
    protocol_name: Optional[str] = None,
    role: Optional[str] = None
) -> bool:
    """
    Post a custom event to the agent's event queue (file-based).
    
    If protocol_name and role are provided, also creates a corresponding
    termination condition to track when the protocol transaction completes.
    
    Args:
        event_type: Type of event (e.g., 'user_defined')
        message: Human-readable description of the event
        priority: Event priority ('low', 'normal', 'high')
        metadata: Optional dict of additional context
        protocol_name: Optional protocol name (e.g., 'Purchase') for termination tracking
        role: Optional role name for termination tracking
    
    Returns:
        bool: True if event posted successfully, False on error
    """
    try:
        import sys
        queue_file = get_agent_event_queue()
        print(f"[EventInjector] Attempting to post event to {queue_file}", file=sys.stderr, flush=True)
        
        # Load existing queue
        queue_data = _load_event_queue_file()
        print(f"[EventInjector] Loaded queue with {len(queue_data.get('events', []))} existing events", file=sys.stderr, flush=True)
        
        # Create event
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "message": message,
            "priority": priority,
            "metadata": metadata or {}
        }
        
        # Add to queue
        queue_data["events"].append(event)
        print(f"[EventInjector] Added event, queue now has {len(queue_data['events'])} events", file=sys.stderr, flush=True)
        
        # Write back to file with explicit flush
        with open(queue_file, 'w') as f:
            json.dump(queue_data, f)
            f.flush()  # Explicit flush
        
        # Verify file was written
        verify_data = _load_event_queue_file()
        print(f"[EventInjector] Verified: queue file now has {len(verify_data.get('events', []))} events", file=sys.stderr, flush=True)
        
        # Create termination condition if protocol and role are provided
        if protocol_name and role:
            try:
                from lib.termination_condition_manager import create_or_update_termination_condition
                
                # Build completion rules dict for this protocol
                completion_rules = {
                    k: v for k, v in COMPLETION_RULES.items()
                    if k[0] == protocol_name
                }
                
                if completion_rules:
                    created = create_or_update_termination_condition(
                        event_message=message,
                        event_metadata=metadata or {},
                        protocol_name=protocol_name,
                        completion_rules=completion_rules,
                        agent_identity=role
                    )
                    if created:
                        print(f"[EventInjector] Created termination condition for {protocol_name}", file=sys.stderr, flush=True)
                    else:
                        print(f"[EventInjector] Failed to create termination condition", file=sys.stderr, flush=True)
                else:
                    print(f"[EventInjector] No completion rules found for protocol {protocol_name}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[EventInjector] Error creating termination condition: {e}", file=sys.stderr, flush=True)
        
        return True
        
    except Exception as e:
        print(f"Error posting event to agent: {e}")
        return False


def get_event_queue_summary() -> Optional[Dict[str, Any]]:
    """
    Get summary statistics of the agent's event queue (file-based).
    
    Returns:
        dict with keys: pending_count, total_events
        or None if queue file not available
    """
    try:
        queue_data = _load_event_queue_file()
        events = queue_data.get("events", [])
        return {
            "pending_count": len(events),
            "total_events": len(events)
        }
    except Exception:
        return None


def drain_event_queue() -> int:
    """
    Remove all pending events from the queue without processing them.
    Useful for test teardown.
    
    Returns:
        Number of events drained
    """
    try:
        queue_file = get_agent_event_queue()
        if queue_file.exists():
            queue_data = _load_event_queue_file()
            count = len(queue_data.get("events", []))
            # Clear the queue
            with open(queue_file, 'w') as f:
                json.dump({"events": []}, f)
            return count
    except Exception:
        pass
    return 0


def remove_handled_events(event_ids: list) -> int:
    """
    Remove specific events from the queue after they've been handled.
    
    Events are identified by their timestamp (used as unique ID).
    This allows selective removal of only the events that were processed
    by the LLM, while keeping others in the queue for future processing.
    
    Args:
        event_ids: List of event timestamp IDs to remove
    
    Returns:
        Number of events removed
    """
    if not event_ids:
        return 0
    
    try:
        queue_file = get_agent_event_queue()
        if queue_file.exists():
            queue_data = _load_event_queue_file()
            events = queue_data.get("events", [])
            
            # Filter out events that match the provided IDs
            # event_ids are timestamps (floats) from the event's 'timestamp' field
            original_count = len(events)
            filtered_events = [
                evt for evt in events 
                if evt.get('timestamp') not in event_ids
            ]
            
            removed_count = original_count - len(filtered_events)
            
            # Write back the filtered events
            if removed_count > 0:
                with open(queue_file, 'w') as f:
                    json.dump({"events": filtered_events}, f)
            
            return removed_count
    except Exception as e:
        # Silently fail - don't crash if event removal fails
        pass
    return 0
