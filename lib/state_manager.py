#!/usr/bin/env python3
"""
Extract and serialize the social state of BSPL adapters for LLM context.

This module provides utilities to extract, serialize, and deserialize the state of
BSPL protocol adapters, enabling LLMs to understand the current system configuration,
message history, and protocol interactions.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


# ============================================================================
# SERIALIZATION: Convert BSPL objects to JSON-serializable format
# ============================================================================

def _serialize_value(value: Any) -> Any:
    """Convert a Python value to a JSON-serializable format.
    
    Handles primitives, collections, datetime objects, and BSPL domain objects
    by converting them to a serializable format with type information.
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    elif isinstance(value, set):
        return sorted([_serialize_value(v) for v in value], key=str)
    elif hasattr(value, 'name'):
        # BSPL objects (Role, Protocol, etc.) have a 'name' attribute
        return {"__object_type__": value.__class__.__name__, "name": str(value.name)}
    else:
        return str(value)


def _serialize_message(message: Any) -> Dict[str, Any]:
    """Extract message schema, payload, and metadata into a serializable dict."""
    result = {
        "schema_name": message.schema.name,
        "qualified_name": message.schema.qualified_name,
        "payload": _serialize_value(message.payload),
        "key": message.key,
        "meta": _serialize_value(message.meta),
    }
    
    # Safely extract sender and recipients (may not always be available)
    try:
        result["sender"] = message.schema.sender.name if message.schema.sender else None
    except Exception:
        result["sender"] = None
    
    try:
        result["recipients"] = [r.name for r in message.schema.recipients] if message.schema.recipients else []
    except Exception:
        result["recipients"] = []
    
    # Extract message schema parameters
    try:
        result["parameters"] = {
            "ins": sorted(list(message.schema.ins)),
            "outs": sorted(list(message.schema.outs)),
            "nils": sorted(list(message.schema.nils)),
            "keys": sorted(list(message.schema.keys)),
        }
    except Exception:
        result["parameters"] = {}
    
    return result


def _serialize_context(context: Any, system_id: Any = None) -> Dict[str, Any]:
    """Recursively serialize a BSPL context with bindings, messages, and subcontexts."""
    result = {
        "bindings": _serialize_value(context.bindings),
        "messages": [_serialize_message(msg) for msg in context._messages.values()],
        "subcontexts": {}
    }
    
    # Recursively handle nested subcontexts
    for param_name, param_contexts in context.subcontexts.items():
        result["subcontexts"][param_name] = {}
        for param_value, subcontext in param_contexts.items():
            result["subcontexts"][param_name][_serialize_value(param_value)] = _serialize_context(subcontext, system_id)
    
    return result


# ============================================================================
# EXTRACTION: Build social state from adapter
# ============================================================================

def extract_social_state(adapter: Any) -> Dict[str, Any]:
    """Extract complete social state from a BSPL adapter.
    
    Returns a dictionary containing:
    - adapter_name: Name of the adapter role
    - timestamp: When extraction occurred
    - systems: Message history for each system
    - protocols: Protocol names involved
    - roles: Available roles in the system
    - global_message_count: Total message count
    
    IMPORTANT: For multirole adapters, messages are stored ONCE at the top level
    (not duplicated in each system entry) to avoid confusing the LLM with duplicate
    message history. Each system still maintains its own message context if needed.
    """
    # Serialize adapter name (may be a Role object or string)
    adapter_name = adapter.name if hasattr(adapter, 'name') else 'unknown'
    if hasattr(adapter_name, 'name'):
        serialized_name = _serialize_value(adapter_name)
    else:
        serialized_name = adapter_name
    
    result = {
        "adapter_name": serialized_name,
        "timestamp": datetime.now().isoformat(),
        "systems": {},
        "global_message_count": 0,
        "protocols": [],
        "roles": [],
        "all_messages": []  # Initialize at top level
    }
    
    # Extract history from adapter contexts
    # For multirole adapters, extract messages from ALL protocol contexts
    if hasattr(adapter, 'history') and hasattr(adapter.history, 'contexts'):
        all_messages_seen = set()  # Use set to deduplicate by (qualified_name, key)
        all_messages_list = []  # Preserve order
        
        # First, try the top-level history.messages() method which should combine all contexts
        try:
            top_level_messages = list(adapter.history.messages())
            for msg in top_level_messages:
                # Deduplicate by message schema qualified name + key (message instance identifier)
                msg_id = (msg.schema.qualified_name, str(msg.key))
                if msg_id not in all_messages_seen:
                    all_messages_seen.add(msg_id)
                    all_messages_list.append(msg)
        except Exception as e:
            pass
        
        # Fallback: iterate through each protocol context individually
        # This ensures we catch messages even if top-level aggregation fails
        if not all_messages_list:
            try:
                for system_id, context in adapter.history.contexts.items():
                    context_messages = list(context.messages())
                    for msg in context_messages:
                        msg_id = (msg.schema.qualified_name, str(msg.key))
                        if msg_id not in all_messages_seen:
                            all_messages_seen.add(msg_id)
                            all_messages_list.append(msg)
            except Exception as e:
                pass
        
        # Serialize all collected messages
        all_serialized = [_serialize_message(msg) for msg in all_messages_list]
        
        # Store all messages at result level (not duplicated in each system)
        result["all_messages"] = all_serialized
        result["global_message_count"] = len(all_serialized)
        
        # Store per-protocol message counts for debugging
        for system_id, context in adapter.history.contexts.items():
            try:
                context_messages = list(context.messages())
                result["systems"][str(system_id)] = {
                    "message_count": len(context_messages)
                }
            except Exception:
                result["systems"][str(system_id)] = {"message_count": 0}
    
    # Extract protocol information
    if hasattr(adapter, 'protocols'):
        for protocol in adapter.protocols:
            try:
                result["protocols"].append(protocol.name)
            except Exception:
                pass
    
    # Extract role information
    if hasattr(adapter, 'roles'):
        result["roles"] = [_serialize_value(role) for role in adapter.roles]
    
    return result


# ============================================================================
# JSON CONVERSION: Between dict and JSON format
# ============================================================================

def social_state_to_json(state_dict: Dict[str, Any], indent: int = 2) -> str:
    """Convert a social state dictionary to a JSON string."""
    return json.dumps(state_dict, indent=indent, default=str)


def json_to_social_state(json_str: str) -> Dict[str, Any]:
    """Parse a JSON string into a social state dictionary."""
    return json.loads(json_str)


# ============================================================================
# FILE I/O: Save and load social state
# ============================================================================

def save_social_state(adapter: Any, filepath: str, indent: int = 2) -> str:
    """Extract social state from adapter and save to a JSON file."""
    state = extract_social_state(adapter)
    json_str = social_state_to_json(state, indent)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(json_str)
    
    return filepath


def load_social_state_from_file(filepath: str) -> Dict[str, Any]:
    """Load a social state dictionary from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        json_str = f.read()
    
    return json_to_social_state(json_str)


# ============================================================================
# DESERIALIZATION: Convert serialized format back to structured data
# ============================================================================

def _deserialize_value(value: Any, role_map: Optional[Dict[str, Any]] = None) -> Any:
    """Recursively deserialize a value, reconstructing BSPL objects where possible.
    
    Args:
        value: The value to deserialize
        role_map: Optional mapping of role names to actual Role objects
    """
    if value is None:
        return None
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (str, int, float)):
        return value
    elif isinstance(value, dict):
        # Check if this is a serialized BSPL object
        if "__object_type__" in value and "name" in value:
            obj_name = value["name"]
            if value["__object_type__"] == "Role" and role_map:
                return role_map.get(obj_name, obj_name)
            return obj_name
        
        # Regular dict - recursively deserialize
        return {k: _deserialize_value(v, role_map) for k, v in value.items()}
    elif isinstance(value, list):
        return [_deserialize_value(v, role_map) for v in value]
    else:
        return value


def deserialize_social_state(state_dict: Dict[str, Any], role_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Deserialize a social state dictionary, reconstructing BSPL objects where possible."""
    return _deserialize_value(state_dict, role_map)


# ============================================================================
# HIGH-LEVEL UTILITIES: Convenient wrappers
# ============================================================================

def get_social_state_json(adapter: Any, indent: int = 2) -> str:
    """Extract social state from adapter and return as JSON string."""
    state = extract_social_state(adapter)
    return social_state_to_json(state, indent)


def load_social_state_from_json(json_str: str, role_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load and deserialize social state from a JSON string."""
    state_dict = json_to_social_state(json_str)
    return deserialize_social_state(state_dict, role_map)
