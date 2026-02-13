#!/usr/bin/env python3
"""
Termination Condition Manager - Generate and track termination conditions from detected events.

When an external event is detected, this module generates a corresponding termination condition
that specifies when the protocol transaction should be considered complete.

The termination condition file tracks:
1. Event metadata (what the user requested)
2. Required protocol messages to satisfy the request
3. Current progress toward completion
4. Termination criteria based on protocol completion rules
"""

import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


def get_termination_condition_file() -> Path:
    """
    Get the path to the termination condition file.
    
    This file tracks what conditions must be satisfied for the transaction to complete.
    """
    return Path(tempfile.gettempdir()) / "maf_termination_conditions.json"


def get_termination_history_file() -> Path:
    """
    Get the path to the termination history log file.
    
    This file maintains a detailed log of all termination condition updates.
    """
    return Path(tempfile.gettempdir()) / "maf_termination_history.json"


def _load_termination_conditions() -> Dict[str, Any]:
    """Load existing termination conditions from file."""
    condition_file = get_termination_condition_file()
    if condition_file.exists():
        try:
            with open(condition_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {"conditions": [], "metadata": {}}
    return {"conditions": [], "metadata": {}}


def _load_termination_history() -> List[Dict[str, Any]]:
    """Load existing termination history from file."""
    history_file = get_termination_history_file()
    if history_file.exists():
        try:
            with open(history_file, 'r') as f:
                data = json.load(f)
                return data.get("history", [])
        except Exception:
            return []
    return []


def generate_termination_condition_from_event(
    event_message: str,
    event_metadata: Dict[str, Any],
    protocol_name: str,
    completion_rules: Dict[tuple, tuple]
) -> Dict[str, Any]:
    """
    Generate a termination condition based on a detected event.
    
    Args:
        event_message: Human-readable event description (e.g., "Purchase request: Buy a bat")
        event_metadata: Event metadata dict (e.g., {"item": "bat", "budget": 29.99, ...})
        protocol_name: Name of the protocol handling this event
        completion_rules: Dict mapping (protocol, role) -> (message_type, direction, count)
    
    Returns:
        Dict representing the termination condition with:
        - event_description: What the user requested
        - event_metadata: Additional event data
        - protocol: The protocol handling this request
        - required_messages: List of messages required for completion by each role
        - termination_criteria: Specific conditions that mark completion
        - created_at: Timestamp when this condition was created
    """
    
    # Extract event details
    item_count = 1  # Default: assume single item unless metadata specifies otherwise
    if "quantity" in event_metadata:
        item_count = int(event_metadata.get("quantity", 1))
    elif "items" in event_metadata:
        item_count = len(event_metadata["items"]) if isinstance(event_metadata["items"], list) else 1
    
    # Build required messages list based on completion rules for this protocol
    required_messages = []
    termination_criteria = []
    
    for (proto, role), rule in completion_rules.items():
        if proto.lower() == protocol_name.lower():
            msg_type, direction, count = rule[0], rule[1], rule[2]
            
            # Adjust count based on item count
            effective_count = count * item_count
            
            required_msg = {
                "role": role,
                "message_type": msg_type,
                "direction": direction,
                "required_count": effective_count,
                "current_count": 0
            }
            required_messages.append(required_msg)
            
            # Create termination criteria statement
            criteria = f"{role} must {direction} {msg_type} message {effective_count} time(s)"
            termination_criteria.append(criteria)
    
    # Construct termination condition
    condition = {
        "id": f"{protocol_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "event_description": event_message,
        "event_metadata": event_metadata,
        "protocol": protocol_name,
        "item_count": item_count,
        "required_messages": required_messages,
        "termination_criteria": termination_criteria,
        "completion_status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    return condition


def create_or_update_termination_condition(
    event_message: str,
    event_metadata: Dict[str, Any],
    protocol_name: str,
    completion_rules: Dict[tuple, tuple],
    agent_identity: str = "unknown"
) -> bool:
    """
    Create or update the termination condition file when a new event is detected.
    
    Args:
        event_message: Human-readable event description
        event_metadata: Event metadata dict
        protocol_name: Name of the protocol
        completion_rules: Protocol completion rules dict
        agent_identity: Identity of the agent processing this event
    
    Returns:
        bool: True if successfully created/updated, False on error
    """
    try:
        # Generate the new condition
        new_condition = generate_termination_condition_from_event(
            event_message,
            event_metadata,
            protocol_name,
            completion_rules
        )
        
        # Load existing conditions
        conditions_data = _load_termination_conditions()
        
        # Add new condition to list
        conditions_data["conditions"].append(new_condition)
        
        # Update metadata
        conditions_data["metadata"] = {
            "last_updated": datetime.now().isoformat(),
            "agent": agent_identity,
            "protocol": protocol_name,
            "total_conditions": len(conditions_data["conditions"]),
            "pending_count": len([c for c in conditions_data["conditions"] if c["completion_status"] == "pending"])
        }
        
        # Write termination conditions file
        condition_file = get_termination_condition_file()
        with open(condition_file, 'w') as f:
            json.dump(conditions_data, f, indent=2)
        
        # Record in history
        _record_to_history({
            "action": "condition_created",
            "condition_id": new_condition["id"],
            "event": event_message,
            "protocol": protocol_name,
            "timestamp": datetime.now().isoformat()
        })
        
        return True
        
    except Exception as e:
        print(f"Error creating/updating termination condition: {e}")
        return False


def update_termination_condition_progress(
    condition_id: str,
    role: str,
    message_type: str,
    new_count: int
) -> bool:
    """
    Update the progress of a termination condition when messages are received.
    
    Args:
        condition_id: ID of the condition to update
        role: Role that received the message
        message_type: Type of message received
        new_count: New count of this message type
    
    Returns:
        bool: True if updated successfully, False if condition not found
    """
    try:
        conditions_data = _load_termination_conditions()
        
        # Find and update the condition
        for condition in conditions_data["conditions"]:
            if condition["id"] == condition_id:
                # Update message count
                for msg in condition["required_messages"]:
                    if msg["role"].lower() == role.lower() and \
                       msg["message_type"].lower() == message_type.lower():
                        msg["current_count"] = new_count
                        
                        # Check if this condition is complete
                        if _is_condition_complete(condition):
                            condition["completion_status"] = "complete"
                
                condition["updated_at"] = datetime.now().isoformat()
                
                # Write back to file
                condition_file = get_termination_condition_file()
                with open(condition_file, 'w') as f:
                    json.dump(conditions_data, f, indent=2)
                
                # Record update in history
                _record_to_history({
                    "action": "progress_update",
                    "condition_id": condition_id,
                    "role": role,
                    "message_type": message_type,
                    "count": new_count,
                    "timestamp": datetime.now().isoformat()
                })
                
                return True
        
        return False
        
    except Exception as e:
        print(f"Error updating termination condition progress: {e}")
        return False


def _is_condition_complete(condition: Dict[str, Any]) -> bool:
    """
    Check if all requirements of a termination condition have been met.
    
    Args:
        condition: The condition dict to check
    
    Returns:
        bool: True if all requirements are satisfied
    """
    for msg in condition["required_messages"]:
        if msg["current_count"] < msg["required_count"]:
            return False
    return True


def get_active_termination_conditions() -> List[Dict[str, Any]]:
    """
    Get all active (non-completed) termination conditions.
    
    Returns:
        List of condition dicts with status == "pending"
    """
    conditions_data = _load_termination_conditions()
    return [c for c in conditions_data["conditions"] if c["completion_status"] == "pending"]


def get_termination_condition_summary() -> Dict[str, Any]:
    """
    Get a summary of current termination conditions.
    
    Returns:
        Dict with:
        - total_conditions: Total number of termination conditions
        - pending: Number of pending conditions
        - completed: Number of completed conditions
        - conditions: List of pending condition summaries
    """
    conditions_data = _load_termination_conditions()
    conditions = conditions_data["conditions"]
    
    pending = [c for c in conditions if c["completion_status"] == "pending"]
    completed = [c for c in conditions if c["completion_status"] == "complete"]
    
    pending_summaries = []
    for c in pending:
        summary = {
            "id": c["id"],
            "event": c["event_description"],
            "protocol": c["protocol"],
            "item_count": c["item_count"],
            "progress": []
        }
        
        # Calculate progress per message type
        for msg in c["required_messages"]:
            progress_pct = int((msg["current_count"] / msg["required_count"]) * 100) if msg["required_count"] > 0 else 0
            summary["progress"].append({
                "role": msg["role"],
                "message": msg["message_type"],
                "progress": f"{msg['current_count']}/{msg['required_count']} ({progress_pct}%)"
            })
        
        pending_summaries.append(summary)
    
    return {
        "total_conditions": len(conditions),
        "pending": len(pending),
        "completed": len(completed),
        "conditions": pending_summaries
    }


def _record_to_history(entry: Dict[str, Any]) -> None:
    """
    Record an event to the termination history log.
    
    Args:
        entry: Event dict to record
    """
    try:
        history = _load_termination_history()
        history.append(entry)
        
        history_file = get_termination_history_file()
        with open(history_file, 'w') as f:
            json.dump({"history": history}, f, indent=2)
    except Exception:
        pass  # Silent fail for history logging


def reset_termination_conditions() -> bool:
    """
    Clear all termination conditions and history.
    Useful for test teardown or starting fresh.
    
    Returns:
        bool: True if successfully reset
    """
    try:
        condition_file = get_termination_condition_file()
        history_file = get_termination_history_file()
        
        with open(condition_file, 'w') as f:
            json.dump({"conditions": [], "metadata": {}}, f)
        
        with open(history_file, 'w') as f:
            json.dump({"history": []}, f)
        
        return True
    except Exception:
        return False
